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
    {"label": "遠", "radius": 4, "cell": 24},
    {"label": "中", "radius": 3, "cell": 34},
    {"label": "近", "radius": 2, "cell": 46},
]

APP_CSS = """
<style>
.block-container {
    padding-top: 0.7rem;
    padding-bottom: 6.3rem;
    padding-left: 0.65rem;
    padding-right: 0.65rem;
    max-width: 560px;
}
h1 {
    font-size: 2.05rem !important;
    line-height: 1.05 !important;
    margin-bottom: 0.2rem !important;
}
.status-card {
    border-radius: 14px;
    color: white;
    font-weight: 700;
    text-align: center;
    padding: 10px 12px;
    margin-bottom: 0.45rem;
}
.small-note {
    color:#64748b;
    font-size:0.84rem;
}
.top-tile-card {
    background:#f8fafc;
    border:1px solid #e5e7eb;
    border-radius:14px;
    padding:10px;
    margin-bottom:0.55rem;
}
.board-wrap {
    background:#ffffff;
    border:1px solid #e5e7eb;
    border-radius:14px;
    padding:10px 8px 8px 8px;
    margin-top:0.2rem;
}
.board-row-gap {
    margin-top: 2px;
}
.candidate-slot div[data-testid="stButton"] > button {
    min-height: 1.55rem;
    height: 100%;
    width: 100%;
    background: #eff6ff;
    border: 2px dashed #60a5fa;
    border-radius: 10px;
    color: transparent;
    padding: 0;
    box-shadow: none;
}
.candidate-slot div[data-testid="stButton"] > button:hover {
    border-color:#2563eb;
    background:#dbeafe;
}
.candidate-slot div[data-testid="stButton"] > button:focus {
    border-color:#2563eb;
    box-shadow:none;
}
.candidate-slot.selected-frame {
    display:flex;
    align-items:center;
    justify-content:center;
}
.tools-row div[data-testid="stButton"] > button,
.selection-row div[data-testid="stButton"] > button,
.meeple-row div[data-testid="stButton"] > button {
    min-height: 2.25rem;
    border-radius: 10px;
    padding: 0;
}
.selection-row div[data-testid="stButton"] > button[kind="primary"] {
    background:#16a34a;
    border-color:#16a34a;
}
.log-card {
    background:#f8fafc;
    border:1px solid #e5e7eb;
    border-radius:12px;
    padding:10px 12px;
    margin-bottom:8px;
    font-size:0.92rem;
}
.selection-bar {
    position: sticky;
    bottom: 0;
    background: rgba(255,255,255,0.96);
    backdrop-filter: blur(8px);
    border-top: 1px solid #e5e7eb;
    padding-top: 0.55rem;
    margin-top: 0.55rem;
    z-index: 100;
}
.selection-card {
    border:1px solid #dbeafe;
    background:#eff6ff;
    color:#1e3a8a;
    border-radius:14px;
    padding:10px 12px;
    margin-bottom: 8px;
    font-size:0.94rem;
}
.score-mini td, .score-mini th {
    padding: 0.2rem 0.3rem !important;
}
</style>
"""


def next_player(idx, num_players):
    return (idx + 1) % num_players



def coord_to_text(coord):
    return f"({coord[0]}, {coord[1]})"



def current_zoom_cfg():
    return ZOOM_LEVELS[st.session_state.get("zoom_level", 1)]



