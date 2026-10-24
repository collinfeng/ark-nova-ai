# Ark Nova AI

A rules engine for the board game **Ark Nova** and an AI that learns to play it by reinforcement learning
(PPO self-play), with a browser board to play against it.

**Demo: [collinfeng.com/ark-nova-ai](https://collinfeng.com/ark-nova-ai/)**: play against the AI in the
browser (guest play, no account needed when the server has a free place).

- **Engine** (`arknova/`): the base game for 2 players, all base maps (Map 0, maps 1-8 and A) with their
  special rules, cards, sponsors, conservation projects and final scoring. One Map 7 token (an animal
  silhouette with a 2) has an unknown meaning and no effect for now. Every decision is a list of legal
  options, so bots, networks and people play through the same interface.
- **Bots** (`arknova/bot.py`): a greedy bot and a look-ahead (beam) bot, used as baselines.
- **Reinforcement learning** (`arknova/rl/`, `tools/train_ppo.py`): an observation encoder, a policy/value
  network that scores each legal option, and asynchronous PPO self-play on many CPU workers and one GPU;
  multi-map training, weight averaging, benchmarks against fixed opponents.
- **Board** (`web/`, `arknova/play/`): React front end and FastAPI server. Play against a trained network
  or a bot, with the network's hints and move analysis; English and Simplified Chinese interface.

Unofficial fan project, not affiliated with the designer (Mathias Wigge) or the publishers (Feuerland Spiele,
Capstone Games). Buy the game, or play it on [Board Game Arena](https://boardgamearena.com/gamepanel?game=arknova).

## Setup

Python 3.11+ and [PyTorch](https://pytorch.org) (install it for your platform first), then:

```bash
pip install -r requirements.txt
```

### Card data

The card data is the game's content, so it is not in this repository. Two scripts rebuild it locally from
the fan-made card list by [Ender-Wiggin2019](https://github.com/Ender-Wiggin2019/Next-Ark-Nova-Cards):

```bash
python tools/fetch_data.py     # downloads its card sources (pinned commit) to data/raw/ (git-ignored)
python tools/build_cards.py    # writes data/cards.json and data/cards_base.json
```

`build_cards.py` also reads `data/overrides.json`, values taken from the printed cards that the text
source lacks (building shapes, project slot sizes, a few sponsor effects).

## Tests

```bash
python -m pytest -q            # fast tests (about 30 s)
python -m pytest -q -m ""      # everything, including whole-game tests
```

## Training

```bash
python tools/train_ppo.py --out experiments/ppo/run1 --max-decisions 1000000000 --minutes 600 \
    --lr 2.6e-4 --bench ""
```

`--maps all` trains one network on every map. `python tools/train_ppo.py --help` lists every option
(network size, value targets, learning-rate schedule, weight averaging, benchmarks). A run writes its log
(`history.jsonl`), checkpoints (`model_<N>M.pt`) and weight averages (`ema_<N>M.pt`) to its folder;
`tools/plot_runs.py` plots the curves and `tools/rl_panel.py` plays checkpoints and bots against each other.

Training is CPU-bound in the game engine: about 40,000 decisions per second with 32 worker processes and
one GPU, so a billion decisions takes 7-9 hours.

## Playing on the board

```bash
python -m arknova.play.server --checkpoint experiments/ppo/run1/model.pt   # game server on :8765
cd web && pnpm install && pnpm dev                                          # board on http://localhost:5173
```

Without a trained network, `--checkpoint greedy` (or `beam_2x3`, `beam_3x8`) plays against a built-in bot.
Trained networks are not distributed; train one as above.

See [web/README.md](web/README.md).

## Notes

Some code comments refer to design notes under `docs/`; those notes are not part of this repository.

## License

MIT for the code in this repository ([LICENSE](LICENSE)). Ark Nova itself, its card texts and artwork belong
to their owners and are not covered by this license. `data/maps/*.json` (map layouts) and
`data/overrides.json` (values read from the printed cards) are our own transcriptions of game components,
included only so that the engine can run; the rights to the game's content stay with its owners.
