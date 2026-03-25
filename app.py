from textwrap import dedent

import streamlit as st

from tile_data import build_deck, rotate_tile, animal_to_emoji, tile_label
from game_logic import (
    get_valid_positions,
    place_tile,
    starter_tile_from_deck,
    draw_next_placeable_tile,
    get_region,
    region_is_complete,
    region_animals,
    region_meeples,
    remove_region_meeples,
    enclosed_cells_by_region,
    compute_nested_bonus,
)
from scoring import score_region

st.set_page_config(
    page_title="どうぶつえんタイルゲーム試作版",
    page_icon="🦁",
    layout="centered",
)

PLAYER_COLORS = ["#ef4444", "#2563eb", "#16a34a", "#a855f7"]
PLAYER_LABELS = ["赤", "青", "緑", "紫"]
ZOOM_LEVELS = [
    {"label": "遠", "radius": 6, "cell": 18},
    {"label": "中", "radius": 4, "cell": 28},
    {"label": "近", "radius": 3, "cell": 40},
]

APP_CSS = """
<style>
.block-container {
    max-width: 560px;
    padding-top: 0.6rem;
    padding-bottom: 5.7rem;
    padding-left: 0.65rem;
    padding-right: 0.65rem;
}
h1 {
    font-size: 2rem !important;
    line-height: 1.04 !important;
    margin-bottom: 0.15rem !important;
}
.small-note {
    color:#64748b;
    font-size:0.82rem;
}
.status-pill {
    color:#fff;
    font-weight:800;
    text-align:center;
    border-radius:16px;
    padding:10px 12px;
    margin-bottom:0.55rem;
}
.surface-card {
    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    border:1px solid #e2e8f0;
    border-radius:16px;
    padding:10px;
    box-shadow:0 8px 22px rgba(15,23,42,0.06);
    margin-bottom:0.55rem;
}
.board-shell {
    background: linear-gradient(180deg, #d9f99d 0%, #bbf7d0 100%);
    border:1px solid #86efac;
    border-radius:18px;
    padding:8px 6px 6px 6px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.6), 0 8px 24px rgba(22,163,74,0.10);
}
.board-caption {
    display:flex;
    justify-content:space-between;
    align-items:center;
    font-size:0.82rem;
    color:#166534;
    margin:0 2px 8px 2px;
    font-weight:600;
}
div[data-testid="stButton"] > button {
    border-radius: 12px;
}
.board-btn div[data-testid="stButton"] > button {
    width:100%;
    min-height:1rem;
    height:100%;
    padding:0;
    border-radius:12px;
    border:0;
    background:transparent;
    box-shadow:none;
}
.board-btn div[data-testid="stButton"] > button:hover {
    border:0;
    background:transparent;
}
.board-btn div[data-testid="stButton"] > button:focus {
    border:0;
    box-shadow:none;
}
.candidate-btn div[data-testid="stButton"] > button {
    width:100%;
    min-height:1rem;
    height:100%;
    padding:0;
    border-radius:12px;
    border:2px solid #2563eb;
    background: rgba(255,255,255,0.55);
    box-shadow: 0 0 0 2px rgba(191,219,254,0.95), inset 0 0 0 1px rgba(255,255,255,0.7);
    color: transparent;
}
.candidate-btn div[data-testid="stButton"] > button:hover {
    background: rgba(219,234,254,0.95);
    border-color:#1d4ed8;
}
.candidate-btn div[data-testid="stButton"] > button:focus {
    border-color:#1d4ed8;
    box-shadow: 0 0 0 2px rgba(191,219,254,0.95), inset 0 0 0 1px rgba(255,255,255,0.7);
}
.flat-btn div[data-testid="stButton"] > button {
    min-height:2.3rem;
}
.green-btn div[data-testid="stButton"] > button {
    min-height:2.4rem;
    background:#16a34a;
    color:#fff;
    border:1px solid #16a34a;
    font-weight:800;
}
.green-btn div[data-testid="stButton"] > button:hover {
    background:#15803d;
    border-color:#15803d;
    color:#fff;
}
.red-btn div[data-testid="stButton"] > button {
    min-height:2.4rem;
    background:#fff1f2;
    color:#be123c;
    border:1px solid #fecdd3;
    font-weight:800;
}
.red-btn div[data-testid="stButton"] > button:hover {
    background:#ffe4e6;
}
.selection-bar {
    position: sticky;
    bottom: 0;
    z-index: 100;
    background: rgba(255,255,255,0.95);
    backdrop-filter: blur(10px);
    border-top:1px solid #e2e8f0;
    padding-top:0.5rem;
    margin-top:0.4rem;
}
.selection-note {
    background:#eff6ff;
    color:#1e3a8a;
    border:1px solid #bfdbfe;
    border-radius:14px;
    padding:10px 12px;
    margin-bottom:8px;
    font-size:0.92rem;
    font-weight:600;
}
.score-chip {
    display:inline-block;
    border-radius:999px;
    padding:3px 8px;
    margin-right:6px;
    font-size:0.8rem;
    color:#fff;
    font-weight:700;
}
.log-card {
    background:#f8fafc;
    border:1px solid #e2e8f0;
    border-radius:12px;
    padding:9px 10px;
    margin-bottom:8px;
    font-size:0.9rem;
}
hr.compact {
    margin: 0.45rem 0 0.45rem 0;
    border:0;
    border-top:1px solid #e2e8f0;
}
</style>
"""


