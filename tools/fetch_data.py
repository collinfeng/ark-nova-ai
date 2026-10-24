"""Download the card-site sources that tools/build_cards.py turns into data/cards.json.

Usage: python tools/fetch_data.py        (then: python tools/build_cards.py)

The card data is game content (Ark Nova by Mathias Wigge, published by Feuerland Spiele / Capstone Games), so
it is not part of this repository. It is read from the fan-made card list by Ender-Wiggin2019
(https://github.com/Ender-Wiggin2019/Next-Ark-Nova-Cards), at the commit the engine was built and tested
against. Files go to data/raw/ender-wiggin/ (git-ignored). Standard library only.
"""
import sys
import urllib.request
from pathlib import Path

REPO = "Ender-Wiggin2019/Next-Ark-Nova-Cards"
COMMIT = "6f67a11b9a038d75bb327cd1abfe20165d6c0055"
DEST = Path(__file__).resolve().parent.parent / "data" / "raw" / "ender-wiggin"
FILES = [
    "public/locales/en/common.json",
    "src/data/ActionCardDescriptions.ts",
    "src/data/ActionCards.ts",
    "src/data/AlternativeMapBoards.ts",
    "src/data/Animals.ts",
    "src/data/CardNames.ts",
    "src/data/EndGames.ts",
    "src/data/MapBoards.ts",
    "src/data/Models.ts",
    "src/data/ProjectBonuses.ts",
    "src/data/Projects.ts",
    "src/data/Sponsors.ts",
    "src/data/prehistoric/Animals.ts",
    "src/data/prehistoric/Projects.ts",
    "src/data/prehistoric/Sponsors.ts",
    "src/data/prehistoric/utils.ts",
    "src/types/ActionCard.ts",
    "src/types/AnimalCard.ts",
    "src/types/AnimalCardModel.ts",
    "src/types/Bonus.ts",
    "src/types/Card.ts",
    "src/types/CardSource.ts",
    "src/types/Comment.ts",
    "src/types/Effect.ts",
    "src/types/EndGameCard.ts",
    "src/types/EndangeredCategory.ts",
    "src/types/IAnimalCard.ts",
    "src/types/IMapBoard.tsx",
    "src/types/IRating.ts",
    "src/types/ISponsorCard.ts",
    "src/types/Icon.ts",
    "src/types/IconName.ts",
    "src/types/KeyWords.ts",
    "src/types/MapBoard.ts",
    "src/types/Order.ts",
    "src/types/ProjectCard.ts",
    "src/types/Requirement.ts",
    "src/types/Size.ts",
    "src/types/SpecialEnclosure.ts",
    "src/types/SponsorCard.ts",
    "src/types/Tags.ts",
    "src/types/quiz.ts",
]


def main():
    for name in FILES:
        url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{name}"
        target = DEST / name
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                target.write_bytes(response.read())
        except OSError as error:
            sys.exit(f"could not download {url}: {error}")
    print(f"{len(FILES)} files in {DEST.relative_to(Path.cwd()) if DEST.is_relative_to(Path.cwd()) else DEST}; "
          "next: python tools/build_cards.py")


if __name__ == "__main__":
    main()
