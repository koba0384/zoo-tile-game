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
    {"label": "遠", "radius": 4, "cell": 34},
    {"label": "中", "radius": 3, "cell": 44},
    {"label": "近", "radius": 2, "cell": 56},
]

APP_CSS = """
<style>
.block-container {
    padding-top: 0.8rem;
    padding-bottom: 5.8rem;
    padding-left: 0.7rem;
    padding-right: 0.7rem;
    max-width: 760px;
}
.board-help {
    color:#64748b;
    font-size:0.88rem;
    margin-bottom:0.45rem;
}
.status-card {
    border-radius:14px;
    color:white;
    font-weight:700;
    text-align:center;
    padding:10px 12px;
    margin-bottom:0.55rem;
}
.tile-meta {
    color:#6b7280;
    font-size:0.9rem;
    margin-top:4px;
}
.log-card {
    background:#f8fafc;
    border:1px solid #e5e7eb;
    border-radius:12px;
    padding:10px 12px;
    margin-bottom:8px;
    font-size:0.94rem;
}
.selection-bar {
    position: sticky;
    bottom: 0;
    background: rgba(255,255,255,0.96);
    backdrop-filter: blur(8px);
    border-top: 1px solid #e5e7eb;
    padding-top: 0.55rem;
    margin-top: 0.65rem;
    z-index: 100;
}
.selection-card {
    border:1px solid #dbeafe;
    background:#eff6ff;
    color:#1e3a8a;
    border-radius:14px;
    padding:10px 12px;
    margin-bottom: 8px;
    font-size:0.95rem;
}
.compact-buttons div[data-testid="stButton"] > button {
    min-height: 2.35rem;
    padding: 0rem 0.35rem;
    font-size: 0.95rem;
}
.compact-buttons div[data-testid="stButton"] > button[kind="primary"] {
    background: #16a34a;
    border-color: #16a34a;
}
.compact-buttons div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: #15803d;
    border-color: #15803d;
}
.board-cell-btn div[data-testid="stButton"] > button {
    min-height: 1.8rem;
    padding: 0rem;
    border-radius: 10px;
    font-size: 1.05rem;
}
.board-tools div[data-testid="stButton"] > button {
    min-height: 2.2rem;
    padding: 0rem;
    border-radius: 10px;
}
.small-stat {
    font-size:0.86rem;
    color:#475569;
    margin-top:2px;
}
</style>
"""


def next_player(idx, num_players):
    return (idx + 1) % num_players


def coord_to_text(coord):
    return f"({coord[0]}, {coord[1]})"


