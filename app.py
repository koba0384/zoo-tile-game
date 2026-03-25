from pathlib import Path
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
    board_bounds,
)
from scoring import score_region

st.set_page_config(
    page_title="どうぶつえんタイルゲーム試作版",
    page_icon="🦁",
    layout="centered",
)

PLAYER_COLORS = ["#ef4444", "#2563eb", "#16a34a", "#a855f7"]
PLAYER_LABELS = ["赤", "青", "緑", "紫"]
ZOOM_STEPS = [2, 3, 4]
ZOOM_NAMES = {2: "近", 3: "中", 4: "遠"}


def inject_css():
    st.markdown(
        """
<style>
.block-container {
    max-width: 760px;
    padding-top: 0.4rem;
    padding-bottom: 0.8rem;
    padding-left: 0.5rem;
    padding-right: 0.5rem;
}
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
h1,h2,h3,p { margin: 0; }
.compact-card {
    background: linear-gradient(180deg, #fbfffc 0%, #f4f7ff 100%);
    border: 1px solid #dbe7df;
    border-radius: 18px;
    padding: 10px;
    box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
    margin-bottom: 8px;
}
.top-pills {
    display:flex;
    flex-wrap:wrap;
    gap:6px;
    align-items:center;
}
.pill {
    display:inline-block;
    padding:5px 9px;
    border-radius:999px;
    border:1px solid #d7e8dc;
    background:#eef6f0;
    font-size:12px;
}
.score-pill {
    font-weight:700;
}
.section-title {
    font-size:14px;
    font-weight:700;
    margin-bottom:6px;
}
.board-shell {
    background:#eaf7e3;
    border:1px solid #cadfc2;
    border-radius:20px;
    padding:8px;
}
.tile-card {
    width:100%;
    aspect-ratio:1 / 1;
    border-radius:10px;
    position:relative;
    background: linear-gradient(180deg, #d8f4ca 0%, #c8ecba 100%);
    box-shadow: inset 0 0 0 1px rgba(255,255,255,0.45), 0 1px 2px rgba(0,0,0,0.10);
    overflow:hidden;
}
.tile-card::after {
    content:"";
    position:absolute;
    inset:0;
    background:
      radial-gradient(circle at 20% 25%, rgba(255,255,255,0.20), transparent 18%),
      radial-gradient(circle at 75% 70%, rgba(255,255,255,0.12), transparent 16%);
    pointer-events:none;
}
.tile-card.current {
    width:84px;
    margin:0 auto;
}
.tile-emoji {
    position:absolute;
    inset:0;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:22px;
    z-index:2;
}
.tile-card.current .tile-emoji {
    font-size:36px;
}
.tile-meeple {
    position:absolute;
    top:3px;
    right:3px;
    color:#fff;
    border-radius:999px;
    padding:0 5px;
    font-size:10px;
    font-weight:700;
    z-index:3;
}
.fence-n,.fence-e,.fence-s,.fence-w {
    position:absolute;
    z-index:4;
}
.fence-n { left:0; right:0; top:0; border-top:5px solid #8b5a2b; }
.fence-e { top:0; bottom:0; right:0; border-right:5px solid #8b5a2b; }
.fence-s { left:0; right:0; bottom:0; border-bottom:5px solid #8b5a2b; }
.fence-w { top:0; bottom:0; left:0; border-left:5px solid #8b5a2b; }
.empty-cell {
    width:100%;
    aspect-ratio:1 / 1;
    border-radius:10px;
    background: rgba(255,255,255,0.20);
}
div[data-testid="stButton"] button {
    min-height: 0;
    height: 100%;
    width: 100%;
    padding: 0;
    border-radius: 10px;
    line-height: 1;
    font-size: 0;
}
.board-valid button {
    background: rgba(59,130,246,0.10) !important;
    border: 2px solid #3b82f6 !important;
    box-shadow: inset 0 0 0 2px rgba(255,255,255,0.45);
}
.board-selected button {
    background: rgba(34,197,94,0.16) !important;
    border: 2px solid #16a34a !important;
    box-shadow: 0 0 0 2px rgba(34,197,94,0.15);
}
.action-btn button {
    font-size: 18px !important;
    height: 46px !important;
    border-radius: 14px !important;
}
.confirm-btn button {
    background: #22c55e !important;
    border: 1px solid #16a34a !important;
    color: #fff !important;
}
.warn-note {
    color:#64748b;
    font-size:12px;
}
.log-line {
    font-size:13px;
    padding: 4px 0;
    border-bottom:1px solid #eef2f7;
}
hr.compact {
    margin: 8px 0;
    border: none;
    border-top: 1px solid #edf2f7;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def next_player(idx, num_players):
    return (idx + 1) % num_players


def board_center(board):
    if not board:
        return (0, 0)
    min_x, max_x, min_y, max_y = board_bounds(board)
    return ((min_x + max_x) // 2, (min_y + max_y) // 2)


def tile_html(tile, meeple=None, current=False):
    emoji = animal_to_emoji(tile.get("animal"))
    fences = []
    if tile["edges"][0] == "fence":
        fences.append("<div class='fence-n'></div>")
    if tile["edges"][1] == "fence":
        fences.append("<div class='fence-e'></div>")
    if tile["edges"][2] == "fence":
        fences.append("<div class='fence-s'></div>")
    if tile["edges"][3] == "fence":
        fences.append("<div class='fence-w'></div>")
    meeple_html = ""
    if meeple is not None:
        color = PLAYER_COLORS[meeple]
        label = PLAYER_LABELS[meeple]
        meeple_html = f"<div class='tile-meeple' style='background:{color};'>{label}</div>"
    current_class = " current" if current else ""
    return f"""
<div class='tile-card{current_class}'>
  {''.join(fences)}
  <div class='tile-emoji'>{emoji}</div>
  {meeple_html}
</div>
"""


def init_state():
    defaults = {
        "num_players": 2,
        "board": {},
        "deck": [],
        "scores": [0, 0],
        "current_player": 0,
        "current_tile": None,
        "selected_coord": None,
        "selected_rotation": 0,
        "log": [],
        "completed_regions": [],
        "last_scoring": None,
        "game_over": False,
        "final_scored": False,
        "zoom_radius": 3,
        "view_center": (0, 0),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_selection():
    st.session_state.selected_coord = None
    st.session_state.selected_rotation = 0


def score_completed_region(region):
    board = st.session_state.board
    animals = region_animals(board, region)
    meeple_counts, _ = region_meeples(board, region)
    enclosed_cells = enclosed_cells_by_region(board, region)
    nested_bonus, _ = compute_nested_bonus(
        st.session_state.completed_regions,
        enclosed_cells,
        region,
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
    winner_text = "、".join([PLAYER_LABELS[p] for p in winners]) if winners else "該当なし"
    st.session_state.last_scoring = {
        "title": "囲い完成",
        "animals": animals,
        "meeples": meeple_counts,
        "breakdown": breakdown,
        "winners": winners,
    }
    st.session_state.log.insert(0, f"囲い完成: {winner_text} が {total_points}点（{len(region)}マス）")


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
        points, breakdown = score_region(
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
        st.session_state.log.insert(0, f"終了時得点: {'、'.join(PLAYER_LABELS[p] for p in winners)} が {points}点")
        st.session_state.last_scoring = {
            "title": "終了時得点",
            "animals": animals,
            "meeples": meeple_counts,
            "breakdown": breakdown,
            "winners": winners,
        }
    st.session_state.final_scored = True


def draw_next_tile_for_turn():
    board = st.session_state.board
    deck = st.session_state.deck
    tile, recycled = draw_next_placeable_tile(board, deck, rotate_tile)
    if recycled:
        st.session_state.log.insert(0, f"置けないタイル {len(recycled)}枚を山札の下へ")
    st.session_state.current_tile = tile
    reset_selection()
    if tile is None:
        st.session_state.game_over = True
        score_endgame_regions()


def start_game(num_players=2):
    deck = build_deck()
    board = {}
    starter = starter_tile_from_deck(deck)
    board[(0, 0)] = {"tile": starter, "meeple": None}
    st.session_state.num_players = num_players
    st.session_state.board = board
    st.session_state.deck = deck
    st.session_state.scores = [0 for _ in range(num_players)]
    st.session_state.current_player = 0
    st.session_state.log = [f"スタート: (0,0) に {tile_label(starter)}"]
    st.session_state.completed_regions = []
    st.session_state.last_scoring = None
    st.session_state.game_over = False
    st.session_state.final_scored = False
    st.session_state.zoom_radius = 3
    st.session_state.view_center = (0, 0)
    draw_next_tile_for_turn()


def ensure_game():
    if not st.session_state.board:
        start_game(st.session_state.num_players)


def get_valid_rotation_map():
    tile = st.session_state.current_tile
    board = st.session_state.board
    valid_map = {}
    if tile is None:
        return valid_map
    for rotation in range(4):
        rotated = rotate_tile(tile, rotation)
        for coord in get_valid_positions(board, rotated):
            valid_map.setdefault(coord, [])
            if rotation not in valid_map[coord]:
                valid_map[coord].append(rotation)
    for coord in valid_map:
        valid_map[coord].sort()
    return valid_map


def select_coord(coord, valid_map):
    rotations = valid_map.get(coord, [])
    if not rotations:
        return
    st.session_state.selected_coord = coord
    if st.session_state.selected_rotation not in rotations:
        st.session_state.selected_rotation = rotations[0]
    st.session_state.view_center = coord


def cycle_rotation(valid_map):
    coord = st.session_state.selected_coord
    if not coord:
        return
    rotations = valid_map.get(coord, [])
    if len(rotations) <= 1:
        return
    current = st.session_state.selected_rotation
    idx = rotations.index(current) if current in rotations else 0
    st.session_state.selected_rotation = rotations[(idx + 1) % len(rotations)]


def current_rotated_tile(valid_map):
    tile = st.session_state.current_tile
    if tile is None:
        return None
    coord = st.session_state.selected_coord
    if coord and coord in valid_map and st.session_state.selected_rotation in valid_map[coord]:
        return rotate_tile(tile, st.session_state.selected_rotation)
    return rotate_tile(tile, 0)


def confirm_current_move(valid_map):
    coord = st.session_state.selected_coord
    tile = st.session_state.current_tile
    if coord is None or tile is None:
        return
    rotations = valid_map.get(coord, [])
    if st.session_state.selected_rotation not in rotations:
        return
    rotated = rotate_tile(tile, st.session_state.selected_rotation)
    result = place_tile(
        st.session_state.board,
        coord,
        rotated,
        player_idx=st.session_state.current_player,
        place_meeple=True,
    )
    region = result["region"]
    meeple_text = " / ミープル配置" if result["meeple_placed"] else " / ミープルなし"
    st.session_state.log.insert(
        0,
        f"{PLAYER_LABELS[st.session_state.current_player]}: {coord} に {tile_label(rotated)}{meeple_text}",
    )
    if region_is_complete(st.session_state.board, region):
        score_completed_region(region)
    st.session_state.current_player = next_player(st.session_state.current_player, st.session_state.num_players)
    st.session_state.view_center = coord
    draw_next_tile_for_turn()


def nudge_view(dx, dy):
    x, y = st.session_state.view_center
    st.session_state.view_center = (x + dx, y + dy)


def change_zoom(delta):
    current = st.session_state.zoom_radius
    idx = ZOOM_STEPS.index(current)
    new_idx = max(0, min(len(ZOOM_STEPS) - 1, idx + delta))
    st.session_state.zoom_radius = ZOOM_STEPS[new_idx]


def render_header(player_count):
    current = st.session_state.current_player
    pills = [
        f"<span class='pill'>手番 <b>{PLAYER_LABELS[current]}</b></span>",
        f"<span class='pill'>山札 <b>{len(st.session_state.deck)}</b></span>",
        f"<span class='pill'>ズーム <b>{ZOOM_NAMES[st.session_state.zoom_radius]}</b></span>",
    ]
    for idx in range(st.session_state.num_players):
        pills.append(
            f"<span class='pill score-pill' style='background:{PLAYER_COLORS[idx]}18;border-color:{PLAYER_COLORS[idx]}55;'>"
            f"<span style='color:{PLAYER_COLORS[idx]};'>{PLAYER_LABELS[idx]}</span> {st.session_state.scores[idx]}点</span>"
        )
    st.markdown(f"<div class='compact-card'><div class='top-pills'>{''.join(pills)}</div></div>", unsafe_allow_html=True)

    cols = st.columns([1, 1])
    with cols[0]:
        if st.button("新しいゲーム", use_container_width=True):
            start_game(player_count or 2)
            st.rerun()
    with cols[1]:
        st.caption("青い枠だけ置ける")


def render_board(valid_map):
    board = st.session_state.board
    center_x, center_y = st.session_state.view_center
    radius = st.session_state.zoom_radius
    xs = list(range(center_x - radius, center_x + radius + 1))
    ys = list(range(center_y - radius, center_y + radius + 1))

    st.markdown("<div class='compact-card'><div class='section-title'>盤面</div><div class='board-shell'>", unsafe_allow_html=True)
    for y in ys:
        cols = st.columns(len(xs), gap="small")
        for i, x in enumerate(xs):
            coord = (x, y)
            with cols[i]:
                if coord in board:
                    cell = board[coord]
                    st.markdown(tile_html(cell["tile"], meeple=cell.get("meeple")), unsafe_allow_html=True)
                elif coord in valid_map:
                    wrapper_class = "board-selected" if st.session_state.selected_coord == coord else "board-valid"
                    st.markdown(f"<div class='{wrapper_class}'>", unsafe_allow_html=True)
                    if st.button("\u00a0", key=f"place_{x}_{y}", use_container_width=True):
                        select_coord(coord, valid_map)
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='empty-cell'></div>", unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)


def render_current_tile_and_actions(valid_map):
    tile = st.session_state.current_tile
    selected = st.session_state.selected_coord
    st.markdown("<div class='compact-card'>", unsafe_allow_html=True)
    cols = st.columns([1, 2])
    with cols[0]:
        st.markdown("<div class='section-title'>現在タイル</div>", unsafe_allow_html=True)
        if tile is None:
            st.success("ゲーム終了")
        else:
            st.markdown(tile_html(current_rotated_tile(valid_map), current=True), unsafe_allow_html=True)
    with cols[1]:
        st.markdown("<div class='section-title'>操作</div>", unsafe_allow_html=True)
        if tile is None:
            st.write("終了時得点まで計算済みや。")
        elif selected is None:
            st.write("盤面の青い枠をタップして、場所を選んでや。")
        else:
            rotations = valid_map.get(selected, [])
            rot_text = f"向き {st.session_state.selected_rotation + 1}/{len(rotations)}"
            st.write(f"選択中: {selected} / {rot_text}")
        action_cols = st.columns(3)
        with action_cols[0]:
            disabled = selected is None or len(valid_map.get(selected, [])) <= 1
            st.markdown("<div class='action-btn'>", unsafe_allow_html=True)
            if st.button("↻", key="rotate_btn", disabled=disabled, use_container_width=True):
                cycle_rotation(valid_map)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with action_cols[1]:
            st.markdown("<div class='action-btn'>", unsafe_allow_html=True)
            if st.button("✕", key="cancel_btn", disabled=selected is None, use_container_width=True):
                reset_selection()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with action_cols[2]:
            st.markdown("<div class='action-btn confirm-btn'>", unsafe_allow_html=True)
            if st.button("✔", key="confirm_btn", disabled=selected is None, use_container_width=True):
                confirm_current_move(valid_map)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        nav1 = st.columns(3)
        with nav1[0]:
            st.markdown("<div class='action-btn'>", unsafe_allow_html=True)
            if st.button("＋", key="zoom_in", use_container_width=True):
                change_zoom(-1)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with nav1[1]:
            st.markdown("<div class='action-btn'>", unsafe_allow_html=True)
            if st.button("◎", key="center_btn", use_container_width=True):
                st.session_state.view_center = st.session_state.selected_coord or board_center(st.session_state.board)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with nav1[2]:
            st.markdown("<div class='action-btn'>", unsafe_allow_html=True)
            if st.button("－", key="zoom_out", use_container_width=True):
                change_zoom(1)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        nav2 = st.columns(3)
        with nav2[0]:
            st.markdown("<div class='action-btn'>", unsafe_allow_html=True)
            if st.button("←", key="pan_left", use_container_width=True):
                nudge_view(-1, 0)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with nav2[1]:
            st.markdown("<div class='action-btn'>", unsafe_allow_html=True)
            if st.button("↑", key="pan_up", use_container_width=True):
                nudge_view(0, -1)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with nav2[2]:
            st.markdown("<div class='action-btn'>", unsafe_allow_html=True)
            if st.button("→", key="pan_right", use_container_width=True):
                nudge_view(1, 0)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        nav3 = st.columns(3)
        with nav3[1]:
            st.markdown("<div class='action-btn'>", unsafe_allow_html=True)
            if st.button("↓", key="pan_down", use_container_width=True):
                nudge_view(0, 1)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_footer():
    with st.expander("得点とログ", expanded=False):
        for idx in range(st.session_state.num_players):
            st.write(f"{PLAYER_LABELS[idx]}: {st.session_state.scores[idx]}点")
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        for line in st.session_state.log[:12]:
            st.markdown(f"<div class='log-line'>{line}</div>", unsafe_allow_html=True)
    with st.expander("直近の得点内訳", expanded=False):
        last = st.session_state.last_scoring
        if not last:
            st.write("まだ得点処理はないで。")
        else:
            st.write(last["title"])
            bd = last.get("breakdown")
            if bd:
                st.write(f"合計: {bd['total']}点")
                st.write(f"動物点: {bd['animal_score']} / 完成ボーナス: {bd['completion_bonus']} / 内包ボーナス: {bd['nested_bonus']}")
                for item in bd.get("combo_details", []):
                    st.write(f"- {item['label']} +{item['score']}")
    with st.expander("ルール要約", expanded=False):
        st.write("- 青い枠だけ置ける")
        st.write("- 置ける向きが複数ある時だけ ↻ で回転")
        st.write("- ✔ で確定、囲いに誰もいなければ自動でミープル配置")
        st.write("- 囲い完成時は多数決、同数トップは全員得点")


def main():
    inject_css()
    init_state()

    count = st.segmented_control(
        "人数",
        options=[2, 3, 4],
        selection_mode="single",
        default=st.session_state.num_players,
        key="player_count_selector",
    )
    if count and count != st.session_state.num_players and not st.session_state.board:
        st.session_state.num_players = count

    ensure_game()
    valid_map = get_valid_rotation_map()

    if st.session_state.selected_coord not in valid_map:
        reset_selection()

    render_header(count)
    render_board(valid_map)
    render_current_tile_and_actions(valid_map)
    render_footer()


if __name__ == "__main__":
    main()
