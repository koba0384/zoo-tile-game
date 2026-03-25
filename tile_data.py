
import json
import random
from copy import deepcopy
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "tiles.json"
EDGE_ORDER = ["N", "E", "S", "W"]
ANIMAL_EMOJI = {
    "lion": "🦁",
    "giraffe": "🦒",
    "flamingo": "🦩",
    "elephant": "🐘",
    "hippo": "🦛",
    "chimpanzee": "🐒",
    None: "·",
}

def load_tiles():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def build_deck(seed=None):
    deck = deepcopy(load_tiles())
    rng = random.Random(seed)
    rng.shuffle(deck)
    return deck

def rotate_tile(tile, steps):
    steps = steps % 4
    rotated = deepcopy(tile)
    rotated["rotation"] = steps
    if steps:
        rotated["edges"] = tile["edges"][-steps:] + tile["edges"][:-steps]
    else:
        rotated["edges"] = tile["edges"][:]
    return rotated

def animal_to_emoji(animal):
    return ANIMAL_EMOJI.get(animal, "·")

def tile_label(tile):
    animal = tile.get("animal")
    emoji = animal_to_emoji(animal)
    rotation = tile.get("rotation", 0)
    return f"{emoji} / {tile['pattern']} / rot{rotation}"
