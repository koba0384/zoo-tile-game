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
    padding-bottom: 4rem;
    padding-left: 0.8rem;
    padding-right: 0.8rem;
    max-width: 900px;
}
.small-note { color: #6b7280; font-size: 0.92rem; }
.tile-scroll {
    overflow-x: auto;
    padding-bottom: 8px;
    -webkit-overflow-scrolling: touch;
}
.log-card {
    background: #f8fafc;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 10px 12px;
    margin-bottom: 8px;
    font-size: 0.95rem;
}
</style>
"""


def next_player(idx, num_players):
    return (idx + 1) % num_players


def coord_to_text(coord):
    return f"({coord[0]}, {coord[1]})"


def render_tile_html(tile, meeple=None, size=76):
    edges = tile["edges"]

    def border(edge):
        return "5px solid #111827" if edge == "fence" else "1.5px dashed #d1d5db"

    emoji = animal_to_emoji(tile.get("animal"))
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
            box-shadow:0 1px 3px rgba(0,0,0,0.08);
        ">
            <div style="font-size:{max(24, int(size*0.48))}px; line-height:1;">{emoji}</div>
            {meeple_html}
        </div>
        """
    ).strip()


def render_board_html(board):
    if not board:
        return "<p>まだ盤面がありません。</p>"

    min_x, max_x, min_y, max_y = board_bounds(board)
    padding = 1
    min_x -= padding
    max_x += padding
    min_y -= padding
    max_y += padding

    rows = []
    for y in range(min_y, max_y + 1):
        cells = []
        for x in range(min_x, max_x + 1):
            coord = (x, y)
            if coord in board:
                cell = board[coord]
                tile_html = render_tile_html(cell["tile"], cell.get("meeple"), size=52)
                cell_html = dedent(
                    f"""
                    <div style='display:flex; flex-direction:column; align-items:center; gap:3px;'>
                        {tile_html}
                        <div style='font-size:10px; color:#6b7280;'>{x},{y}</div>
                    </div>
                    """
                ).strip()
            else:
                cell_html = dedent(
                    f"""
                    <div style='display:flex; flex-direction:column; align-items:center; gap:3px;'>
                        <div style='
                            width:52px;
                            height:52px;
                            border:1px dashed #e5e7eb;
                            border-radius:10px;
                            background:#fafafa;
                            margin:auto;'>
                        </div>
                        <div style='font-size:10px; color:#d1d5db;'>{x},{y}</div>
                    </div>
                    """
                ).strip()
            cells.append(f"<div style='display:grid; place-items:center; width:60px;'>{cell_html}</div>")
        rows.append(f"<div style='display:flex; gap:4px; margin-bottom:6px;'>{''.join(cells)}</div>")

    wrapper = dedent(
        f"""
        <div class='tile-scroll'>
            {''.join(rows)}
        </div>
        """
    ).strip()
    return wrapper


def available_rotations(board, tile):
    valid = {}
    for rotation in range(4):
        rotated = rotate_tile(tile, rotation)
        valid_positions = get_valid_positions(board, rotated)
        if valid_positions:
            valid[rotation] = valid_positions
    return valid


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
        score_endgame_regions()
        return
    st.session_state.current_tile = current
    st.session_state.rotation = 0


def ensure_game():
    if "board" not in st.session_state:
        start_game(2)


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
    st.caption("iPhoneでも遊びやすい縦長レイアウト版。横スクロール盤面で試せます。")

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
    st.subheader("設定")
    default_players = st.session_state.get("num_players", 2)
    num_players = st.selectbox("プレイヤー人数", [2, 3, 4], index=max(0, default_players - 2))
    if st.button("新しいゲーム", use_container_width=True):
        start_game(num_players)
        st.rerun()

    with st.expander("ルール要約", expanded=False):
        st.markdown(
            """
- 手番ではタイルを1枚置く
- その囲いにミープルがいなければ1個置ける
- 囲い完成時は多数決
- 同点トップは全員満点
- 山札が尽きたら未完成囲いは動物点のみ
            """
        )


def render_scores():
    st.subheader("スコア")
    score_table = {
        "プレイヤー": [f"{PLAYER_LABELS[i]}プレイヤー" for i in range(st.session_state.num_players)],
        "点数": st.session_state.scores,
    }
    st.table(score_table)
    render_scoring_panel()


def render_current_tile_controls():
    st.subheader("現在のタイル")
    if st.session_state.current_tile is None:
        st.info("これ以上置けるタイルがありません。終了時得点を反映済みです。")
        return

    rotation = st.select_slider(
        "向き",
        options=[0, 1, 2, 3],
        value=st.session_state.rotation,
        format_func=lambda x: f"{x * 90}°",
        key="rotation_slider",
    )
    st.session_state.rotation = rotation
    tile = rotate_tile(st.session_state.current_tile, rotation)
    st.markdown(render_tile_html(tile, size=92), unsafe_allow_html=True)
    st.caption(tile_label(tile))

    valid_map = available_rotations(st.session_state.board, st.session_state.current_tile)
    valid_positions = valid_map.get(rotation, [])
    if not valid_positions:
        st.warning("この向きでは置ける場所がありません。向きを変えてください。")
        return

    selected_coord = st.selectbox(
        "置ける座標",
        options=valid_positions,
        format_func=coord_to_text,
        key=f"coord_select_{rotation}_{st.session_state.current_tile['id']}",
    )

    preview_board = dict(st.session_state.board)
    preview_board[selected_coord] = {"tile": tile, "meeple": None}
    temp_region = get_region(preview_board, selected_coord)
    counts, _ = region_meeples(preview_board, temp_region)
    can_meeple = len(counts) == 0

    place_meeple_flag = st.checkbox(
        "この囲いにミープルを置く",
        value=False,
        disabled=not can_meeple,
        help="すでに誰かのミープルがつながっている囲いには置けません。",
    )

    if st.button("この位置に置く", type="primary", use_container_width=True):
        info = place_tile(
            st.session_state.board,
            selected_coord,
            tile,
            player_idx=st.session_state.current_player,
            place_meeple=place_meeple_flag,
        )

        log_line = f"{PLAYER_LABELS[st.session_state.current_player]}が {coord_to_text(selected_coord)} に {tile_label(tile)} を配置"
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
        st.rerun()


def render_board_section():
    st.subheader("盤面")
    st.markdown("<div class='small-note'>左右にスクロールできます。</div>", unsafe_allow_html=True)
    st.markdown(render_board_html(st.session_state.board), unsafe_allow_html=True)


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
    render_current_tile_controls()
    render_board_section()
    render_log_section()

    if st.session_state.game_over:
        max_score = max(st.session_state.scores)
        winners = [PLAYER_LABELS[i] for i, score in enumerate(st.session_state.scores) if score == max_score]
        st.success(f"勝者: {' / '.join(winners)}（{max_score}点）")


if __name__ == "__main__":
    main()