def render_tile_html(tile, meeple=None, size=60, selected=False, preview=False, show_rotate_hint=False):
    edges = tile["edges"]

    def border(edge):
        return "4px solid #111827" if edge == "fence" else "1.5px dashed #d1d5db"

    emoji = animal_to_emoji(tile.get("animal"))
    bg = "#ecfeff" if preview else "#ffffff"
    outline = (
        "box-shadow:0 0 0 3px #22c55e, 0 4px 10px rgba(0,0,0,0.12);"
        if selected
        else "box-shadow:0 1px 3px rgba(0,0,0,0.08);"
    )
    meeple_html = ""
    if meeple is not None:
        color = PLAYER_COLORS[meeple]
        label = PLAYER_LABELS[meeple]
        meeple_html = f"""
        <div style='position:absolute; top:2px; right:3px; font-size:10px; background:{color};
             color:white; padding:1px 5px; border-radius:999px; line-height:1.2; font-weight:700;'>
             {label}
        </div>
        """

    rotate_html = ""
    if show_rotate_hint:
        icon_size = max(15, int(size * 0.28))
        rotate_html = f"""
        <div style='position:absolute; right:3px; bottom:3px; width:{icon_size}px; height:{icon_size}px;
             border-radius:999px; background:rgba(255,255,255,0.92); border:1px solid #d1d5db;
             display:flex; align-items:center; justify-content:center; font-size:{max(10, int(size * 0.2))}px;'>↻</div>
        """

    return dedent(
        f"""
        <div style="
            width:{size}px;
            height:{size}px;
            display:flex;
            align-items:center;
            justify-content:center;
            position:relative;
            font-size:{max(18, int(size*0.48))}px;
            background:{bg};
            border-top:{border(edges[0])};
            border-right:{border(edges[1])};
            border-bottom:{border(edges[2])};
            border-left:{border(edges[3])};
            border-radius:10px;
            margin:auto;
            {outline}
        ">
            <div style="font-size:{max(18, int(size*0.48))}px; line-height:1;">{emoji}</div>
            {meeple_html}
            {rotate_html}
        </div>
        """
    ).strip()



def render_empty_slot_html(size=42, active=False):
    border = "2px dashed #60a5fa" if active else "1px dashed #e5e7eb"
    bg = "#eff6ff" if active else "transparent"
    return dedent(
        f"""
        <div style='width:{size}px; height:{size}px; border:{border}; border-radius:10px; background:{bg}; margin:auto;'></div>
        """
    ).strip()



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
    return {coord: sorted(set(rotations)) for coord, rotations in by_coord.items()}



def score_completed_region(region):
    board = st.session_state.board
    animals = region_animals(board, region)
    meeple_counts, _ = region_meeples(board, region)
    enclosed_cells = enclosed_cells_by_region(board, region)
    nested_bonus, _ = compute_nested_bonus(
        st.session_state.completed_regions, enclosed_cells, region
    )
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
    nested_text = f" / 内包ボーナス {nested_bonus}点" if nested_bonus else ""
    st.session_state.last_scoring = {
        "title": "囲い完成",
        "animals": animals,
        "meeples": meeple_counts,
        "breakdown": breakdown,
        "winners": winners,
    }
    st.session_state.log.insert(
        0,
        f"囲い完成: {winner_text} が {total_points}点獲得（{len(region)}タイル{nested_text}）",
    )



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
        points, _ = score_region(
            animals=animals,
            region_size=len(region),
            nested_bonus=0,
            completed=False,
        )
        top = max(meeple_counts.values())
        winners = [p for p, count in meeple_counts.items() if count == top]
        for player in winners:
            st.session_state.scores[player] += points
        remove_region_meeples(board, region)
        st.session_state.log.insert(
            0,
            f"終了時得点: {'、'.join(PLAYER_LABELS[p] for p in winners)} が {points}点獲得（未完成囲い）",
        )

    st.session_state.final_scored = True
    st.session_state.last_scoring = {
        "title": "終了時得点",
        "animals": [],
        "meeples": {},
        "breakdown": None,
        "winners": [],
    }



def board_center_from_cells(cells):
    if not cells:
        return (0, 0)
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return (round(sum(xs) / len(xs)), round(sum(ys) / len(ys)))



def reset_selection():
    st.session_state.selected_coord = None
    st.session_state.selected_rotation = None
    st.session_state.selection_place_meeple = False



def current_valid_map():
    if st.session_state.current_tile is None:
        return {}
    return valid_rotations_by_coord(st.session_state.board, st.session_state.current_tile)



def sync_view_center(preferred=None):
    if preferred is not None:
        st.session_state.view_center = preferred
        return
    cells = set(st.session_state.board.keys())
    if st.session_state.current_tile is not None:
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
    current, recycled = draw_next_placeable_tile(
        st.session_state.board,
        st.session_state.deck,
        rotate_tile,
    )
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
    if "selected_coord" not in st.session_state:
        st.session_state.selected_coord = None
    if "selected_rotation" not in st.session_state:
        st.session_state.selected_rotation = None
    if "selection_place_meeple" not in st.session_state:
        st.session_state.selection_place_meeple = False
    if "zoom_level" not in st.session_state:
        st.session_state.zoom_level = 1
    if "view_center" not in st.session_state:
        st.session_state.view_center = (0, 0)