def next_player(idx, num_players):
    return (idx + 1) % num_players


def coord_to_text(coord):
    return f"({coord[0]}, {coord[1]})"


def current_zoom_cfg():
    return ZOOM_LEVELS[st.session_state.get("zoom_level", 1)]


def board_center_from_cells(cells):
    if not cells:
        return (0, 0)
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return (round(sum(xs) / len(xs)), round(sum(ys) / len(ys)))


def render_tile_html(tile, meeple=None, size=60, selected=False, preview=False, rotate_hint=False):
    edges = tile["edges"]

    def border(edge):
        if edge == "fence":
            return f"{max(3, int(size*0.10))}px solid #7c3f00"
        return f"{max(1, int(size*0.05))}px dashed rgba(120,113,108,0.35)"

    emoji = animal_to_emoji(tile.get("animal"))
    grass = "#ecfccb" if preview else "#fefce8"
    outline = (
        "box-shadow:0 0 0 3px #22c55e, 0 10px 20px rgba(0,0,0,0.14);"
        if selected
        else "box-shadow:0 4px 10px rgba(0,0,0,0.10);"
    )
    inner_size = max(12, int(size * 0.40))
    badge = ""
    if meeple is not None:
        color = PLAYER_COLORS[meeple]
        badge = (
            f"<div style='position:absolute; top:2px; right:2px; min-width:{max(14, int(size*0.28))}px; "
            f"height:{max(14, int(size*0.28))}px; background:{color}; border:1px solid rgba(255,255,255,0.9); "
            f"border-radius:999px; color:#fff; font-size:{max(8, int(size*0.16))}px; display:flex; "
            f"align-items:center; justify-content:center; font-weight:800;'>{PLAYER_LABELS[meeple]}</div>"
        )
    rotate_html = ""
    if rotate_hint:
        rotate_html = (
            f"<div style='position:absolute; left:2px; bottom:2px; width:{max(14, int(size*0.26))}px; "
            f"height:{max(14, int(size*0.26))}px; background:rgba(255,255,255,0.92); border:1px solid #d1d5db; "
            f"border-radius:999px; font-size:{max(8, int(size*0.16))}px; display:flex; align-items:center; justify-content:center;'>↻</div>"
        )

    return dedent(
        f"""
        <div style="
            width:{size}px;
            height:{size}px;
            border-top:{border(edges[0])};
            border-right:{border(edges[1])};
            border-bottom:{border(edges[2])};
            border-left:{border(edges[3])};
            border-radius:{max(8, int(size*0.18))}px;
            background:linear-gradient(180deg, {grass} 0%, #dcfce7 100%);
            position:relative;
            display:flex;
            align-items:center;
            justify-content:center;
            margin:auto;
            {outline}
            overflow:hidden;
        ">
            <div style="position:absolute; inset:0; background:
                radial-gradient(circle at 20% 20%, rgba(255,255,255,0.32), transparent 30%),
                radial-gradient(circle at 70% 80%, rgba(134,239,172,0.25), transparent 28%);"></div>
            <div style="font-size:{inner_size}px; line-height:1; position:relative; z-index:1;">{emoji}</div>
            {badge}
            {rotate_html}
        </div>
        """
    ).strip()


