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

MOBILE_CSS = """
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 5.5rem;
    padding-left: 0.8rem;
    padding-right: 0.8rem;
    max-width: 900px;
}
.small-note { color: #6b7280; font-size: 0.92rem; }
.log-card {
    background: #f8fafc;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 10px 12px;
    margin-bottom: 8px;
    font-size: 0.95rem;
}
.tile-meta {
    color:#6b7280;
    font-size: 0.9rem;
    margin-top: 4px;
}
.selection-bar {
    position: sticky;
    bottom: 0;
    background: rgba(255,255,255,0.96);
    backdrop-filter: blur(8px);
    padding: 0.7rem 0 0.3rem 0;
    border-top: 1px solid #e5e7eb;
    margin-top: 0.75rem;
    z-index: 100;
}
.selection-card {
    border:1px solid #dbeafe;
    background:#eff6ff;
    color:#1e3a8a;
    border-radius:14px;
    padding:10px 12px;
    margin-bottom: 10px;
    font-size:0.95rem;
}
.board-row-gap {
    margin-bottom: 0.35rem;
}
div[data-testid="stButton"] > button[kind="primary"] {
    background: #16a34a;
    border-color: #16a34a;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: #15803d;
    border-color: #15803d;
}
</style>
"""


def next_player(idx, num_players):
    return (idx + 1) % num_players


def coord_to_text(coord):
    return f"({coord[0]}, {coord[1]})"


def render_tile_html(tile, meeple=None, size=76, selected=False, show_rotate_hint=False):
    edges = tile["edges"]

    def border(edge):
        return "5px solid #111827" if edge == "fence" else "1.5px dashed #d1d5db"

    emoji = animal_to_emoji(tile.get("animal"))
    outline = "box-shadow:0 0 0 3px #22c55e, 0 4px 10px rgba(0,0,0,0.12);" if selected else "box-shadow:0 1px 3px rgba(0,0,0,0.08);"
    meeple_html = ""
    if meeple is not None:
        color = PLAYER_COLORS[meeple]
        label = PLAYER_LABELS[meeple]
        meeple_html = f"""
        <div style='position:absolute; top:3px; right:4px; font-size:11px; background:{color};
             color:white; padding:1px 6px; border-radius:999px; line-height:1.2; font-weight:700;'>
             {label}
        </div>
        """

    rotate_html = ""
    if show_rotate_hint:
        rotate_html = """
        <div style='position:absolute; right:4px; bottom:4px; width:22px; height:22px; border-radius:999px;
             background:rgba(255,255,255,0.92); border:1px solid #d1d5db; display:flex; align-items:center;
             justify-content:center; font-size:14px;'>↻</div>
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
            font-size:{max(24, int(size*0.48))}px;
            background:#ffffff;
            border-top:{border(edges[0])};
            border-right:{border(edges[1])};
            border-bottom:{border(edges[2])};
            border-left:{border(edges[3])};
            border-radius:10px;
            margin:auto;
            {outline}
        ">
            <div style="font-size:{max(24, int(size*0.48))}px; line-height:1;">{emoji}</div>
            {meeple_html}
            {rotate_html}
        </div>
        """
    ).strip()


