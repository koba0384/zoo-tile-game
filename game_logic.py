
from collections import deque
from copy import deepcopy

SIDES = ["N", "E", "S", "W"]
OFFSETS = {
    "N": (0, -1),
    "E": (1, 0),
    "S": (0, 1),
    "W": (-1, 0),
}
OPPOSITE = {"N": "S", "E": "W", "S": "N", "W": "E"}

def add_coords(a, b):
    return (a[0] + b[0], a[1] + b[1])

def board_bounds(board):
    if not board:
        return (0, 0, 0, 0)
    xs = [x for x, _ in board]
    ys = [y for _, y in board]
    return min(xs), max(xs), min(ys), max(ys)

def get_candidate_positions(board):
    if not board:
        return [(0, 0)]
    candidates = set()
    for coord in board:
        for side in SIDES:
            neighbor = add_coords(coord, OFFSETS[side])
            if neighbor not in board:
                candidates.add(neighbor)
    return sorted(candidates, key=lambda c: (c[1], c[0]))

def is_valid_placement(board, coord, tile):
    if coord in board:
        return False
    if not board:
        return coord == (0, 0)

    has_adjacent = False
    for side in SIDES:
        neighbor = add_coords(coord, OFFSETS[side])
        if neighbor in board:
            has_adjacent = True
            if tile["edges"][SIDES.index(side)] != board[neighbor]["tile"]["edges"][SIDES.index(OPPOSITE[side])]:
                return False
    return has_adjacent

def get_valid_positions(board, tile):
    return [coord for coord in get_candidate_positions(board) if is_valid_placement(board, coord, tile)]

def get_region(board, start):
    if start not in board:
        return set()

    region = set()
    q = deque([start])

    while q:
        coord = q.popleft()
        if coord in region:
            continue
        region.add(coord)
        tile = board[coord]["tile"]
        for idx, side in enumerate(SIDES):
            if tile["edges"][idx] != "open":
                continue
            neighbor = add_coords(coord, OFFSETS[side])
            if neighbor in board:
                other = board[neighbor]["tile"]
                if other["edges"][SIDES.index(OPPOSITE[side])] == "open":
                    q.append(neighbor)
    return region

def region_meeples(board, region):
    counts = {}
    placements = []
    for coord in region:
        meeple = board[coord].get("meeple")
        if meeple is None:
            continue
        counts[meeple] = counts.get(meeple, 0) + 1
        placements.append((coord, meeple))
    return counts, placements

def can_place_meeple(board, coord):
    region = get_region(board, coord)
    counts, _ = region_meeples(board, region)
    return len(counts) == 0

def region_is_complete(board, region):
    for coord in region:
        tile = board[coord]["tile"]
        for idx, side in enumerate(SIDES):
            if tile["edges"][idx] != "open":
                continue
            neighbor = add_coords(coord, OFFSETS[side])
            if neighbor not in board:
                return False
            other = board[neighbor]["tile"]
            if other["edges"][SIDES.index(OPPOSITE[side])] != "open":
                return False
    return True

def region_animals(board, region):
    animals = []
    for coord in region:
        animal = board[coord]["tile"].get("animal")
        if animal:
            animals.append(animal)
    return animals

def place_tile(board, coord, tile, player_idx=None, place_meeple=False):
    if not is_valid_placement(board, coord, tile):
        raise ValueError("Invalid placement")

    board[coord] = {
        "tile": deepcopy(tile),
        "meeple": None,
    }

    meeple_placed = False
    if place_meeple and can_place_meeple(board, coord):
        board[coord]["meeple"] = player_idx
        meeple_placed = True

    return {
        "coord": coord,
        "meeple_placed": meeple_placed,
        "region": get_region(board, coord),
    }

def remove_region_meeples(board, region):
    removed = []
    for coord in region:
        if board[coord].get("meeple") is not None:
            removed.append((coord, board[coord]["meeple"]))
            board[coord]["meeple"] = None
    return removed

def draw_next_placeable_tile(board, deck, rotate_tile):
    if not deck:
        return None, []
    recycled = []
    deck_size = len(deck)
    for _ in range(deck_size):
        tile = deck.pop(0)
        for rotation in range(4):
            rotated = rotate_tile(tile, rotation)
            if get_valid_positions(board, rotated):
                current = rotate_tile(tile, 0)
                return current, recycled
        deck.append(tile)
        recycled.append(tile["id"])
    return None, recycled

def starter_tile_from_deck(deck):
    if not deck:
        raise ValueError("Deck is empty")
    return deck.pop(0)

def _tile_edge(board, coord, side):
    if coord not in board:
        return "open"
    return board[coord]["tile"]["edges"][SIDES.index(side)]

def enclosed_cells_by_region(board, region):
    if not region:
        return set()

    min_x, max_x, min_y, max_y = board_bounds(board)
    min_x -= 2
    max_x += 2
    min_y -= 2
    max_y += 2

    all_cells = {
        (x, y)
        for x in range(min_x, max_x + 1)
        for y in range(min_y, max_y + 1)
        if (x, y) not in region
    }

    reachable = set()
    q = deque()

    for cell in all_cells:
        x, y = cell
        if x in {min_x, max_x} or y in {min_y, max_y}:
            q.append(cell)

    while q:
        cell = q.popleft()
        if cell in reachable or cell not in all_cells:
            continue
        reachable.add(cell)
        for side in SIDES:
            neighbor = add_coords(cell, OFFSETS[side])
            if neighbor not in all_cells:
                continue
            edge_a = _tile_edge(board, cell, side)
            edge_b = _tile_edge(board, neighbor, OPPOSITE[side])
            if edge_a == "open" and edge_b == "open":
                q.append(neighbor)

    return all_cells - reachable

def compute_nested_bonus(completed_regions, enclosed_cells, newly_completed_region):
    bonus = 0
    nested = []
    newly_cells = set(newly_completed_region)
    for meta in completed_regions:
        cells = set(tuple(c) for c in meta["cells"])
        if cells == newly_cells:
            continue
        if cells.issubset(enclosed_cells):
            bonus += meta.get("completion_bonus", 0)
            nested.append(meta)
    return bonus, nested