def render_blank_cell_html(size=28, candidate=False):
    if candidate:
        return dedent(
            f"""
            <div style="
                width:{size}px;
                height:{size}px;
                border:2px solid #2563eb;
                border-radius:{max(8, int(size*0.22))}px;
                background:rgba(255,255,255,0.58);
                box-shadow:0 0 0 2px rgba(191,219,254,0.95), inset 0 0 0 1px rgba(255,255,255,0.6);
                margin:auto;
            "></div>
            """
        ).strip()
    return f"<div style='width:{size}px;height:{size}px;margin:auto;'></div>"


def available_rotations(board, tile):
    valid = {}
    for rotation in range(4):
        rotated = rotate_tile(tile, rotation)
        positions = get_valid_positions(board, rotated)
        if positions:
            valid[rotation] = positions
    return valid


def valid_rotations_by_coord(board, tile):
    by_coord = {}
    for rotation, positions in available_rotations(board, tile).items():
        for coord in positions:
            by_coord.setdefault(coord, []).append(rotation)
    return {coord: sorted(set(v)) for coord, v in by_coord.items()}


def score_completed_region(region):
    board = st.session_state.board
    animals = region_animals(board, region)
    meeple_counts, _ = region_meeples(board, region)
    enclosed_cells = enclosed_cells_by_region(board, region)
    nested_bonus, _ = compute_nested_bonus(st.session_state.completed_regions, enclosed_cells, region)
    total_points, breakdown = score_region(
        animals=animals,
        region_size=len(region),
        nested_bonus=nested_bonus,
        completed=True,
    )

    winners = []
    if meeple_counts:
        top = max(meeple_counts.values())
        winners = [p for p, count in meeple_counts.items() if count == top]
        for player in winners:
            st.session_state.scores[player] += total_points

    remove_region_meeples(board, region)
    st.session_state.completed_regions.append(
        {
            "cells": [list(c) for c in sorted(region)],
            "completion_bonus": len(region),
            "winners": winners,
            "total_points": total_points,
        }
    )

    winner_text = "、".join([f"{PLAYER_LABELS[p]}プレイヤー" for p in winners]) if winners else "該当なし"
    nested_text = f" / 内包 {nested_bonus}点" if nested_bonus else ""
    st.session_state.last_scoring = {
        "title": "囲い完成",
        "breakdown": breakdown,
        "winners": winners,
    }
    st.session_state.log.insert(0, f"囲い完成: {winner_text} が {total_points}点獲得（{len(region)}タイル{nested_text}）")


def score_endgame_regions():
    if st.session_state.final_scored:
        return
    seen = set()
    board = st.session_state.board
    for coord in list(board.keys()):
        region = frozenset(get_region(board, coord))
        if region in seen:
            continue
        seen.add(region)
        meeple_counts, _ = region_meeples(board, region)
        if not meeple_counts:
            continue
        animals = region_animals(board, region)
        points, _ = score_region(animals=animals, region_size=len(region), nested_bonus=0, completed=False)
        top = max(meeple_counts.values())
        winners = [p for p, count in meeple_counts.items() if count == top]
        for player in winners:
            st.session_state.scores[player] += points
        remove_region_meeples(board, region)
        st.session_state.log.insert(0, f"終了時得点: {'、'.join(PLAYER_LABELS[p] for p in winners)} が {points}点獲得")

    st.session_state.final_scored = True
    st.session_state.last_scoring = {"title": "終了時得点", "breakdown": None, "winners": []}


