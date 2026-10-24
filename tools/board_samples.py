"""Write real Board JSON samples to web/samples/ for front-end work (run after changing arknova/play/view.py).

    python tools/board_samples.py [--checkpoint experiments/ppo/keep/long_s0_1B.pt]

Both sides are played by the network, the human side through Game.play, so every sample has records,
undo points and the AI's turn filled in. The game is not saved (current.json is untouched).
"""
import argparse
import json
from pathlib import Path

from arknova.play import view
from arknova.play.ai import LocalNet
from arknova.play.game import Game

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "samples"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=str(ROOT / "experiments" / "ppo" / "keep" / "long_s0_1B.pt"))
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()
    ai = LocalNet(args.checkpoint)
    OUT.mkdir(exist_ok=True)

    def write(name, game):
        (OUT / f"{name}.json").write_text(json.dumps(view.board(game), indent=1))
        print("wrote", name)

    write("setup", Game(ai, seed=args.seed))
    game = Game(ai, seed=args.seed)
    wanted = {"turn", "act_animals", "act_build"}
    names = {"turn": "turn", "act_animals": "animals", "act_build": "build"}
    while not game.state.over:
        if game.turn_done:
            if game.turn == 8:
                write("end_turn", game)
            game.end_turn()
            continue
        kind = game.state.stack[-1].kind
        if kind in wanted and game.turn >= 10:
            write(names[kind], game)
            wanted.discard(kind)
        game.play(game.analysis.best)
    write("over", game)


if __name__ == "__main__":
    main()
