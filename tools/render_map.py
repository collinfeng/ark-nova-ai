"""Draw a transcribed zoo map (data/maps/<plan>.json, or Map 0 from the code) as hexes, to compare with
the board image by eye.

Usage: python tools/render_map.py data/maps/plan1.json [more.json ...] [--out-dir experiments/plots/maps]
       python tools/render_map.py map0
Water blue, rock grey, plain sand; Build II spaces outlined red; bonus names written on their space;
special cells hatched with their name; [col,row] printed small in each hex.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import RegularPolygon  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

COLOURS = {"W": "#7fb3d5", "R": "#a6a6a6", ".": "#f3e2b3"}


def load(source):
    if source == "map0":
        from arknova.hexmap import MAP0  # noqa: PLC0415
        columns = [[] for _ in range(9)]
        for (q, r), cell in sorted(MAP0.cells.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            token = {"water": "W", "rock": "R"}.get(cell.terrain, ".")
            if cell.build2_only:
                token = ".:build2"
            elif cell.bonus:
                token = f".:{cell.bonus}"
            columns[q].append(token)
        return {"map": "map0", "name": "Map 0", "columns": columns, "special": [], "special_spaces": []}
    return json.loads(Path(source).read_text())


def draw(data, out):
    fig, ax = plt.subplots(figsize=(11, 8))
    size = 1.0
    special = {}
    for entry in data.get("special", []) + data.get("special_spaces", []):
        if isinstance(entry, dict):
            for cell in entry.get("cells", []):
                special[tuple(cell)] = entry.get("name", "special")
    for col, tokens in enumerate(data["columns"]):
        for row, token in enumerate(tokens):
            x = col * 1.5 * size
            y = -(row * math.sqrt(3) * size + (0 if col % 2 else math.sqrt(3) / 2 * size))
            terrain = token.split(":")[0]
            hexagon = RegularPolygon((x, y), 6, radius=size * 0.97, orientation=math.pi / 6,
                                     facecolor=COLOURS.get(terrain, "#ffffff"),
                                     edgecolor="red" if token == ".:build2" else "black",
                                     linewidth=2.5 if token == ".:build2" else 0.8,
                                     hatch="//" if (col, row) in special else None)
            ax.add_patch(hexagon)
            ax.text(x, y + 0.55, f"{col},{row}", ha="center", va="center", fontsize=6, color="#555555")
            if ":" in token and token != ".:build2":
                ax.text(x, y, token.split(":", 1)[1], ha="center", va="center", fontsize=8, weight="bold")
            if (col, row) in special:
                ax.text(x, y - 0.45, special[(col, row)][:12], ha="center", va="center", fontsize=6, color="darkred")
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.axis("off")
    ax.set_title(f"{data.get('name', data['map'])} ({data['map']}) as transcribed")
    fig.tight_layout()
    fig.savefig(out, dpi=90)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs="+")
    parser.add_argument("--out-dir", default="experiments/plots/maps")
    args = parser.parse_args()
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for source in args.sources:
        data = load(source)
        counts = [len(c) for c in data["columns"]]
        expected = [6, 7, 6, 7, 6, 7, 6, 7, 6]
        flag = "" if counts == expected else f"  COLUMN LENGTHS {counts} != {expected}"
        out = out_dir / f"{data['map']}.png"
        draw(data, out)
        print(f"wrote {out}{flag}")


if __name__ == "__main__":
    main()