def current_zoom_cfg():
    level = st.session_state.get("zoom_level", 1)
    return ZOOM_LEVELS[level]



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
        rotate_html = f"""
        <div style='position:absolute; right:3px; bottom:3px; width:{max(16, int(size*0.28))}px; height:{max(16, int(size*0.28))}px; border-radius:999px;
             background:rgba(255,255,255,0.92); border:1px solid #d1d5db; display:flex; align-items:center;
             justify-content:center; font-size:{max(10, int(size*0.2))}px;'>↻</div>
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
        valid_positions = get_valid_positions(board, rotated)
        if valid_positions:
            valid[rotation] = valid_positions
    return valid



def valid_rotations_by_coord(board, tile):
    by_coord = {}
    for rotation, positions in available_rotations(board, tile).items():
        for coord in positions:
            by_coord.setdefault(coord, []).append(rotation)
    for coord in by_coord:
        by_coord[coord] = sorted(set(by_coord[coord]))
    return by_coord



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
        f"囲い完成: {winner_text} が {total_points}点獲得（{len(region)}タイル{nested_text}）"
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
            f"終了時得点: {'、'.join(PLAYER_LABELS[p] for p in winners)} が {points}点獲得（未完成囲い）"
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
    st.session_state.rotation = 0
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
    st.session_state.rotation = 0
    reset_selection()
    sync_view_center()



def ensure_game():
    if "board" not in st.session_state:
        start_game(2)
    if "selected_coord" not in st.session_state:
        reset_selection()
    if "zoom_level" not in st.session_state:
        st.session_state.zoom_level = 1
    if "view_center" not in st.session_state:
        st.session_state.view_center = (0, 0)
    if "selection_place_meeple" not in st.session_state:
        st.session_state.selection_place_meeple = False



def current_valid_map():
    if st.session_state.current_tile is None:
        return {}
    return valid_rotations_by_coord(st.session_state.board, st.session_state.current_tile)



def select_position(coord):
    valid_map = current_valid_map()
    rotations = valid_map.get(coord, [])
    if not rotations:
        return
    st.session_state.selected_coord = coord
    if st.session_state.selected_rotation not in rotations:
        st.session_state.selected_rotation = rotations[0]
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

        st.table(
            {
                "項目": [r[0] for r in rows],
                "点": [r[1] for r in rows],
                "メモ": [r[2] for r in rows],
            }
        )
        st.metric("合計", breakdown["total"])



def render_header_and_status():
    st.markdown(APP_CSS, unsafe_allow_html=True)
    st.title("🦁 どうぶつえんタイルゲーム試作版")
    st.caption("置ける場所だけ表示。ズームと移動で盤面を俯瞰しつつ、最後に✔︎で確定します。")

    if st.session_state.game_over:
        st.error("ゲーム終了")
    else:
        player = st.session_state.current_player
        st.markdown(
            f"<div class='status-card' style='background:{PLAYER_COLORS[player]};'>{PLAYER_LABELS[player]}プレイヤーの番</div>",
            unsafe_allow_html=True,
        )

    left, center, right = st.columns([1.2, 1, 1])
    with left:
        st.markdown(f"**山札** {len(st.session_state.deck)}枚")
    with center:
        st.markdown(f"**人数** {st.session_state.num_players}人")
    with right:
        zoom_cfg = current_zoom_cfg()
        st.markdown(f"**ズーム** {zoom_cfg['label']}")



def render_top_compact_panel():
    current_tile = st.session_state.current_tile
    if current_tile is None:
        st.info("これ以上置けるタイルがありません。終了時得点を反映済みです。")
        return

    coord = st.session_state.get("selected_coord")
    tile = current_selected_tile() if coord is not None else rotate_tile(current_tile, 0)
    valid_count = len(current_valid_map())

    left, right = st.columns([1, 1.5], gap="small")
    with left:
        st.markdown(render_tile_html(tile, size=88, selected=coord is not None, preview=coord is not None), unsafe_allow_html=True)
    with right:
        st.markdown("**現在のタイル**")
        st.markdown(f"<div class='small-stat'>候補 {valid_count}か所</div>", unsafe_allow_html=True)
        if coord is None:
            st.markdown("<div class='small-stat'>場所をタップしてください</div>", unsafe_allow_html=True)
        else:
            st.markdown(
                f"<div class='small-stat'>選択中 {coord_to_text(coord)} / 向き {st.session_state.selected_rotation * 90}°</div>",
                unsafe_allow_html=True,
            )
            allowed = current_selected_meeple_allowed()
            place_meeple = st.toggle(
                "ミープルを置く",
                value=st.session_state.get("selection_place_meeple", False),
                disabled=not allowed,
                help="すでに誰かのミープルがつながっている囲いには置けません。",
            )
            st.session_state.selection_place_meeple = place_meeple if allowed else False



def render_board_tools():
    st.markdown("**盤面**")
    st.markdown("<div class='board-help'>青い枠だけタップできます。ズームで俯瞰、矢印で移動。</div>", unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5, gap="small")
    with c1:
        if st.button("−", key="zoom_out", use_container_width=True, disabled=st.session_state.zoom_level == 0):
            st.session_state.zoom_level -= 1
            st.rerun()
    with c2:
        if st.button("＋", key="zoom_in", use_container_width=True, disabled=st.session_state.zoom_level == len(ZOOM_LEVELS) - 1):
            st.session_state.zoom_level += 1
            st.rerun()
    with c3:
        if st.button("←", key="pan_left", use_container_width=True):
            x, y = st.session_state.view_center
            st.session_state.view_center = (x - 1, y)
            st.rerun()
    with c4:
        if st.button("◎", key="pan_center", use_container_width=True):
            preferred = st.session_state.get("selected_coord")
            sync_view_center(preferred=preferred)
            st.rerun()
    with c5:
        if st.button("→", key="pan_right", use_container_width=True):
            x, y = st.session_state.view_center
            st.session_state.view_center = (x + 1, y)
            st.rerun()

    c6, c7, c8 = st.columns(3, gap="small")
    with c6:
        if st.button("↑", key="pan_up", use_container_width=True):
            x, y = st.session_state.view_center
            st.session_state.view_center = (x, y - 1)
            st.rerun()
    with c7:
        st.markdown(
            f"<div class='small-stat' style='text-align:center;'>中心 {coord_to_text(st.session_state.view_center)}</div>",
            unsafe_allow_html=True,
        )
    with c8:
        if st.button("↓", key="pan_down", use_container_width=True):
            x, y = st.session_state.view_center
            st.session_state.view_center = (x, y + 1)
            st.rerun()



def visible_coords_and_valid_map():
    valid_map = current_valid_map() if st.session_state.current_tile is not None else {}
    center_x, center_y = st.session_state.view_center
    cfg = current_zoom_cfg()
    radius = cfg["radius"]
    xs = range(center_x - radius, center_x + radius + 1)
    ys = range(center_y - radius, center_y + radius + 1)
    return list(xs), list(ys), valid_map



def render_board_section():
    render_board_tools()
    xs, ys, valid_map = visible_coords_and_valid_map()
    valid_coords = set(valid_map.keys())
    size = current_zoom_cfg()["cell"]

    for y in ys:
        cols = st.columns(len(xs), gap="small")
        for idx, x in enumerate(xs):
            coord = (x, y)
            with cols[idx]:
                st.markdown("<div class='board-cell-btn'>", unsafe_allow_html=True)
                if coord in st.session_state.board:
                    cell = st.session_state.board[coord]
                    st.markdown(render_tile_html(cell["tile"], cell.get("meeple"), size=size), unsafe_allow_html=True)
                elif coord == st.session_state.get("selected_coord"):
                    rotations = valid_map.get(coord, [])
                    tile = current_selected_tile()
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
                    if len(rotations) > 1:
                        if st.button("↻", key=f"rotate_{x}_{y}", use_container_width=True):
                            rotate_selected_position()
                            st.rerun()
                    elif coord in valid_coords:
                        st.caption("固定")
                    else:
                        st.write("")
                elif coord in valid_coords:
                    st.markdown(render_empty_slot_html(size=size, active=True), unsafe_allow_html=True)
                    if st.button("", key=f"select_{x}_{y}", use_container_width=True):
                        select_position(coord)
                        st.rerun()
                else:
                    st.markdown(render_empty_slot_html(size=size, active=False), unsafe_allow_html=True)
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

    st.markdown("<div class='selection-bar compact-buttons'>", unsafe_allow_html=True)
    if coord is None:
        st.markdown(
            "<div class='selection-card'>まず、青い枠の場所をタップしてください。</div>",
            unsafe_allow_html=True,
        )
    else:
        rotation_count = len(current_valid_map().get(coord, []))
        rotate_note = " / ↻で回転可" if rotation_count > 1 else " / 向き固定"
        st.markdown(
            f"<div class='selection-card'>選択中: {coord_to_text(coord)} / 向き {st.session_state.selected_rotation * 90}°{rotate_note}</div>",
            unsafe_allow_html=True,
        )

    left, right = st.columns(2, gap="small")
    with left:
        if st.button("✖ やりなおし", use_container_width=True, disabled=coord is None):
            reset_selection()
            st.rerun()
    with right:
        if st.button("✔︎ 決定", type="primary", use_container_width=True, disabled=coord is None):
            confirm_current_move()
            st.rerun()
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
- 場所をタップすると、その場所で置ける向きに自動で切り替わります
- 選択したタイルの ↻ で、その場所で置ける向きだけ順番に回ります
- ✔︎ 決定で確定、✖ やりなおしで場所選びに戻ります
- 囲い完成時は多数決、同点トップは全員得点です
- ライオン、仲良し、サバンナ、にぎやか、群れ、内包ボーナス対応です
            """
        )
        default_players = st.session_state.get("num_players", 2)
        num_players = st.selectbox("プレイヤー人数", [2, 3, 4], index=max(0, default_players - 2))
        if st.button("新しいゲーム", use_container_width=True):
            start_game(num_players)
            st.rerun()



def main():
    ensure_game()
    render_header_and_status()
    render_top_compact_panel()
    st.markdown("<div class='board-tools'>", unsafe_allow_html=True)
    render_board_section()
    st.markdown("</div>", unsafe_allow_html=True)
    render_selection_bar()
    render_bottom_panels()

    if st.session_state.game_over:
        max_score = max(st.session_state.scores)
        winners = [PLAYER_LABELS[i] for i, score in enumerate(st.session_state.scores) if score == max_score]
        st.success(f"勝者: {' / '.join(winners)}（{max_score}点）")


if __name__ == "__main__":
    main()
