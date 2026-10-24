"""Fixed numbers of the base game. Sources and open questions: docs/RULES_NOTES.md."""

ACTIONS = ["animals", "build", "cards", "association", "sponsors"]
CONTINENTS = ["africa", "americas", "asia", "australia", "europe"]
UNIVERSITIES = ["hand", "science2", "science_rep"]  # hand limit 5 +1 rep | 2 science | 1 science +2 rep
ANIMAL_CATEGORIES = ["bird", "herbivore", "predator", "primate", "reptile", "bear", "pet"]

START_MONEY = 25
MAX_XTOKENS = 5
HAND_LIMIT = 3
HAND_LIMIT_UNIVERSITY = 5
BUILD_COST_PER_SPACE = 2
PARTNER_ZOO_DISCOUNT = 3
FULL_COVER_APPEAL = 7
DISPLAY_SIZE = 6
MAX_WORKERS = 4
MAX_PARTNER_ZOOS = 4

# Steps from the start space to the end of the break track (rulebook board picture, p. 4-5).
BREAK_TRACK = {1: 9, 2: 9, 3: 12, 4: 15}
PROJECTS_ABOVE_BOARD = {1: 2, 2: 2, 3: 3, 4: 4}
BASE_PROJECTS = {1: 3, 2: 3, 3: 3, 4: 4}

# (draw, discard, may_snap) by strength 1..5; strength above 5 uses the last entry.
CARDS_TABLE = {
    False: [(1, 1, False), (1, 0, False), (2, 1, False), (2, 0, False), (3, 1, True)],
    True: [(1, 0, False), (2, 1, False), (2, 0, True), (3, 1, True), (4, 1, True)],
}
ANIMALS_TABLE = {False: [0, 1, 1, 1, 2], True: [1, 1, 2, 2, 2]}
ANIMALS_II_REPUTATION_STRENGTH = 5

TASK_VALUE = {"reputation": 2, "partner_zoo": 3, "university": 4, "project": 5}
TASK_REPUTATION_GAIN = 2
DONATION_COSTS = {1: [2, 5, 5, 7, 7, 10, 10], 2: [2, 5, 7, 10], 3: [2, 5, 5, 7, 7, 10, 10], 4: [2, 5, 5, 7, 7, 10, 10]}
DONATION_FINAL_COST = 12

# Money income by appeal: (minimum appeal, income), ascending.
INCOME_THRESHOLDS = [
    (0, 5), (1, 6), (2, 7), (3, 8), (4, 9), (5, 10), (7, 11), (9, 12), (11, 13), (13, 14), (15, 15),
    (17, 16), (20, 17), (23, 18), (26, 19), (29, 20), (32, 21), (36, 22), (40, 23), (44, 24), (48, 25),
    (52, 26), (56, 27), (61, 28), (66, 29), (71, 30), (76, 31), (81, 32), (86, 33), (91, 34), (96, 35),
    (102, 36), (108, 37),
]


def appeal_income(appeal):
    income = INCOME_THRESHOLDS[0][1]
    for threshold, money in INCOME_THRESHOLDS:
        if appeal >= threshold:
            income = money
    return income


def target_appeal(conservation):
    """Lowest appeal value in the scoring area of this conservation space."""
    c = max(conservation, 0)
    label = 2 * c - 14 if c <= 10 else 6 + 3 * (c - 10)
    return 100 - label


def victory_points(appeal, conservation):
    return appeal - target_appeal(conservation)


REPUTATION_MAX = 15
REPUTATION_CAP_WITHOUT_CARDS_II = 9
REPUTATION_BONUS = {5: "upgrade", 8: "worker", 10: "card", 11: "conservation", 12: "xtoken",
                    13: "card", 14: "conservation", 15: "xtoken"}


def reputation_folders(reputation):
    """Number of display folders within reputation range."""
    for folders, top in enumerate([1, 3, 6, 9, 12, 15], start=1):
        if reputation <= top:
            return folders
    return 6


def folder_reputation(folder):
    """The reputation that brings display folder `folder` (1..6) into range."""
    return 0 if folder == 1 else [1, 3, 6, 9, 12][folder - 2] + 1


CONSERVATION_UPGRADE_OR_WORKER = 2
CONSERVATION_TILE_SPACES = [5, 8]
CONSERVATION_TILE_MONEY = 5
CONSERVATION_FINAL_CARD_DISCARD = 10

# The 9 base bonus tiles (community list on BoardGameGeek; multiplier confirmed by the official FAQ).
# Each is a list of (effect, amount).
BONUS_TILES = {
    "money10": [("money", 10)],
    "xtoken3": [("xtoken", 3)],
    "reputation2": [("reputation", 2)],
    "university": [("university", 1)],
    "partner_zoo": [("partner_zoo", 1)],
    "enclosure3": [("enclosure", 3)],
    "cards3": [("card", 3)],
    "multiplier": [("multiplier", 1)],
    "sponsor": [("sponsor_for_money", 1)],
}

# Placement bonuses printed on map spaces.
PLACEMENT_BONUS = {
    "money5": [("money", 5)], "money10": [("money", 10)], "xtoken": [("xtoken", 1)],
    "rep2": [("reputation", 2)], "card": [("card", 1)], "clever": [("clever", 1)],
}

# Per-map boards. Slot bonuses are indexed by the slot being filled (0-based).
MAPS = {
    "map0": {
        "partner_zoo_slots": [[], [("upgrade", 1)], [("worker", 1)], [("conservation", 2)]],
        "university_slots": [[], [("upgrade", 1)], [("conservation", 2)]],
        "last_worker": [("conservation", 2)],
        # Left-edge tokens, top to bottom: (effects, repeats every break).
        "tokens": [
            ([("card", 1)], True), ([("enclosure", 2)], True), ([("money", 5)], True),
            ([("conservation", 1)], True),
            ([("worker", 1)], False), ([("money", 12)], False), ([("xtoken", 3)], False),
        ],
    },
}
