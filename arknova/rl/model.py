"""Policy and value network: one state vector per decision, one score per legal option. Version 3 (encoder v3);
version 2 is frozen in arknova/rl/v2."""
import torch
from torch import nn
from torch.nn import functional as F

from . import encode


def _mlp(*widths):
    layers = []
    for a, b in zip(widths, widths[1:]):
        layers += [nn.Linear(a, b), nn.ReLU()]
    return nn.Sequential(*layers[:-1])


class Net(nn.Module):
    """The defaults reproduce the first v2 network. The options are the "network hygiene" changes from the
    audit (docs/rl/06_audit.md), each switchable so their effects can be separated:
    - separate_value: the value head gets its own trunk instead of sharing the policy's;
    - input_norm: LayerNorm on the trunk input;
    - small_policy_init: last policy layer scaled by 0.01, so the policy starts near uniform;
    - policy_layers: hidden layers in the option-scoring head;
    - trunk_hidden, state_dim: widths of the trunks (hidden layer, output); 512 and 256 by default.
    Version 3 adds:
    - a learned embedding of which set each card slot belongs to (hand, own zoo, display, ...);
    - set_attention: transformer layers over all cards in the sets (0: none), so a card's representation can
      depend on the other cards (an animal and the enclosure it fits, a sponsor and the icons it scores);
    - option cards use their representation in context (the slot the encoder found for them) when the card
      lies in a set, plus the look-ahead columns (zero unless the encoder computes them);
    - aux_value: a second value head for an auxiliary return (see self.aux); needs nothing else;
    - privileged_value: the value trunk also reads hidden information (the opponent's hand and final cards,
      the next deck cards, a deck summary; encoder `privileged=True`). Needs separate_value, so that nothing
      hidden reaches the policy; the policy never reads those inputs either way."""

    def __init__(self, card_dim=64, word_dim=32, state_dim=256, option_dim=128, separate_value=False,
                 input_norm=False, small_policy_init=False, policy_layers=1, set_attention=0, attention_heads=4,
                 privileged_value=False, aux_value=False, trunk_hidden=512):
        super().__init__()
        size = encode.sizes()
        features = torch.from_numpy(encode.card_features())
        self.register_buffer("card_features", features)
        self.card_id = nn.Embedding(size["cards"], card_dim, padding_idx=0)
        self.card_printed = nn.Linear(features.shape[1], card_dim)
        self.card_context = nn.Linear(size["set_extra"], card_dim)  # where the card lies: slots taken, playable
        self.word = nn.Embedding(size["words"], word_dim, padding_idx=0)
        self.set_slices = [encode.SET_SLICES[name] for name, _ in encode.SETS]
        kinds = torch.cat([torch.full((sl.stop - sl.start,), k) for k, sl in enumerate(self.set_slices)])
        self.register_buffer("slot_kind", kinds)
        self.set_kind = nn.Embedding(len(self.set_slices), card_dim)
        self.attention = None
        if set_attention:
            self.global_token = nn.Parameter(torch.zeros(1, 1, card_dim))
            layer = nn.TransformerEncoderLayer(card_dim, attention_heads, dim_feedforward=2 * card_dim, dropout=0.0,
                                               batch_first=True, norm_first=True)
            self.attention = nn.TransformerEncoder(layer, set_attention, enable_nested_tensor=False)
        state_in = size["scalars"] + size["maps"] + 2 * card_dim * len(self.set_slices) + 2 * word_dim
        self.input_norm = nn.LayerNorm(state_in) if input_norm else None
        self.trunk = nn.Sequential(_mlp(state_in, trunk_hidden, state_dim), nn.ReLU())
        self.privileged = privileged_value
        if privileged_value and not separate_value:
            raise ValueError("privileged_value needs separate_value: hidden information must not reach the policy")
        priv_in = 0
        if privileged_value:
            self.priv_kind = nn.Embedding(size["priv_sets"], card_dim)
            kinds = torch.cat([torch.full((sl.stop - sl.start,), k)
                               for k, sl in enumerate(encode.PRIV_SLICES.values())])
            self.register_buffer("priv_slot_kind", kinds)
            self.priv_position = nn.Linear(1, card_dim)
            self.priv_slices = list(encode.PRIV_SLICES.values())
            priv_in = 2 * card_dim * len(self.priv_slices) + size["priv_scalars"]
            self.priv_norm = nn.LayerNorm(priv_in) if input_norm else None
        self.value_trunk = (nn.Sequential(_mlp(state_in + priv_in, trunk_hidden, state_dim), nn.ReLU())
                            if separate_value else None)
        self.option = nn.Sequential(
            nn.Linear(2 * word_dim + card_dim + size["option_numbers"] + size["cells"] + size["option_effects"],
                      option_dim), nn.ReLU())
        self.policy = _mlp(state_dim + option_dim, *([256] * policy_layers), 1)
        self.value = _mlp(state_dim, 256, 1)
        # aux_value: a second value head on the same value features, trained on another return (the shaped
        # win + margin/20) as an auxiliary task; the policy never uses it. forward() leaves its estimate in
        # self.last_aux so the network's outputs stay (logits, owner, value) for every caller.
        self.aux = _mlp(state_dim, 256, 1) if aux_value else None
        self.last_aux = None
        if small_policy_init:
            with torch.no_grad():
                self.policy[-1].weight.mul_(0.01)
                self.policy[-1].bias.zero_()

    pack_tokens = True  # attention over the occupied slots only (about 32 of 164); False: over all slots

    def _attend(self, sets, present):
        """Transformer layers over the cards in the sets. A global token that is never masked keeps rows without
        cards well defined. With pack_tokens, each row's cards are moved to the front (their order kept) and
        the batch is cut to the most cards any row has, so attention costs about (50 / 165)^2 of the full
        version; the result is scattered back to the slots. Same output either way (tested)."""
        if self.pack_tokens:
            longest = max(1, int(present.sum(1).max()))
            order = torch.argsort((~present).to(torch.uint8), dim=1, stable=True)[:, :longest]
            index = order.unsqueeze(-1).expand(-1, -1, sets.shape[-1])
            packed, mask = sets.gather(1, index), ~present.gather(1, order)
        else:
            packed, mask = sets, ~present
        tokens = torch.cat([self.global_token.expand(len(sets), -1, -1), packed], dim=1)
        mask = torch.cat([torch.zeros_like(mask[:, :1]), mask], dim=1)
        out = self.attention(tokens, src_key_padding_mask=mask)[:, 1:]
        if not self.pack_tokens:
            return out
        return torch.zeros_like(sets).scatter(1, index, out)  # empty slots get zero (masked again by the caller)

    def forward(self, batch):
        """batch: tensors from encode.collate. Returns (option logits [M], decision of each option [M], values [B])."""
        cards = self.card_id.weight + self.card_printed(self.card_features)
        cards = cards * (torch.arange(len(cards), device=cards.device) > 0).unsqueeze(1)  # row 0 = no card
        # lookups go through F.embedding / index_select: the gradient of plain indexing is very slow on the GPU
        present = (batch["sets"] > 0).unsqueeze(-1)
        sets = F.embedding(batch["sets"], cards) + self.card_context(batch["set_extras"]) + self.set_kind(self.slot_kind)
        if self.attention is not None:
            sets = self._attend(sets, present[..., 0])
        sets = sets * present  # [B, slots, D]
        pooled = []
        for span in self.set_slices:
            part, mask = sets[:, span], present[:, span]
            pooled.append(part.sum(1) / mask.sum(1).clamp(min=1))
            pooled.append(part.masked_fill(~mask, -1e4).amax(1).clamp(min=-10) * mask.any(1))
        context = self.word(batch["context"]).flatten(1)
        inputs = torch.cat([batch["scalars"], batch["maps"], *pooled, context], dim=1)
        if self.input_norm is not None:
            inputs = self.input_norm(inputs)
        state = self.trunk(inputs)
        if self.privileged:  # hidden information, for the value only (the policy below never sees it)
            present = (batch["priv_sets"] > 0).unsqueeze(-1)
            hidden = (F.embedding(batch["priv_sets"], cards) + self.priv_kind(self.priv_slot_kind)
                      + self.priv_position(batch["priv_positions"])) * present
            pooled = []
            for span in self.priv_slices:
                part, mask = hidden[:, span], present[:, span]
                pooled.append(part.sum(1) / mask.sum(1).clamp(min=1))
                pooled.append(part.masked_fill(~mask, -1e4).amax(1).clamp(min=-10) * mask.any(1))
            extra = torch.cat([*pooled, batch["priv_scalars"]], dim=1)
            if self.priv_norm is not None:
                extra = self.priv_norm(extra)
            value_state = self.value_trunk(torch.cat([inputs, extra], dim=1))
        else:
            value_state = self.value_trunk(inputs) if self.value_trunk is not None else state

        words = self.word(batch["option_words"])                      # [M, 1 + args, W]
        owner = torch.repeat_interleave(torch.arange(len(state), device=state.device), batch["counts"])
        option_cards = F.embedding(batch["option_cards"], cards)  # [M, cards, D]
        slots = batch["option_slots"]  # 1 + slot of each option card in its decision's sets, 0 if not in a set
        flat = sets.reshape(-1, sets.shape[-1])
        where = (owner.unsqueeze(1) * sets.shape[1] + (slots - 1).clamp(min=0)).reshape(-1)
        in_context = F.embedding(where, flat).reshape(option_cards.shape) * (slots > 0).unsqueeze(-1)
        option = self.option(torch.cat([words[:, 0], words[:, 1:].sum(1), (option_cards + in_context).sum(1),
                                        batch["option_numbers"], batch["option_cells"], batch["option_effects"]],
                                       dim=1))
        logits = self.policy(torch.cat([state.index_select(0, owner), option], dim=1)).squeeze(1)
        self.last_aux = self.aux(value_state).squeeze(1) if self.aux is not None else None
        return logits, owner, self.value(value_state).squeeze(1)


