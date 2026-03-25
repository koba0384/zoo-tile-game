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
ZOOM_OPTIONS = {
    "近": 3,
    "中": 4,
    "遠": 5,
}


def inject_css():
    st.markdown(
        """
<style>
.block-container {padding-top: 0.8rem; padding-bottom: 1rem; max-width: 820px;}
html, body, [class*="css"] {font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;}
.main-card {
    background: linear-gradient(180deg, #f8fffb 0%, #f5f7ff 100%);
    border: 1px solid #dbe7df;
    border-radius: 18px;
    padding: 14px 14px 12px 14px;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
    margin-bottom: 10px;
}
.stat-pill {
    display:inline-block; padding:6px 10px; border-radius:999px; margin:0 6px 6px 0;
    background:#eef6f0; border:1px solid #d7e8dc; font-size:13px;
}
.tile-card {
    width: 52px; height: 52px; border-radius: 10px; position: relative; margin: 0 auto;
    background: #dff4d7; box-shadow: inset 0 0 0 1px rgba(255,255,255,.4), 0 1px 3px rgba(0,0,0,.10);
}
.tile-card.large { width: 74px; height: 74px; }
.tile-emoji {position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:28px;}
.tile-card.large .tile-emoji { font-size: 38px; }
.tile-meeple {
    position:absolute; top:2px; right:4px; color:#fff; border-radius:999px; padding:0 5px; font-size:11px; font-weight:700;
}
.fence-n {position:absolute; left:0; right:0; top:0; border-top:6px solid #8b5a2b; border-radius:10px 10px 0 0;}
.fence-e {position:absolute; top:0; bottom:0; right:0; border-right:6px solid #8b5a2b; border-radius:0 10px 10px 0;}
.fence-s {position:absolute; left:0; right:0; bottom:0; border-bottom:6px solid #8b5a2b; border-radius:0 0 10px 10px;}
.fence-w {position:absolute; top:0; bottom:0; left:0; border-left:6px solid #8b5a2b; border-radius:10px 0 0 10px;}
.empty-cell {
    width: 52px; height: 52px; border-radius: 10px; margin: 0 auto;
    background: rgba(255,255,255,0.55); border: 1px solid #edf2f7;
}
.coord-label {text-align:center; font-size:10px; color:#90a4ae; margin-top:2px;}
.board-row-gap {margin-bottom: 5px;}
.selection-box {
    border: 2px dashed #38bdf8; background: #effaff; border-radius: 14px; padding: 10px;
}
.stButton > button {
    border-radius: 12px;
}
div[data-testid="stButton"] button[kind="primary"] {
    background: #22c55e;
    border: 1px solid #16a34a;
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


def tile_html(tile, meeple=None, large=False):
    size_class = "large" if large else ""
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
    return f"""
    <div class='tile-card {size_class}'>
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
        "zoom_name": "中",
        "view_center": (0, 0),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


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
    winner_text = "、".join([f"{PLAYER_LABELS[p]}" for p in winners]) if winners else "該当なし"
    st.session_state.last_scoring = {
        "title": "囲い完成",
        "animals": animals,
        "meeples": meeple_counts,
        "breakdown": breakdown,
        "winners": winners,
    }
    st.session_state.log.insert(
        0,
        f"囲い完成: {winner_text} が {total_points}点（{len(region)}マス）",
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
        st.session_state.log.insert(
            0,
            f"終了時得点: {'、'.join(PLAYER_LABELS[p] for p in winners)} が {points}点（未完成）",
        )
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


def current_rotated_tile(valid_map):
    tile = st.session_state.current_tile
    if tile is None:
        return None
    coord = st.session_state.selected_coord
    if coord and coord in valid_map and st.session_state.selected_rotation in valid_map[coord]:
        return rotate_tile(tile, st.session_state.selected_rotation)
    return rotate_tile(tile, 0)


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
    st.session_state.current_player = next_player(
        st.session_state.current_player,
        st.session_state.num_players,
    )
    st.session_state.view_center = coord
    draw_next_tile_for_turn()


def render_header():
    current = st.session_state.current_player
    deck_left = len(st.session_state.deck)
    pills = []
    pills.append(f"<span class='stat-pill'>手番: <b>{PLAYER_LABELS[current]}</b></span>")
    pills.append(f"<span class='stat-pill'>山札: <b>{deck_left}</b></span>")
    pills.append(f"<span class='stat-pill'>ズーム: <b>{st.session_state.zoom_name}</b></span>")
    score_pills = []
    for idx in range(st.session_state.num_players):
        score_pills.append(
            f"<span class='stat-pill' style='background:{PLAYER_COLORS[idx]}18;border-color:{PLAYER_COLORS[idx]}55;'>"
            f"<b style='color:{PLAYER_COLORS[idx]};'>{PLAYER_LABELS[idx]}</b> {st.session_state.scores[idx]}点</span>"
        )
    st.markdown("<div class='main-card'>" + "".join(pills + score_pills) + "</div>", unsafe_allow_html=True)


def render_top_controls():
    cols = st.columns([1, 1, 1, 1, 1])
    with cols[0]:
        if st.button("◀", use_container_width=True):
            x, y = st.session_state.view_center
            st.session_state.view_center = (x - 1, y)
            st.rerun()
    with cols[1]:
        if st.button("▶", use_container_width=True):
            x, y = st.session_state.view_center
            st.session_state.view_center = (x + 1, y)
            st.rerun()
    with cols[2]:
        zoom = st.segmented_control(
            "ズーム",
            options=list(ZOOM_OPTIONS.keys()),
            selection_mode="single",
            default=st.session_state.zoom_name,
            label_visibility="collapsed",
            key="zoom_selector",
        )
        if zoom and zoom != st.session_state.zoom_name:
            st.session_state.zoom_name = zoom
            st.rerun()
    with cols[3]:
        if st.button("▲", use_container_width=True):
            x, y = st.session_state.view_center
            st.session_state.view_center = (x, y - 1)
            st.rerun()
    with cols[4]:
        if st.button("▼", use_container_width=True):
            x, y = st.session_state.view_center
            st.session_state.view_center = (x, y + 1)
            st.rerun()
    if st.button("◎ 中心に戻す", use_container_width=True):
        if st.session_state.selected_coord:
            st.session_state.view_center = st.session_state.selected_coord
        else:
            st.session_state.view_center = board_center(st.session_state.board)
        st.rerun()


def render_current_tile(valid_map):
    st.markdown("<div class='main-card'>", unsafe_allow_html=True)
    st.subheader("現在のタイル")
    tile = st.session_state.current_tile
    if tile is None:
        st.success("山札が尽きたで。終了時得点まで計算済みや。")
        st.markdown("</div>", unsafe_allow_html=True)
        return
    selected = st.session_state.selected_coord
    rotated = current_rotated_tile(valid_map)
    st.markdown(tile_html(rotated, large=True), unsafe_allow_html=True)
    st.caption(tile_label(rotated))
    if selected:
        st.markdown(
            f"<div class='selection-box'><b>選択中:</b> {selected} / 向き rot{st.session_state.selected_rotation}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("青い枠のマスをタップして、置く場所を選んでや。")
    btn_cols = st.columns([1, 1, 1])
    with btn_cols[0]:
        rotate_disabled = not selected or len(valid_map.get(selected, [])) <= 1
        if st.button("↻ 回転", use_container_width=True, disabled=rotate_disabled):
            cycle_rotation(valid_map)
            st.rerun()
    with btn_cols[1]:
        if st.button("✖ やり直し", use_container_width=True, disabled=selected is None):
            reset_selection()
            st.rerun()
    with btn_cols[2]:
        if st.button("✔ 決定", type="primary", use_container_width=True, disabled=selected is None):
            confirm_current_move(valid_map)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_board(valid_map):
    board = st.session_state.board
    center_x, center_y = st.session_state.view_center
    radius = ZOOM_OPTIONS[st.session_state.zoom_name]
    xs = list(range(center_x - radius, center_x + radius + 1))
    ys = list(range(center_y - radius, center_y + radius + 1))

    st.markdown("<div class='main-card'>", unsafe_allow_html=True)
    st.subheader("盤面")
    st.caption("置ける場所だけ青い枠が出る。空白はタップ不可。")

    for y in ys:
        cols = st.columns(len(xs), gap="small")
        for i, x in enumerate(xs):
            coord = (x, y)
            with cols[i]:
                if coord in board:
                    cell = board[coord]
                    st.markdown(tile_html(cell["tile"], meeple=cell.get("meeple")), unsafe_allow_html=True)
                    st.markdown(f"<div class='coord-label'>{x},{y}</div>", unsafe_allow_html=True)
                elif coord in valid_map:
                    label = " "
                    border_text = ""
                    if st.session_state.selected_coord == coord:
                        border_text = "選"
                    if st.button(label + border_text, key=f"cand_{x}_{y}", use_container_width=True):
                        select_coord(coord, valid_map)
                        st.rerun()
                    st.caption(f"{x},{y}")
                else:
                    st.markdown("<div class='empty-cell'></div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='coord-label'>{x},{y}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_footer_panels():
    with st.expander("得点・直近ログ", expanded=False):
        for idx in range(st.session_state.num_players):
            st.write(f"{PLAYER_LABELS[idx]}: {st.session_state.scores[idx]}点")
        for line in st.session_state.log[:12]:
            st.write("-", line)
    with st.expander("直近の得点内訳", expanded=False):
        last = st.session_state.last_scoring
        if not last:
            st.write("まだ得点処理はないで。")
        else:
            st.write(last["title"])
            if last.get("breakdown"):
                bd = last["breakdown"]
                st.write(f"合計: {bd['total']}点")
                st.write(f"動物点: {bd['animal_score']} / 完成ボーナス: {bd['completion_bonus']} / 内包ボーナス: {bd['nested_bonus']}")
                if bd["combo_details"]:
                    for item in bd["combo_details"]:
                        st.write(f"- {item['label']} +{item['score']}")
    with st.expander("ルール要約", expanded=False):
        st.write("- 青い枠だけ置ける")
        st.write("- タップで場所を選ぶ")
        st.write("- ↻ はその場所で置ける向きだけ回る")
        st.write("- ✔で確定。自動でミープルを置ける囲いなら置く")
        st.write("- 囲い完成時は多数決。同数トップは全員得点")


def main():
    inject_css()
    init_state()

    top_cols = st.columns([1, 1])
    with top_cols[0]:
        player_count = st.segmented_control(
            "人数",
            options=[2, 3, 4],
            selection_mode="single",
            default=st.session_state.num_players,
            key="player_count_selector",
        )
    with top_cols[1]:
        if st.button("新しいゲーム", use_container_width=True):
            start_game(player_count or 2)
            st.rerun()

    if player_count and player_count != st.session_state.num_players and not st.session_state.board:
        st.session_state.num_players = player_count

    ensure_game()
    valid_map = get_valid_rotation_map()

    # selected coord becomes invalid after board changes or zoom/pan changes
    if st.session_state.selected_coord not in valid_map:
        reset_selection()

    render_header()
    render_top_controls()
    render_current_tile(valid_map)
    render_board(valid_map)
    render_footer_panels()


if __name__ == "__main__":
    main()