def reset_selection():
    st.session_state.selected_coord = None
    st.session_state.selected_rotation = None
    st.session_state.selection_place_meeple = False


def current_valid_map():
    tile = st.session_state.get("current_tile")
    if tile is None:
        return {}
    return valid_rotations_by_coord(st.session_state.board, tile)


def sync_view_center(preferred=None):
    if preferred is not None:
        st.session_state.view_center = preferred
        return
    cells = set(st.session_state.board.keys())
    if st.session_state.get("current_tile") is not None:
        cells |= set(current_valid_map().keys())
    st.session_state.view_center = board_center_from_cells(cells)


def start_game(num_players):
    deck = build_deck()
    board = {}
    starter = starter_tile_from_deck(deck)
    board[(0, 0)] = {"tile": starter, "meeple": None}
    st.session_state.board = board
    st.session_state.deck = deck
    st.session_state.num_players = num_players
    st.session_state.current_player = 0
    st.session_state.current_tile = None
    st.session_state.scores = [0 for _ in range(num_players)]
    st.session_state.log = [f"スタートタイルを (0, 0) に配置: {tile_label(starter)}"]
    st.session_state.completed_regions = []
    st.session_state.last_scoring = None
    st.session_state.game_over = False
    st.session_state.final_scored = False
    st.session_state.zoom_level = 1
    st.session_state.view_center = (0, 0)
    reset_selection()
    draw_next_tile_for_turn()


def draw_next_tile_for_turn():
    current, recycled = draw_next_placeable_tile(st.session_state.board, st.session_state.deck, rotate_tile)
    if recycled:
        st.session_state.log.insert(0, f"置けないタイルを山札の下へ: {len(recycled)}枚")
    if current is None:
        st.session_state.current_tile = None
        st.session_state.game_over = True
        reset_selection()
        score_endgame_regions()
        sync_view_center()
        return
    st.session_state.current_tile = current
    reset_selection()
    sync_view_center()