def to_tensors(batch, device):
    out = {}
    for key, array in batch.items():
        tensor = torch.as_tensor(array, device=device)
        out[key] = tensor.long() if key in ("context", "sets", "option_words", "option_cards", "option_slots",
                                            "priv_sets", "counts") else tensor.float()
    return out


def log_probabilities(logits, owner, n):
    """Log-softmax of the option scores within each decision."""
    top = torch.full((n,), -1e30, device=logits.device).scatter_reduce(0, owner, logits, "amax")
    total = torch.zeros(n, device=logits.device).index_add(0, owner, (logits - top.index_select(0, owner)).exp())
    return logits - top.index_select(0, owner) - total.log().index_select(0, owner)


def sample(logp, owner, counts):
    """One option per decision, drawn from the policy. Returns the index within each decision's options."""
    n = len(counts)
    noisy = logp - torch.log(-torch.log(torch.rand_like(logp).clamp_min(1e-20)))
    best = torch.full((n,), -1e30, device=logp.device).scatter_reduce(0, owner, noisy, "amax")
    position = torch.arange(len(logp), device=logp.device)
    picked = torch.full((n,), len(logp), device=logp.device).scatter_reduce(
        0, owner, torch.where(noisy >= best[owner], position, len(logp)), "amin")
    return picked - (counts.cumsum(0) - counts), picked


def entropy(logp, owner, n):
    return torch.zeros(n, device=logp.device).index_add(0, owner, -logp.exp() * logp)
