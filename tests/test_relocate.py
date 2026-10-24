import arknova  # noqa: F401
from arknova import cards, engine as G
from arknova.actions import animals


def test_reptile_can_move_into_new_reptile_house():
    state = G.new_game(2, seed=0)
    while state.stack[-1].kind == "setup_keep":
        G.step(state, G.legal_options(state)[0])
    p0 = state.players[0]
    reptile = next(cid for cid, c in sorted(cards.all_cards().items()) if c["type"] == "animal"
                   and any(e["type"] == "Reptile House" and e["size"] > 0 for e in c["enclosure"]["special"])
                   and not c["enclosure"]["rock"] and not c["enclosure"]["water"])
    size = cards.card(reptile)["enclosure"]["standard_size"]
    enclosure, _ = p0.zoo.place("enclosure", size, p0.zoo.legal_placements("enclosure", size)[0])
    enclosure.occupied = True
    p0.zoo_cards.append(reptile)
    p0.housing[reptile] = (enclosure.id, 0)
    p0.upgraded.add("build")
    p0.money = 50
    p0.slots = ["animals", "cards", "association", "sponsors", "build"]
    G.step(state, ("act", "build", 0))
    option = next(o for o in G.legal_options(state) if o.key[1] == "reptile_house")
    G.step(state, option)
    while state.stack[-1].kind != "move_animals":  # placement bonuses, if any
        G.step(state, G.legal_options(state)[-1])
    G.step(state, ("move", reptile))
    house = next(b for b in p0.zoo.buildings if b.kind == "reptile_house")
    spaces = next(e["size"] for e in cards.card(reptile)["enclosure"]["special"])
    assert p0.housing[reptile] == (house.id, spaces) and house.used == spaces
    assert not enclosure.occupied
    animals.release_animal(state, 0, reptile)
    assert house.used == 0 and reptile in state.discard