def render_empty_slot_html(size=58, active=False):
    border = "2px dashed #60a5fa" if active else "1px dashed #e5e7eb"
    bg = "#eff6ff" if active else "transparent"
    return dedent(
        f"""
        <div style='width:{size}px; height:{size}px; border:{border}; border-radius:12px; background:{bg}; margin:auto;'></div>
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


def reset_selection():
    st.session_state.selected_coord = None
    st.session_state.selected_rotation = None
    st.session_state.place_meeple_desired = False


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
        return
    st.session_state.current_tile = current
    st.session_state.rotation = 0
    reset_selection()


def ensure_game():
    if "board" not in st.session_state:
        start_game(2)
    if "selected_coord" not in st.session_state:
        reset_selection()


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
    st.session_state.place_meeple_desired = False


def rotate_selected_position():
    coord = st.session_state.get("selected_coord")
    if coord is None:
        return
    rotations = current_valid_map().get(coord, [])
    if not rotations:
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

        st.table(
            {
                "項目": [r[0] for r in rows],
                "点": [r[1] for r in rows],
                "メモ": [r[2] for r in rows],
            }
        )
        st.metric("合計", breakdown["total"])


def render_header_and_status():
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)
    st.title("🦁 どうぶつえんタイルゲーム試作版")
    st.caption("タップで場所を選び、↻で向きを変えて、最後に決定します。")

    if st.session_state.game_over:
        st.error("ゲーム終了")
    else:
        player = st.session_state.current_player
        st.markdown(
            f"<div style='padding:10px 14px; border-radius:12px; color:white; background:{PLAYER_COLORS[player]}; font-weight:700; text-align:center;'>"
            f"{PLAYER_LABELS[player]}プレイヤーの番"
            f"</div>",
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns(2)
    with col1:
        st.metric("山札", f"{len(st.session_state.deck)}枚")
    with col2:
        st.metric("プレイヤー数", st.session_state.num_players)


def render_controls():
    with st.expander("ゲーム設定とルール", expanded=False):
        default_players = st.session_state.get("num_players", 2)
        num_players = st.selectbox("プレイヤー人数", [2, 3, 4], index=max(0, default_players - 2))
        if st.button("新しいゲーム", use_container_width=True):
            start_game(num_players)
            st.rerun()

        st.markdown(
            """
- 置ける場所だけ青い枠で表示されます
- まず場所をタップすると、その場所で置ける向きに自動で切り替わります
- ↻でその場所で置ける向きだけ順番に回ります
- ✔︎ 決定で確定、✖ やりなおしで場所選びに戻ります
- 囲い完成時は多数決、同点トップは全員得点です
            """
        )


def render_scores():
    st.subheader("スコア")
    st.table(score_table_data())
    render_scoring_panel()


def render_current_tile_summary():
    st.subheader("現在のタイル")
    if st.session_state.current_tile is None:
        st.info("これ以上置けるタイルがありません。終了時得点を反映済みです。")
        return

    selected_tile = current_selected_tile()
    valid_map = current_valid_map()
    valid_count = len(valid_map)

    if selected_tile is None:
        st.markdown(render_tile_html(rotate_tile(st.session_state.current_tile, 0), size=92), unsafe_allow_html=True)
        st.markdown(f"<div class='tile-meta'>置ける場所: {valid_count}か所</div>", unsafe_allow_html=True)
        return

    st.markdown(
        render_tile_html(
            selected_tile,
            size=92,
            selected=True,
            show_rotate_hint=len(valid_map.get(st.session_state.selected_coord, [])) > 1,
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='tile-meta'>選択中: {coord_to_text(st.session_state.selected_coord)} / 向き {st.session_state.selected_rotation * 90}°</div>",
        unsafe_allow_html=True,
    )


def render_board_section():
    st.subheader("盤面")
    if st.session_state.current_tile is None:
        valid_map = {}
    else:
        valid_map = current_valid_map()
    valid_coords = set(valid_map.keys())

    min_x, max_x, min_y, max_y = board_bounds(st.session_state.board)
    all_coords = set(st.session_state.board.keys()) | valid_coords
    if all_coords:
        xs = [c[0] for c in all_coords]
        ys = [c[1] for c in all_coords]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
    padding = 1
    min_x -= padding
    max_x += padding
    min_y -= padding
    max_y += padding

    st.markdown("<div class='small-note'>青い枠だけタップできます。</div>", unsafe_allow_html=True)

    for y in range(min_y, max_y + 1):
        cols = st.columns(max_x - min_x + 1, gap="small")
        for idx, x in enumerate(range(min_x, max_x + 1)):
            coord = (x, y)
            with cols[idx]:
                if coord in st.session_state.board:
                    cell = st.session_state.board[coord]
                    st.markdown(render_tile_html(cell["tile"], cell.get("meeple"), size=54), unsafe_allow_html=True)
                elif coord == st.session_state.get("selected_coord"):
                    rotations = valid_map.get(coord, [])
                    tile = current_selected_tile()
                    if tile is not None:
                        st.markdown(
                            render_tile_html(
                                tile,
                                size=54,
                                selected=True,
                                show_rotate_hint=len(rotations) > 1,
                            ),
                            unsafe_allow_html=True,
                        )
                        if len(rotations) > 1:
                            if st.button("↻", key=f"rotate_{x}_{y}", use_container_width=True):
                                rotate_selected_position()
                                st.rerun()
                        else:
                            st.caption("固定")
                elif coord in valid_coords:
                    if st.button("＋", key=f"select_{x}_{y}", use_container_width=True):
                        select_position(coord)
                        st.rerun()
                    st.markdown(render_empty_slot_html(size=54, active=True), unsafe_allow_html=True)
                else:
                    st.markdown("<div style='height:76px;'></div>", unsafe_allow_html=True)
                st.caption(f"{x},{y}")
        st.markdown("<div class='board-row-gap'></div>", unsafe_allow_html=True)


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
        place_meeple=bool(st.session_state.get("place_meeple_desired", False)),
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
    draw_next_tile_for_turn()


def render_selection_bar():
    if st.session_state.current_tile is None:
        return

    coord = st.session_state.get("selected_coord")
    allowed = current_selected_meeple_allowed() if coord is not None else False
    if not allowed:
        st.session_state.place_meeple_desired = False

    st.markdown("<div class='selection-bar'>", unsafe_allow_html=True)
    if coord is None:
        st.markdown(
            "<div class='selection-card'>まず、青い枠の場所をタップしてください。</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div class='selection-card'>選択中: {coord_to_text(coord)} / 向き {st.session_state.selected_rotation * 90}°</div>",
            unsafe_allow_html=True,
        )
        st.toggle(
            "この囲いにミープルを置く",
            key="place_meeple_desired",
            disabled=not allowed,
            help="すでに誰かのミープルがつながっている囲いには置けません。",
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


def render_log_section():
    st.subheader("ログ")
    if not st.session_state.log:
        st.info("まだログはありません。")
        return
    for entry in st.session_state.log[:12]:
        st.markdown(f"<div class='log-card'>• {entry}</div>", unsafe_allow_html=True)


def main():
    ensure_game()
    render_header_and_status()
    render_controls()
    render_scores()
    render_current_tile_summary()
    render_board_section()
    render_selection_bar()
    render_log_section()

    if st.session_state.game_over:
        max_score = max(st.session_state.scores)
        winners = [PLAYER_LABELS[i] for i, score in enumerate(st.session_state.scores) if score == max_score]
        st.success(f"勝者: {' / '.join(winners)}（{max_score}点）")


if __name__ == "__main__":
    main()