def select_position(coord):
    rotations = current_valid_map().get(coord, [])
    if not rotations:
        return
    st.session_state.selected_coord = coord
    current = st.session_state.get("selected_rotation")
    st.session_state.selected_rotation = current if current in rotations else rotations[0]
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



def render_scoring_panel():
    last = st.session_state.last_scoring
    if not last:
        st.info("まだ得点イベントはありません。")
        return
    with st.expander(f"直近の得点: {last['title']}", expanded=False):
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
            rows.append(("内包ボーナス", breakdown["nested_bonus"], "完成済みの内側の囲い"))
        st.table({
            "項目": [r[0] for r in rows],
            "点": [r[1] for r in rows],
            "メモ": [r[2] for r in rows],
        })
        st.metric("合計", breakdown["total"])



def render_header():
    st.markdown(APP_CSS, unsafe_allow_html=True)
    st.title("🦁 どうぶつえんタイルゲーム試作版")
    st.caption("置ける場所だけ枠が出ます。枠をタップ → 必要なら回転 → ✔︎で確定。")
    if st.session_state.game_over:
        st.error("ゲーム終了")
    else:
        player = st.session_state.current_player
        st.markdown(
            f"<div class='status-card' style='background:{PLAYER_COLORS[player]};'>{PLAYER_LABELS[player]}プレイヤーの番</div>",
            unsafe_allow_html=True,
        )
    a, b, c = st.columns(3)
    a.markdown(f"**山札** {len(st.session_state.deck)}")
    b.markdown(f"**人数** {st.session_state.num_players}")
    c.markdown(f"**ズーム** {current_zoom_cfg()['label']}")



def render_current_tile_panel():
    tile = current_selected_tile() if st.session_state.get("selected_coord") is not None else rotate_tile(st.session_state.current_tile, 0)
    valid_count = len(current_valid_map())
    st.markdown("<div class='top-tile-card'>", unsafe_allow_html=True)
    left, right = st.columns([1, 1.5], gap="small")
    with left:
        st.markdown(
            render_tile_html(
                tile,
                size=90,
                selected=st.session_state.get("selected_coord") is not None,
                preview=st.session_state.get("selected_coord") is not None,
                show_rotate_hint=st.session_state.get("selected_coord") is not None and len(current_valid_map().get(st.session_state.get("selected_coord"), [])) > 1,
            ),
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("**現在のタイル**")
        st.markdown(f"<div class='small-note'>候補 {valid_count}か所</div>", unsafe_allow_html=True)
        coord = st.session_state.get("selected_coord")
        if coord is None:
            st.markdown("<div class='small-note'>青い枠をタップしてください</div>", unsafe_allow_html=True)
        else:
            st.markdown(
                f"<div class='small-note'>選択中 {coord_to_text(coord)} / 向き {st.session_state.selected_rotation * 90}°</div>",
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)



def render_board_tools():
    st.markdown("**盤面**")
    st.markdown("<div class='small-note'>スクロールなしで見やすいように、ズームと移動で盤面を切り替えます。</div>", unsafe_allow_html=True)
    st.markdown("<div class='tools-row'>", unsafe_allow_html=True)
    r1 = st.columns(5, gap="small")
    if r1[0].button("−", use_container_width=True, disabled=st.session_state.zoom_level == 0):
        st.session_state.zoom_level -= 1
        st.rerun()
    if r1[1].button("＋", use_container_width=True, disabled=st.session_state.zoom_level == len(ZOOM_LEVELS) - 1):
        st.session_state.zoom_level += 1
        st.rerun()
    if r1[2].button("←", use_container_width=True):
        x, y = st.session_state.view_center
        st.session_state.view_center = (x - 1, y)
        st.rerun()
    if r1[3].button("◎", use_container_width=True):
        sync_view_center(preferred=st.session_state.get("selected_coord"))
        st.rerun()
    if r1[4].button("→", use_container_width=True):
        x, y = st.session_state.view_center
        st.session_state.view_center = (x + 1, y)
        st.rerun()
    r2 = st.columns(3, gap="small")
    if r2[0].button("↑", use_container_width=True):
        x, y = st.session_state.view_center
        st.session_state.view_center = (x, y - 1)
        st.rerun()
    r2[1].markdown(f"<div class='small-note' style='text-align:center; padding-top:0.35rem;'>中心 {coord_to_text(st.session_state.view_center)}</div>", unsafe_allow_html=True)
    if r2[2].button("↓", use_container_width=True):
        x, y = st.session_state.view_center
        st.session_state.view_center = (x, y + 1)
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)