def ensure_game():
    if "board" not in st.session_state:
        start_game(2)
    for key, default in [
        ("selected_coord", None),
        ("selected_rotation", None),
        ("selection_place_meeple", False),
        ("zoom_level", 1),
        ("view_center", (0, 0)),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default


def select_position(coord):
    rotations = current_valid_map().get(coord, [])
    if not rotations:
        return
    st.session_state.selected_coord = coord
    cur = st.session_state.get("selected_rotation")
    st.session_state.selected_rotation = cur if cur in rotations else rotations[0]
    st.session_state.selection_place_meeple = False
    st.session_state.view_center = coord


def rotate_selected_position():
    coord = st.session_state.get("selected_coord")
    if coord is None:
        return
    rotations = current_valid_map().get(coord, [])
    if len(rotations) <= 1:
        return
    current = st.session_state.get("selected_rotation")
    if current not in rotations:
        st.session_state.selected_rotation = rotations[0]
        return
    idx = rotations.index(current)
    st.session_state.selected_rotation = rotations[(idx + 1) % len(rotations)]


def current_selected_tile():
    tile = st.session_state.get("current_tile")
    rotation = st.session_state.get("selected_rotation")
    if tile is None or rotation is None:
        return None
    return rotate_tile(tile, rotation)


def current_selected_meeple_allowed():
    coord = st.session_state.get("selected_coord")
    tile = current_selected_tile()
    if coord is None or tile is None:
        return False
    preview_board = dict(st.session_state.board)
    preview_board[coord] = {"tile": tile, "meeple": None}
    temp_region = get_region(preview_board, coord)
    counts, _ = region_meeples(preview_board, temp_region)
    return len(counts) == 0


def score_table_data():
    return {
        "プレイヤー": [f"{PLAYER_LABELS[i]}プレイヤー" for i in range(st.session_state.num_players)],
        "点数": st.session_state.scores,
    }


def render_header():
    st.markdown(APP_CSS, unsafe_allow_html=True)
    st.title("🦁 どうぶつえんタイルゲーム試作版")
    st.caption("置ける場所だけ青い枠が出ます。枠をタップ → ↻で回転 → ✔で確定。")
    if st.session_state.game_over:
        st.error("ゲーム終了")
    else:
        p = st.session_state.current_player
        st.markdown(
            f"<div class='status-pill' style='background:{PLAYER_COLORS[p]};'>{PLAYER_LABELS[p]}プレイヤーの番</div>",
            unsafe_allow_html=True,
        )

    top = st.columns([1, 1, 1], gap="small")
    top[0].markdown(f"**山札** {len(st.session_state.deck)}")
    top[1].markdown(f"**人数** {st.session_state.num_players}")
    top[2].markdown(f"**ズーム** {current_zoom_cfg()['label']}")


def render_current_tile_panel():
    current_tile = st.session_state.get("current_tile")
    if current_tile is None:
        return
    selected = st.session_state.get("selected_coord") is not None
    tile = current_selected_tile() if selected else rotate_tile(current_tile, 0)
    valid_count = len(current_valid_map())
    st.markdown("<div class='surface-card'>", unsafe_allow_html=True)
    left, right = st.columns([1, 1.6], gap="small")
    with left:
        st.markdown(
            render_tile_html(
                tile,
                size=88,
                selected=selected,
                preview=selected,
                rotate_hint=selected and len(current_valid_map().get(st.session_state.get("selected_coord"), [])) > 1,
            ),
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("**現在のタイル**")
        st.markdown(f"<div class='small-note'>候補 {valid_count}か所</div>", unsafe_allow_html=True)
        coord = st.session_state.get("selected_coord")
        if coord is None:
            st.markdown("<div class='small-note'>まず盤面の青い枠をタップ</div>", unsafe_allow_html=True)
        else:
            rot = st.session_state.get("selected_rotation", 0) * 90
            st.markdown(f"<div class='small-note'>選択中 {coord_to_text(coord)} / {rot}°</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def shift_view(dx=0, dy=0):
    x, y = st.session_state.get("view_center", (0, 0))
    st.session_state.view_center = (x + dx, y + dy)


def render_board_tools():
    st.markdown("<div class='surface-card'>", unsafe_allow_html=True)
    st.markdown("**盤面**")
    st.markdown("<div class='small-note'>青い枠だけ置けます。青い枠が出ない空白は置けません。</div>", unsafe_allow_html=True)
    z = current_zoom_cfg()
    t1 = st.columns(5, gap="small")
    with t1[0]:
        if st.button("遠", use_container_width=True, type="primary" if z["label"] == "遠" else "secondary"):
            st.session_state.zoom_level = 0
            st.rerun()
    with t1[1]:
        if st.button("中", use_container_width=True, type="primary" if z["label"] == "中" else "secondary"):
            st.session_state.zoom_level = 1
            st.rerun()
    with t1[2]:
        if st.button("近", use_container_width=True, type="primary" if z["label"] == "近" else "secondary"):
            st.session_state.zoom_level = 2
            st.rerun()
    with t1[3]:
        if st.button("◎", use_container_width=True):
            sync_view_center(preferred=st.session_state.get("selected_coord"))
            st.rerun()
    with t1[4]:
        if st.button("新規", use_container_width=True):
            start_game(st.session_state.num_players)
            st.rerun()

    t2 = st.columns(3, gap="small")
    with t2[0]:
        if st.button("←", use_container_width=True):
            shift_view(dx=-2)
            st.rerun()
    with t2[1]:
        st.markdown(
            f"<div class='small-note' style='text-align:center;padding-top:0.45rem;'>中心 {coord_to_text(st.session_state.view_center)}</div>",
            unsafe_allow_html=True,
        )
    with t2[2]:
        if st.button("→", use_container_width=True):
            shift_view(dx=2)
            st.rerun()

    t3 = st.columns(3, gap="small")
    with t3[0]:
        if st.button("↑", use_container_width=True):
            shift_view(dy=-2)
            st.rerun()
    with t3[1]:
        st.markdown("<div class='small-note' style='text-align:center;padding-top:0.45rem;'>ズームで俯瞰できます</div>", unsafe_allow_html=True)
    with t3[2]:
        if st.button("↓", use_container_width=True):
            shift_view(dy=2)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def visible_coords_and_valid_map():
    valid_map = current_valid_map() if st.session_state.get("current_tile") is not None else {}
    center_x, center_y = st.session_state.get("view_center", (0, 0))
    cfg = current_zoom_cfg()
    radius = cfg["radius"]
    xs = list(range(center_x - radius, center_x + radius + 1))
    ys = list(range(center_y - radius, center_y + radius + 1))
    return xs, ys, valid_map


def render_board_section():
    render_board_tools()
    xs, ys, valid_map = visible_coords_and_valid_map()
    valid_coords = set(valid_map.keys())
    size = current_zoom_cfg()["cell"]

    st.markdown("<div class='board-shell'>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='board-caption'><span>見えている範囲 {len(xs)}×{len(ys)}</span><span>置ける場所 {len(valid_coords)}</span></div>",
        unsafe_allow_html=True,
    )
    for y in ys:
        cols = st.columns(len(xs), gap="small")
        for idx, x in enumerate(xs):
            coord = (x, y)
            with cols[idx]:
                if coord in st.session_state.board:
                    cell = st.session_state.board[coord]
                    st.markdown(render_tile_html(cell["tile"], cell.get("meeple"), size=size), unsafe_allow_html=True)
                elif coord == st.session_state.get("selected_coord"):
                    tile = current_selected_tile()
                    rots = valid_map.get(coord, [])
                    if tile is not None:
                        st.markdown(
                            render_tile_html(tile, size=size, selected=True, preview=True, rotate_hint=len(rots) > 1),
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(render_blank_cell_html(size=size, candidate=True), unsafe_allow_html=True)
                elif coord in valid_coords:
                    st.markdown("<div class='candidate-btn board-btn'>", unsafe_allow_html=True)
                    if st.button(" ", key=f"cand_{x}_{y}", use_container_width=True):
                        select_position(coord)
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.markdown(render_blank_cell_html(size=size, candidate=False), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def confirm_current_move():
    coord = st.session_state.get("selected_coord")
    tile = current_selected_tile()
    if coord is None or tile is None:
        return

    info = place_tile(
        st.session_state.board,
        coord,
        tile,
        player_idx=st.session_state.current_player,
        place_meeple=bool(st.session_state.get("selection_place_meeple", False)),
    )
    log_line = f"{PLAYER_LABELS[st.session_state.current_player]}が {coord_to_text(coord)} に {tile_label(tile)} を配置"
    if info["meeple_placed"]:
        log_line += " / ミープル配置"
    st.session_state.log.insert(0, log_line)
    region = info["region"]
    if region_is_complete(st.session_state.board, region):
        score_completed_region(region)
    st.session_state.current_player = next_player(st.session_state.current_player, st.session_state.num_players)
    st.session_state.view_center = coord
    draw_next_tile_for_turn()


def render_selection_bar():
    if st.session_state.get("current_tile") is None:
        return
    coord = st.session_state.get("selected_coord")
    st.markdown("<div class='selection-bar'>", unsafe_allow_html=True)
    if coord is None:
        st.markdown("<div class='selection-note'>青い枠だけタップできます。まず置く場所を選んでください。</div>", unsafe_allow_html=True)
    else:
        rotations = current_valid_map().get(coord, [])
        note = "回転あり" if len(rotations) > 1 else "回転なし"
        st.markdown(
            f"<div class='selection-note'>選択中 {coord_to_text(coord)} / 向き {st.session_state.selected_rotation * 90}° / {note}</div>",
            unsafe_allow_html=True,
        )
        allowed = current_selected_meeple_allowed()
        mcols = st.columns(2, gap="small")
        with mcols[0]:
            if st.button("ミープルなし", use_container_width=True, type="primary" if not st.session_state.get("selection_place_meeple", False) else "secondary"):
                st.session_state.selection_place_meeple = False
                st.rerun()
        with mcols[1]:
            if st.button("ミープル置く", use_container_width=True, disabled=not allowed, type="primary" if st.session_state.get("selection_place_meeple", False) else "secondary"):
                st.session_state.selection_place_meeple = True
                st.rerun()
    a, b, c = st.columns([1, 1, 1.3], gap="small")
    with a:
        st.markdown("<div class='red-btn flat-btn'>", unsafe_allow_html=True)
        if st.button("✖ やり直し", use_container_width=True, disabled=coord is None):
            reset_selection()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with b:
        st.markdown("<div class='flat-btn'>", unsafe_allow_html=True)
        if st.button("↻ 回転", use_container_width=True, disabled=coord is None or len(current_valid_map().get(coord, [])) <= 1):
            rotate_selected_position()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with c:
        st.markdown("<div class='green-btn flat-btn'>", unsafe_allow_html=True)
        if st.button("✔ 配置", use_container_width=True, disabled=coord is None):
            confirm_current_move()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_scoring_panel():
    last = st.session_state.get("last_scoring")
    if not last:
        st.info("まだ得点イベントはありません。")
        return
    breakdown = last.get("breakdown")
    if not breakdown:
        st.write("終了時の未完成囲いを精算しました。")
        return
    rows = []
    for item in breakdown["animal_details"]:
        rows.append((item["label"], item["score"], item["note"]))
    for item in breakdown["combo_details"]:
        rows.append((item["label"], item["score"], item["note"]))
    if breakdown["completion_bonus"]:
        rows.append(("完成ボーナス", breakdown["completion_bonus"], "囲いのタイル数"))
    if breakdown["nested_bonus"]:
        rows.append(("内包ボーナス", breakdown["nested_bonus"], "内側の完成囲い"))
    st.table({"項目": [r[0] for r in rows], "点": [r[1] for r in rows], "メモ": [r[2] for r in rows]})
    st.metric("合計", breakdown["total"])


def render_bottom_panels():
    st.markdown("<div class='surface-card'>", unsafe_allow_html=True)
    chips = " ".join(
        [f"<span class='score-chip' style='background:{PLAYER_COLORS[i]};'>{PLAYER_LABELS[i]} {st.session_state.scores[i]}点</span>" for i in range(st.session_state.num_players)]
    )
    st.markdown(f"<div>{chips}</div>", unsafe_allow_html=True)
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)
    with st.expander("得点の詳細", expanded=False):
        st.table(score_table_data())
        render_scoring_panel()
    with st.expander("ログ", expanded=False):
        if not st.session_state.log:
            st.info("まだログはありません。")
        else:
            for entry in st.session_state.log[:12]:
                st.markdown(f"<div class='log-card'>• {entry}</div>", unsafe_allow_html=True)
    with st.expander("ルールと操作", expanded=False):
        st.markdown(
            """
- 置ける場所だけ**青い枠**が出ます
- 青い枠が出ない空白には置けません
- 枠をタップすると、その場所で置ける向きの1つが選ばれます
- **↻ 回転**で、その場所で置ける向きだけ順番に回ります
- **✔ 配置**で確定、**✖ やり直し**で場所選びから戻ります
- 囲い完成時は多数決で得点、同数トップは全員得点です
            """
        )
    st.markdown("</div>", unsafe_allow_html=True)


def main():
    ensure_game()
    render_header()
    render_current_tile_panel()
    render_board_section()
    render_selection_bar()
    render_bottom_panels()


if __name__ == "__main__":
    main()
