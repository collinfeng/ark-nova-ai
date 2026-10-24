"""Policy and value network: one state vector per decision, one score per legal option."""
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
    - policy_layers: hidden layers in the option-scoring head."""

    def __init__(self, card_dim=64, word_dim=32, state_dim=256, option_dim=128, separate_value=False,
                 input_norm=False, small_policy_init=False, policy_layers=1):
        super().__init__()
        size = encode.sizes()
        features = torch.from_numpy(encode.card_features())
        self.register_buffer("card_features", features)
        self.card_id = nn.Embedding(size["cards"], card_dim, padding_idx=0)
        self.card_printed = nn.Linear(features.shape[1], card_dim)
        self.card_context = nn.Linear(size["set_extra"], card_dim)  # where the card lies: slots taken, playable
        self.word = nn.Embedding(size["words"], word_dim, padding_idx=0)
        self.set_slices = [encode.SET_SLICES[name] for name, _ in encode.SETS]
        state_in = size["scalars"] + size["maps"] + 2 * card_dim * len(self.set_slices) + 2 * word_dim
        self.input_norm = nn.LayerNorm(state_in) if input_norm else None
        self.trunk = nn.Sequential(_mlp(state_in, 512, state_dim), nn.ReLU())
        self.value_trunk = nn.Sequential(_mlp(state_in, 512, state_dim), nn.ReLU()) if separate_value else None
        self.option = nn.Sequential(
            nn.Linear(2 * word_dim + card_dim + size["option_numbers"] + size["cells"], option_dim), nn.ReLU())
        self.policy = _mlp(state_dim + option_dim, *([256] * policy_layers), 1)
        self.value = _mlp(state_dim, 256, 1)
        if small_policy_init:
            with torch.no_grad():
                self.policy[-1].weight.mul_(0.01)
                self.policy[-1].bias.zero_()

    def forward(self, batch):
        """batch: tensors from encode.collate. Returns (option logits [M], decision of each option [M], values [B])."""
        cards = self.card_id.weight + self.card_printed(self.card_features)
        cards = cards * (torch.arange(len(cards), device=cards.device) > 0).unsqueeze(1)  # row 0 = no card
        # lookups go through F.embedding / index_select: the gradient of plain indexing is very slow on the GPU
        present = (batch["sets"] > 0).unsqueeze(-1)
        sets = (F.embedding(batch["sets"], cards) + self.card_context(batch["set_extras"])) * present  # [B, slots, D]
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
        value_state = self.value_trunk(inputs) if self.value_trunk is not None else state

        words = self.word(batch["option_words"])                      # [M, 1 + args, W]
        option = self.option(torch.cat([words[:, 0], words[:, 1:].sum(1), F.embedding(batch["option_cards"], cards).sum(1),
                                        batch["option_numbers"], batch["option_cells"]], dim=1))
        owner = torch.repeat_interleave(torch.arange(len(state), device=state.device), batch["counts"])
        logits = self.policy(torch.cat([state.index_select(0, owner), option], dim=1)).squeeze(1)
        return logits, owner, self.value(value_state).squeeze(1)


def to_tensors(batch, device):
    out = {}
    for key, array in batch.items():
        tensor = torch.as_tensor(array, device=device)
        out[key] = tensor.long() if key in ("context", "sets", "option_words", "option_cards", "counts") else tensor.float()
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