def visible_coords_and_valid_map():
    valid_map = current_valid_map() if st.session_state.current_tile is not None else {}
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

    st.markdown("<div class='board-wrap'>", unsafe_allow_html=True)
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
                    rotations = valid_map.get(coord, [])
                    if tile is not None:
                        st.markdown(
                            render_tile_html(
                                tile,
                                size=size,
                                selected=True,
                                preview=True,
                                show_rotate_hint=len(rotations) > 1,
                            ),
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(render_empty_slot_html(size=size, active=True), unsafe_allow_html=True)
                elif coord in valid_coords:
                    st.markdown("<div class='candidate-slot'>", unsafe_allow_html=True)
                    if st.button(" ", key=f"cand_{x}_{y}", use_container_width=True):
                        select_position(coord)
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.markdown(render_empty_slot_html(size=size, active=False), unsafe_allow_html=True)
        st.markdown("<div class='board-row-gap'></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)



def toggle_meeple_choice(value: bool):
    st.session_state.selection_place_meeple = value



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

    st.session_state.current_player = next_player(
        st.session_state.current_player,
        st.session_state.num_players,
    )
    st.session_state.view_center = coord
    draw_next_tile_for_turn()



def render_selection_bar():
    if st.session_state.current_tile is None:
        return

    coord = st.session_state.get("selected_coord")
    st.markdown("<div class='selection-bar'>", unsafe_allow_html=True)
    if coord is None:
        st.markdown(
            "<div class='selection-card'>青い枠だけ置けます。置きたい場所の枠をタップしてください。</div>",
            unsafe_allow_html=True,
        )
    else:
        rotations = current_valid_map().get(coord, [])
        rotate_note = " / ↻で回転可" if len(rotations) > 1 else " / 向き固定"
        st.markdown(
            f"<div class='selection-card'>選択中: {coord_to_text(coord)} / 向き {st.session_state.selected_rotation * 90}°{rotate_note}</div>",
            unsafe_allow_html=True,
        )
        allowed = current_selected_meeple_allowed()
        st.markdown("<div class='meeple-row'>", unsafe_allow_html=True)
        m1, m2 = st.columns(2, gap="small")
        on = bool(st.session_state.get("selection_place_meeple", False))
        if m1.button("ミープルなし", use_container_width=True, type="secondary" if on else "primary"):
            toggle_meeple_choice(False)
            st.rerun()
        if m2.button("ミープル置く", use_container_width=True, disabled=not allowed, type="primary" if on else "secondary"):
            toggle_meeple_choice(True)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='selection-row'>", unsafe_allow_html=True)
    row = st.columns(3, gap="small")
    if row[0].button("✖", use_container_width=True, disabled=coord is None):
        reset_selection()
        st.rerun()
    if row[1].button("↻", use_container_width=True, disabled=coord is None or len(current_valid_map().get(coord, [])) <= 1):
        rotate_selected_position()
        st.rerun()
    if row[2].button("✔︎", use_container_width=True, type="primary", disabled=coord is None):
        confirm_current_move()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)



def render_bottom_panels():
    with st.expander("スコア", expanded=False):
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
- 置ける場所だけ青い枠で表示されます
- 枠をタップすると、その場所で置ける向きに自動で切り替わります
- ↻ は、その場所で置ける向きだけ順番に回ります
- ✔︎ で確定、✖ でやり直しです
- ミープルは置けるときだけ ON にできます
- 囲い完成時は多数決、同点トップは全員得点です
            """
        )
        default_players = st.session_state.get("num_players", 2)
        num_players = st.selectbox("プレイヤー人数", [2, 3, 4], index=max(0, default_players - 2))
        if st.button("新しいゲーム", use_container_width=True):
            start_game(num_players)
            st.rerun()



def main():
    ensure_game()
    render_header()
    if st.session_state.current_tile is not None:
        render_current_tile_panel()
    else:
        st.info("これ以上置けるタイルがありません。終了時得点を反映済みです。")
    render_board_section()
    render_selection_bar()
    render_bottom_panels()
    if st.session_state.game_over:
        max_score = max(st.session_state.scores)
        winners = [PLAYER_LABELS[i] for i, score in enumerate(st.session_state.scores) if score == max_score]
        st.success(f"勝者: {' / '.join(winners)}（{max_score}点）")


if __name__ == "__main__":
    main()
