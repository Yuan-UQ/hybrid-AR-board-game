"""
Xiangqi Arena — main game loop.

Player-facing interaction is reduced to exactly TWO phases per turn:

  MOVEMENT  : click a piece, then click a green node  (Enter = skip)
  ATTACK    : click a HumanSide target                       (Enter = skip)

The other three phases (START, RECOGNITION, RESOLVE) are processed
automatically on the same frame they are enteHumanSide — players never see a
"Press Enter to continue" prompt for them.

Controls
--------
  Mouse click on board  : select piece / choose destination or attack target
  Enter                 : skip the current action (move or attack)
  Space                 : 悔棋 — 对方回合开始后仍可回到上一方完整回合行动前
  Escape                : cancel current selection (or quit on game-over)
"""

from __future__ import annotations

import argparse
import copy
import sys
import os

# Allow `python xiangqi_arena/main.py` to work from the project root.
# When run as a script the package root is not on sys.path; add it here.
if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame

# ---------------------------------------------------------------------------
# Game-logic imports
# ---------------------------------------------------------------------------
from xiangqi_arena.core.enums import EventPointType, Faction, Phase, PieceType, VictoryState
from xiangqi_arena.core.utils import is_within_board
from xiangqi_arena.flow.phase import advance_phase
from xiangqi_arena.flow.round import should_spawn_event_point
from xiangqi_arena.flow.turn import can_select_piece, end_turn, start_turn
from xiangqi_arena.modification.attack import (
    apply_attack, apply_wizard_attack, apply_skip_attack,
)
from xiangqi_arena.modification.event import apply_event_trigger, spawn_event_point
from xiangqi_arena.modification.move import apply_move, apply_skip_move
from xiangqi_arena.rules.event_rules import get_all_triggers
from xiangqi_arena.rules.piece_rules import legal_attack_targets, legal_moves
from xiangqi_arena.rules.victory_rules import check_victory
from xiangqi_arena.recognition.aruco_tracker import VisionFrame, VisionTracker
from xiangqi_arena.state.game_state import GameState, build_default_state

# ---------------------------------------------------------------------------
# UI / input imports
# ---------------------------------------------------------------------------
from xiangqi_arena.input_control.keyboard_handler import KeyAction, classify_key
from xiangqi_arena.input_control.selection_handler import (
    SelectionState, pixel_to_node,
)
from xiangqi_arena.ui import display_config
from xiangqi_arena.ui.board_renderer import draw_board, draw_global_background, invalidate_board_image_cache
from xiangqi_arena.ui.death_marker_renderer import draw_dead_pieces
from xiangqi_arena.ui.piece_renderer import invalidate_layout_caches
from xiangqi_arena.ui.event_renderer import (
    draw_event_points,
    draw_heal_effect_overlays,
    draw_pending_heal_effect,
    is_pending_heal_effect_finished,
    make_pending_heal_effect,
)
from xiangqi_arena.ui.highlight_renderer import (
    draw_attack_effect_overlays,
    draw_attack_target_arrows,
    draw_highlights,
    draw_selected_arrow,
)
import xiangqi_arena.ui.others as ui_others
from xiangqi_arena.ui.others import (
    BUTTON_RECT, DRAW_RECT, SURRENDER_RECT,
    draw_kill_dialog, draw_panel, draw_top_bar, draw_victory_overlay,
    reset_panel_fonts, sync_button_rects_from_config,
    LOG_EXPAND_RECT, LOG_MODAL_CLOSE_RECT, LOG_MODAL_SCROLLBAR_RECT, LOG_MODAL_THUMB_RECT,
)
from xiangqi_arena.ui.piece_renderer import (
    draw_attack_hit_effects,
    draw_pieces,
    has_death_animation_finished,
    is_death_animation_active,
    trigger_attack_animation,
)
from xiangqi_arena.ui.ranged_attack_renderer import (
    draw_ranged_attack,
    is_ranged_attack_finished,
    is_ranged_attacker,
    make_pending_ranged_attack,
)
from xiangqi_arena.ui.retract_animation import (
    RetractAnim,
    draw_retracts,
    make_retract,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LOG_MAX = 15   # side panel uses only the latest few anyway
LOG_HISTORY_MAX = 2000
WALK_ANIM_MS = 1500
VICTORY_OVERLAY_DELAY_MS = 500

# A queued kill is considered "physically removed" once the dead piece's
# marker has been absent from the camera for this many *consecutive vision
# updates*. ~6 ticks at the default vision_sync_ms (~80ms each) is roughly
# half a second of stable absence — short enough to feel responsive, long
# enough to absorb single-frame ArUco dropouts.
_KILL_REMOVED_STABLE_TICKS = 6

# After a death is recorded, hold the "remove fallen piece" modal closed this
# long (ms) while still blocking turn / vision commit — lets hit effects settle.
KILL_DIALOG_DELAY_MS = 1500

# Once the kill modal is visible, do not dismiss it (even if markers read as
# gone) until this many ms have elapsed — keeps the prompt readable.
KILL_MODAL_MIN_VISIBLE_MS = 3000


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Xiangqi Arena UI")
    vision_group = parser.add_mutually_exclusive_group()
    vision_group.add_argument(
        "--vision",
        dest="vision",
        action="store_true",
        help="使用摄像头识别的实际棋子位置（默认开启）",
    )
    vision_group.add_argument(
        "--no-vision",
        dest="vision",
        action="store_false",
        help="关闭摄像头识别，使用预设棋子位置",
    )
    parser.set_defaults(vision=True)
    parser.add_argument("--source", default="1", help="Camera index or stream URL")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument(
        "--no-line-snap",
        action="store_true",
        help="关闭检测棋盘线吸附，仅用四角插值网格",
    )
    parser.add_argument("--snap-radius", type=int, default=22)
    parser.add_argument("--warp-width", type=int, default=900)
    parser.add_argument("--warp-height", type=int, default=1000)
    parser.add_argument("--warp-quad-expand", type=float, default=0.0)
    parser.add_argument("--piece-off-fwd", type=float, default=0.0)
    parser.add_argument("--piece-off-side", type=float, default=0.0)
    parser.add_argument("--piece-cell-mult", type=float, default=None)
    parser.add_argument("--aruco-strict", action="store_true")
    parser.add_argument(
        "--vision-debug",
        dest="vision_debug",
        action="store_true",
        help="显示 OpenCV 调试窗口（默认开启）",
    )
    parser.add_argument(
        "--no-vision-debug",
        dest="vision_debug",
        action="store_false",
        help="关闭 OpenCV 调试窗口",
    )
    parser.set_defaults(vision_debug=True)
    parser.add_argument(
        "--vision-flip-y",
        action="store_true",
        help="如果实体棋盘左右方向与 UI 相反，翻转游戏 y 坐标",
    )
    parser.add_argument(
        "--vision-sync-ms",
        type=int,
        default=100,
        help="摄像头位置同步间隔，毫秒",
    )
    parser.add_argument(
        "--vision-warmup-frames",
        type=int,
        default=90,
        help="启动时最多读取多少帧来获得初始实际位置",
    )
    parser.add_argument(
        "--vision-ready-pieces",
        type=int,
        default=14,
        help="启动预热期间等待稳定识别到的棋子数量",
    )
    return parser.parse_args()


def _piece_at(state: GameState, pos: tuple) -> str | None:
    return state.board._occupancy.get(pos)


def _is_game_over(state: GameState) -> bool:
    return state.victory_state != VictoryState.ONGOING


def _setup_status_from_vision(
    state: GameState,
    vision_status: VisionFrame | None,
    *,
    camera_connected: bool,
    vision_enabled: bool,
) -> dict:
    """Build setup-readiness UI state from the existing camera tracker output."""
    positions = vision_status.positions if vision_status is not None else {}
    board_detected = bool(vision_status.board_ok) if vision_status is not None else False

    if not vision_enabled:
        camera_connected = True
        board_detected = True
        positions = {pid: piece.pos for pid, piece in state.pieces.items()}

    pieces: dict[str, dict] = {}
    for pid, piece in state.pieces.items():
        detected_pos = positions.get(pid)
        detected = detected_pos is not None
        pieces[pid] = {
            "detected": detected,
            "correct": bool(detected and tuple(detected_pos) == tuple(piece.pos)),
            "expected_pos": tuple(piece.pos),
            "detected_pos": tuple(detected_pos) if detected_pos is not None else None,
        }

    ready = (
        camera_connected
        and board_detected
        and bool(pieces)
        and all(info["detected"] for info in pieces.values())
        and all(info["correct"] for info in pieces.values())
    )
    return {
        "camera_connected": camera_connected,
        "board_detected": board_detected,
        "pieces": pieces,
        "ready": ready,
    }


def _setup_ready(setup_status: dict) -> bool:
    return bool(setup_status.get("ready", False))


def _inactive_setup_piece_ids(setup_status: dict | None) -> set[str]:
    if setup_status is None:
        return set()
    return {
        pid
        for pid, info in setup_status.get("pieces", {}).items()
        if not bool(info.get("detected", False))
    }


def _enter_game_from_setup(
    state: GameState,
    sel: SelectionState,
    log: list[str],
    log_history: list[str],
    game_over_ref: list[bool],
    pending_event_ref: list[dict | None],
    undo_snapshot_ref: list[GameState | None],
    turn_start_snapshot_ref: list[GameState | None],
    last_undo_capture_key_ref: list[tuple[int, Faction] | None],
    death_history_cursor_ref: list[int],
) -> bool:
    start_turn(state)
    _drain_auto_phases(
        state,
        sel,
        log,
        log_history,
        game_over_ref,
        pending_event_ref,
        undo_snapshot_ref=undo_snapshot_ref,
        turn_start_snapshot_ref=turn_start_snapshot_ref,
    )
    _maybe_capture_turn_start_snapshot(state, last_undo_capture_key_ref, turn_start_snapshot_ref)
    death_history_cursor_ref[0] = len(state.history)
    faction = "HUMANSIDE" if state.active_faction == Faction.HumanSide else "ORCSIDE"
    _push(log, f"Round {state.round_number} - {faction}'s turn", history=log_history)
    return game_over_ref[0]


def _sync_state_to_vision(
    state: GameState,
    positions: dict[str, tuple[int, int]],
    sel: SelectionState,
    pending_retracts: list[RetractAnim] | None = None,
) -> list[str]:
    """Write stable camera positions into GameState without recording a turn move."""
    if not positions:
        return []

    messages: list[str] = []
    duplicate_targets: set[tuple[int, int]] = set()
    seen_targets: dict[tuple[int, int], str] = {}
    valid_updates: dict[str, tuple[int, int]] = {}

    for pid, pos in positions.items():
        piece = state.pieces.get(pid)
        if piece is None:
            messages.append(f"Vision ignored unknown piece: {pid}")
            continue
        if piece.is_dead:
            continue
        if not is_within_board(*pos):
            messages.append(f"Vision ignored out-of-board {pid}: {pos}")
            continue

        previous = seen_targets.get(pos)
        if previous is not None:
            duplicate_targets.add(pos)
            messages.append(f"Vision overlap: {previous} / {pid} at {pos}")
            continue

        seen_targets[pos] = pid
        valid_updates[pid] = pos

    for pos in duplicate_targets:
        duplicate_pid = seen_targets.get(pos)
        if duplicate_pid is not None:
            valid_updates.pop(duplicate_pid, None)

    if not valid_updates:
        return messages

    changed: list[str] = []
    for pid, pos in sorted(valid_updates.items()):
        piece = state.pieces[pid]
        target = tuple(pos)

        # During MOVEMENT, the currently selected piece is driven by the
        # vision-commit pipeline (_resolve_vision_action). Auto-syncing here
        # would leak the in-progress physical position into the game state
        # before legality is decided, breaking the illegal-retract flow.
        if (
            state.current_phase is Phase.MOVEMENT
            and sel.has_selection
            and pid == sel.selected_pid
        ):
            continue

        unseen_blocker: str | None = None
        for other in state.pieces.values():
            if other.is_dead or other.id == pid:
                continue
            if tuple(other.pos) != target:
                continue
            if other.id not in positions:
                unseen_blocker = other.id
                break

        if unseen_blocker is not None:
            messages.append(
                f"Vision rejected {pid} @ {target}: unseen {unseen_blocker} occupies cell "
                "(e.g. face-down marker)"
            )
            continue

        # MOVEMENT: only the flip-selected active piece may change cell via vision
        # until _resolve_vision_action commits. Everyone else (including inactive
        # faction during the opponent's turn) must not drift from the camera or
        # the turn / move_completed bookkeeping breaks.
        if state.current_phase is Phase.MOVEMENT:
            old_gate = tuple(piece.pos)
            if old_gate != target:
                wrong_turn = piece.faction is not state.active_faction
                if pending_retracts is not None:
                    now_ms = pygame.time.get_ticks()
                    if not any(
                        r.piece_id == pid and not r.is_finished(now_ms)
                        for r in pending_retracts
                    ):
                        _push_retract(
                            pending_retracts,
                            pid,
                            piece.faction,
                            target,
                            old_gate,
                        )
                        if wrong_turn:
                            messages.append(
                                "当前为对方回合，请勿移动该棋子。"
                                f"请将 {pid} 放回 {old_gate}。"
                            )
                        else:
                            messages.append(
                                "请先翻面选中再走子；未选中的己方棋子请勿拖动。"
                                f"请将 {pid} 放回 {old_gate}。"
                            )
                continue

        old = tuple(piece.pos)
        if old != target:
            changed.append(f"{pid} -> {target}")
        piece.pos = target

    rebuilt: dict[tuple[int, int], str] = {}
    for p in state.pieces.values():
        if p.is_dead:
            continue
        kt = tuple(p.pos)
        prev = rebuilt.get(kt)
        if prev is not None and prev != p.id:
            messages.append(
                f"Vision occupancy clash after sync: {prev} / {p.id} @ {kt}"
            )
        rebuilt[kt] = p.id
    state.board._occupancy = rebuilt

    if sel.has_selection and sel.selected_pid in state.pieces:
        selected = state.pieces[sel.selected_pid]
        if selected.is_dead:
            sel.deselect()
        elif state.current_phase == Phase.MOVEMENT:
            # Single-action turn: MOVEMENT behaves as ACTION — refresh both moves and
            # attack targets whenever vision updates mid-selection (_resolve_vision_selection
            # returns early when already selected). Preserve from_pos across refresh.
            sel.select(
                selected.id,
                selected.pos,
                moves=legal_moves(selected, state),
                attacks=legal_attack_targets(selected, state),
                from_pos=sel.from_pos if sel.from_pos is not None else selected.pos,
            )
        elif state.current_phase == Phase.ATTACK:
            sel.select(
                selected.id,
                selected.pos,
                moves=[],
                attacks=legal_attack_targets(selected, state),
                from_pos=sel.from_pos if sel.from_pos is not None else selected.pos,
            )
        else:
            sel.selected_pos = selected.pos

    messages.extend(f"Vision sync: {item}" for item in changed)
    return messages


def _resolve_vision_selection(
    state: GameState,
    sel: SelectionState,
    vision_status: VisionFrame,
    flip_cancel_streak_ref: list[dict] | None = None,
) -> list[str]:
    """
    Drive `SelectionState` from the back-side selection marker (ID=4).

    Behaviour (Rulebook addendum: physical-flip selection):
      - Only valid during the MOVEMENT (action) phase.
      - Active faction filter: only flipped pieces belonging to the side whose
        turn it is can become "selected".
      - >1 active-faction candidate -> illegal, do not change selection.
      - Exactly 1 candidate -> select it (populates valid moves/attacks).
      - 0 candidates AND the currently-selected piece is now visible again
        (player flipped it back) -> deselect.
    """
    if state.current_phase is not Phase.MOVEMENT:
        return []

    # Face-up markers actually detected *this frame* (not ``positions.keys()``,
    # which can retain stale entries from last-frame tracking while flipped).
    front_this: frozenset[str] = vision_status.front_piece_ids_this_frame
    selection_cells = vision_status.selection_cells or ()

    candidates: list[str] = []
    for cell in selection_cells:
        cell_t = (int(cell[0]), int(cell[1]))
        for pid, piece in state.pieces.items():
            if piece.is_dead:
                continue
            if piece.faction is not state.active_faction:
                continue
            if pid in front_this:
                continue
            if tuple(piece.pos) == cell_t:
                if pid not in candidates:
                    candidates.append(pid)
                break

    if len(candidates) > 1:
        if flip_cancel_streak_ref is not None:
            flip_cancel_streak_ref[0] = {}
        return ["Illegal: multiple flipped pieces detected; flip only one."]

    if len(candidates) == 1:
        pid = candidates[0]
        if sel.selected_pid == pid:
            return []
        if not can_select_piece(state, pid):
            return []
        piece = state.pieces[pid]
        if flip_cancel_streak_ref is not None:
            flip_cancel_streak_ref[0] = {}
        sel.select(
            pid,
            piece.pos,
            moves=legal_moves(piece, state),
            attacks=legal_attack_targets(piece, state),
            from_pos=piece.pos,
        )
        return [f"Vision selected {pid}"]

    if sel.has_selection and sel.selected_pid in front_this:
        # Only treat "face-up marker back at the original cell" as a true cancel.
        # When the piece reappears at a DIFFERENT cell the player just
        # finished a physical move attempt — that case is owned by
        # `_resolve_vision_action`, which decides commit vs illegal-retract.
        # Use _vision_piece_cell (raw-first), not positions.get: overlap pruning
        # can leave positions stale at from_pos while the marker has moved,
        # which would wrongly deselect and then _sync_state_to_vision would
        # treat the in-flight piece as unauthorized drift.
        visible_pos = _vision_piece_cell(vision_status, sel.selected_pid)
        from_pos = sel.from_pos if sel.from_pos is not None else state.pieces[sel.selected_pid].pos
        if visible_pos is None:
            if flip_cancel_streak_ref is not None:
                flip_cancel_streak_ref[0] = {}
            return []
        if tuple(visible_pos) != tuple(from_pos):
            # Mid-move: face-up at a new cell — never treat as flip-back cancel.
            if flip_cancel_streak_ref is not None:
                flip_cancel_streak_ref[0] = {}
            return []
        # Stable face-up at origin: require several consecutive frames so a
        # brief ArUco/raw glitch cannot deselect mid-move on the next sync tick.
        if flip_cancel_streak_ref is not None:
            key = ("flip_cancel", sel.selected_pid)
            prev = flip_cancel_streak_ref[0]
            cnt = (prev.get("count", 0) + 1) if prev.get("key") == key else 1
            flip_cancel_streak_ref[0] = {"key": key, "count": cnt}
            if cnt < _FLIP_CANCEL_STABLE_TICKS:
                return []
            flip_cancel_streak_ref[0] = {}
        sel.deselect()
        return ["Vision deselected (piece flipped back)"]

    if flip_cancel_streak_ref is not None:
        flip_cancel_streak_ref[0] = {}

    return []


# ---------------------------------------------------------------------------
# Vision-driven action commit (move / attack / illegal retract)
# ---------------------------------------------------------------------------

# Number of consecutive vision ticks a proposed action must persist before
# the system commits it. Suppresses single-frame ArUco glitches.
_ACTION_STABLE_TICKS = 2

# Face-up back at from_pos before we clear selection (flip-back cancel).
_FLIP_CANCEL_STABLE_TICKS = 4


def _select_marker_on_cell(
    select_cells: set[tuple[int, int]],
    cell: tuple[int, int],
) -> bool:
    """True if a back-side SELECT (ID=4) cell snap matches *cell*."""
    ct = (int(cell[0]), int(cell[1]))
    return any((int(c[0]), int(c[1])) == ct for c in select_cells)


def _vision_piece_cell(vision_status: VisionFrame, pid: str) -> tuple[int, int] | None:
    """
    Best-effort camera cell for *pid*.

    Prefer ``raw_piece_positions`` (no overlap pruning) so a piece that
    temporarily disappears from ``positions`` during a physical move
    still reports its tracked cell for ``_resolve_vision_action``.
    """
    raw = {p: (x, y) for p, x, y in vision_status.raw_piece_positions}
    return raw.get(pid) or vision_status.positions.get(pid)


def _resolve_vision_action(
    state: GameState,
    sel: SelectionState,
    vision_status: VisionFrame,
    pending_attack_ref: list[dict | None],
    pending_attack_commit_ref: list[dict | None],
    pending_retracts: list,
    action_streak_ref: list[dict],
) -> list[str]:
    """
    Drive move / attack commits and illegal-move retracts from the camera.

    State machine (called every vision tick after _sync_state_to_vision):

    * No selection                           -> no-op (selection done elsewhere)
    * Animated ranged attack pending         -> no-op (wait for projectile)
    * Retract animation in flight            -> no-op (let player settle piece)
    * SELECT marker on a `valid_attacks` cell -> set pending_attack_commit_ref
        (player has stacked the attacker on the victim and flipped it)
    * pending_attack_commit_ref is set:
        - SELECT cell still seen           -> wait
        - SELECT gone, attacker visible @ from_pos -> apply_attack/ranged
        - SELECT gone, attacker visible elsewhere  -> cancel + retract
    * Otherwise (selected piece reappears at NEW cell, no SELECT visible):
        - new_pos in valid_moves           -> apply_move + advance_phase
        - new_pos == from_pos              -> handled by deselect path above
        - else                             -> retract animation, keep selection
    """
    if state.current_phase is not Phase.MOVEMENT or not sel.has_selection:
        action_streak_ref[0] = {}
        return []

    if pending_attack_ref[0] is not None:
        action_streak_ref[0] = {}
        return []

    now_ms = pygame.time.get_ticks()
    if any(not r.is_finished(now_ms) for r in pending_retracts):
        action_streak_ref[0] = {}
        return []

    pid = sel.selected_pid
    piece = state.pieces.get(pid)
    if piece is None or piece.is_dead:
        action_streak_ref[0] = {}
        return []

    from_pos = tuple(sel.from_pos if sel.from_pos is not None else piece.pos)
    visible_pos = _vision_piece_cell(vision_status, pid)
    select_cells = set(tuple(c) for c in (vision_status.selection_cells or ()))

    # ---- attack commit: attacker placed back at original cell ----
    if pending_attack_commit_ref[0] is not None:
        commit = pending_attack_commit_ref[0]
        target_v = tuple(commit["target_pos"])
        if commit.get("pid") != pid:
            pending_attack_commit_ref[0] = None
        elif target_v in select_cells:
            return []
        elif visible_pos is None:
            return []
        elif visible_pos == from_pos:
            pending_attack_commit_ref[0] = None
            action_streak_ref[0] = {}
            return _do_commit_attack(state, sel, pid, target_v, pending_attack_ref)
        else:
            pending_attack_commit_ref[0] = None
            action_streak_ref[0] = {}
            _push_retract(
                pending_retracts,
                pid,
                piece.faction,
                visible_pos,
                from_pos,
            )
            return [
                f"Cancelled attack: please return {pid} to {from_pos} and retry"
            ]

    # ---- attack pre-commit: SELECT marker on a valid attack target ----
    # Only while the attacker's front marker is still at *from_pos*. If the
    # piece has already moved toward a legal empty cell, stray SELECT snaps
    # on attack-highlight nodes must not arm attack-pre (fixes false retracts
    # e.g. OrcSide General committing a palace step).
    valid_attack_set = set(tuple(c) for c in sel.valid_attacks)
    attack_pre = None
    if (
        visible_pos is not None
        and tuple(visible_pos) == tuple(from_pos)
    ):
        attack_pre = next(
            (
                c
                for c in select_cells
                if c in valid_attack_set and c != from_pos
            ),
            None,
        )
    if attack_pre is not None:
        key = ("attack_pre", attack_pre)
        prev = action_streak_ref[0]
        cnt = (prev.get("count", 0) + 1) if prev.get("key") == key else 1
        action_streak_ref[0] = {"key": key, "count": cnt}
        if cnt < _ACTION_STABLE_TICKS:
            return []
        action_streak_ref[0] = {}
        pending_attack_commit_ref[0] = {
            "pid": pid,
            "target_pos": attack_pre,
            "started_ms": now_ms,
        }
        return [
            f"Attack ready: lift {pid} back to {from_pos} and flip face-up to confirm"
        ]

    # ---- move judging: face-up marker at a NEW cell ----
    # Do *not* require global ``not select_cells``: the camera often keeps a
    # stale SELECT snap on the origin square while the front marker has
    # already moved, which would otherwise block commits forever (logs:
    # ``selection_cells`` non-empty alongside ``vision_reported_pos``).
    # Only block when SELECT covers the *destination* cell (face-down token
    # still sitting on the target intersection).
    if (
        visible_pos is not None
        and tuple(visible_pos) != from_pos
        and not _select_marker_on_cell(select_cells, tuple(visible_pos))
    ):
        new_pos = tuple(visible_pos)
        key = ("move", new_pos)
        prev = action_streak_ref[0]
        cnt = (prev.get("count", 0) + 1) if prev.get("key") == key else 1
        action_streak_ref[0] = {"key": key, "count": cnt}
        if cnt < _ACTION_STABLE_TICKS:
            return []
        action_streak_ref[0] = {}

        live_moves = legal_moves(piece, state)
        valid_move_set = set(tuple(c) for c in live_moves)
        if new_pos in valid_move_set:
            return _do_commit_move(state, sel, pid, new_pos)

        _push_retract(
            pending_retracts,
            pid,
            piece.faction,
            new_pos,
            from_pos,
        )
        return [
            f"Illegal move: {pid} cannot move to {new_pos}; please return to {from_pos}"
        ]

    # No actionable signal this tick: keep streak alive only if SELECT
    # is still on the same target_v cell (handled above).
    action_streak_ref[0] = {}
    return []


def _do_commit_move(
    state: GameState,
    sel: SelectionState,
    pid: str,
    new_pos: tuple,
) -> list[str]:
    apply_move(pid, tuple(new_pos), state)
    sel.deselect()
    advance_phase(state)
    return [f"Vision moved {pid} -> {new_pos}"]


def _do_commit_attack(
    state: GameState,
    sel: SelectionState,
    pid: str,
    target_pos: tuple,
    pending_attack_ref: list[dict | None],
) -> list[str]:
    piece = state.pieces[pid]
    target_pos = tuple(target_pos)

    if piece.piece_type == PieceType.WIZARD:
        if is_ranged_attacker(pid):
            trigger_attack_animation(pid, target_pos, state)
            pending_attack_ref[0] = make_pending_ranged_attack(
                pid, target_pos, state, is_wizard=True
            )
            sel.deselect()
            return [f"{pid} launched at {target_pos}"]
        apply_wizard_attack(pid, target_pos, state)
    else:
        if is_ranged_attacker(pid):
            trigger_attack_animation(pid, target_pos, state)
            pending_attack_ref[0] = make_pending_ranged_attack(
                pid, target_pos, state, is_wizard=False
            )
            sel.deselect()
            return [f"{pid} launched at {target_pos}"]
        apply_attack(pid, target_pos, state)

    sel.deselect()
    advance_phase(state)
    return [f"Vision attack {pid} -> {target_pos}"]


def _push_retract(
    pending_retracts: list,
    pid: str,
    faction: Faction,
    illegal_pos: tuple,
    target_pos: tuple,
) -> None:
    now_ms = pygame.time.get_ticks()
    anim = make_retract(
        pid,
        faction,
        tuple(illegal_pos),
        tuple(target_pos),
        now_ms,
    )
    pending_retracts.append(anim)


def _promote_pending_kill_staging(
    now_ms: int,
    pending_kill_staging: list[dict],
    pending_kill_queue: list[dict],
) -> None:
    """Move staging kill entries into the visible queue once delay elapses."""
    if not pending_kill_staging:
        return
    remain: list[dict] = []
    for item in pending_kill_staging:
        if now_ms >= int(item.get("show_dialog_after_ms", 0)):
            pending_kill_queue.append(
                {k: v for k, v in item.items() if k != "show_dialog_after_ms"}
            )
        else:
            remain.append(item)
    pending_kill_staging[:] = remain


def _scan_new_deaths(
    state: GameState,
    cursor_ref: list[int],
    pending_kill_queue: list[dict],
    pending_kill_staging: list[dict],
    pending_attack_ref: list[dict | None] | None = None,
) -> None:
    """Append new ``"death"`` history entries onto the kill *staging* queue.

    Entries carry ``show_dialog_after_ms``; ``_promote_pending_kill_staging``
    moves them to ``pending_kill_queue`` after ``KILL_DIALOG_DELAY_MS``.

    Idempotent w.r.t. already-staged or already-visible pieces. When
    *pending_attack_ref* holds an in-flight ranged projectile, new deaths are
    **not** staged yet and the history cursor stops before the first such
    death so the kill modal appears only after the projectile animation
    finishes and ``apply_*`` has run.
    """
    cursor = int(cursor_ref[0])
    history = state.history
    if cursor > len(history):
        cursor = 0
    queued_ids = (
        {item["piece_id"] for item in pending_kill_queue}
        | {item["piece_id"] for item in pending_kill_staging}
    )
    new_cursor = cursor

    while new_cursor < len(history):
        entry = history[new_cursor]
        if not isinstance(entry, dict):
            new_cursor += 1
            continue
        if entry.get("type") != "death":
            new_cursor += 1
            continue

        pid = str(entry.get("piece_id", ""))
        if not pid:
            new_cursor += 1
            continue
        if pid in queued_ids:
            new_cursor += 1
            continue

        if pending_attack_ref is not None and pending_attack_ref[0] is not None:
            break

        piece = state.pieces.get(pid)
        faction = piece.faction if piece is not None else None
        pos = entry.get("pos")
        if pos is None and piece is not None:
            pos = piece.pos
        pending_kill_staging.append({
            "piece_id": pid,
            "faction": faction,
            "pos": tuple(pos) if pos is not None else None,
            "gone_streak": 0,
            "show_dialog_after_ms": int(pygame.time.get_ticks()) + KILL_DIALOG_DELAY_MS,
        })
        queued_ids.add(pid)
        new_cursor += 1

    cursor_ref[0] = new_cursor


def _tick_pending_kills(
    pending_kill_queue: list[dict],
    vision_status,
    *,
    min_close_until_ms: int | None = None,
) -> None:
    """Advance the "marker physically gone" streak per queued kill.

    Pops entries whose marker has been missing from vision for at least
    ``_KILL_REMOVED_STABLE_TICKS`` consecutive vision updates. Should be
    called once per *vision tick* (not per render frame) so the streak
    reflects vision cadence rather than display cadence.

    While *min_close_until_ms* is set and ``pygame.time.get_ticks()`` is still
    before it, entries that would otherwise dequeue stay in the queue (their
    ``gone_streak`` is clamped) so the modal stays up for at least
    ``KILL_MODAL_MIN_VISIBLE_MS`` after it first appears.
    """
    if not pending_kill_queue or vision_status is None:
        return

    now_ms = pygame.time.get_ticks()
    hold_modal = min_close_until_ms is not None and now_ms < int(min_close_until_ms)

    front_ids = set(getattr(vision_status, "front_piece_ids_this_frame", set()) or set())
    board_ok = bool(getattr(vision_status, "board_ok", False))

    # Only *front* markers count as "still on board" for removal detection.
    # ``positions`` / ``raw_piece_positions`` are derived from ``piece_last_cell``
    # which is not cleared when a marker disappears, so unioning them would
    # keep ``gone_streak`` at 0 forever (see debug log: in_raw/in_pruned true
    # after physical removal).
    survivors: list[dict] = []
    for item in pending_kill_queue:
        pid = item["piece_id"]
        if not board_ok:
            survivors.append(item)
            continue
        if pid in front_ids:
            item["gone_streak"] = 0
            survivors.append(item)
            continue
        item["gone_streak"] = int(item.get("gone_streak", 0)) + 1
        if item["gone_streak"] < _KILL_REMOVED_STABLE_TICKS:
            survivors.append(item)
        elif hold_modal:
            item["gone_streak"] = max(0, _KILL_REMOVED_STABLE_TICKS - 1)
            survivors.append(item)
    pending_kill_queue[:] = survivors


def _try_surrender(state: GameState, log: list[str], history: list[str]) -> bool:
    state.players[state.active_faction].has_surrendered = True
    state.victory_state = check_victory(state)
    faction_name = "HUMANSIDE" if state.active_faction == Faction.HumanSide else "ORCSIDE"
    _push(log, f"{faction_name} surrendered!", history=history)
    return _is_game_over(state)


def _try_draw(state: GameState, log: list[str], history: list[str]) -> bool:
    player = state.players[state.active_faction]
    opponent = state.players[state.active_faction.opponent()]

    if player.draw_requested and not opponent.draw_requested:
        _push(log, "Draw request already sent; waiting for opponent.", history=history)
        return False

    if not player.draw_requested:
        player.draw_requested = True
        if opponent.draw_requested:
            result = check_victory(state)
            if result == VictoryState.DRAW:
                state.victory_state = result
                _push(log, "Both sides agreed — DRAW!", history=history)
                return True
        faction_name = "HUMANSIDE" if state.active_faction == Faction.HumanSide else "ORCSIDE"
        _push(log, f"{faction_name} requests a draw.", history=history)
        return False

    result = check_victory(state)
    if result == VictoryState.DRAW:
        state.victory_state = result
        _push(log, "Both sides agreed — DRAW!", history=history)
        return True
    return False


def _restore_game_state_into(dst: GameState, src: GameState) -> None:
    """Copy all persisted fields from *src* into *dst* (same object identity as *dst*)."""
    dst.round_number = src.round_number
    dst.active_faction = src.active_faction
    dst.current_phase = src.current_phase
    dst.board = copy.deepcopy(src.board)
    dst.pieces = copy.deepcopy(src.pieces)
    dst.players = copy.deepcopy(src.players)
    dst.event_points = copy.deepcopy(src.event_points)
    dst.victory_state = src.victory_state
    dst.action = copy.deepcopy(src.action)
    dst.history = copy.deepcopy(src.history)


def _maybe_capture_turn_start_snapshot(
    state: GameState,
    last_key_ref: list[tuple[int, Faction] | None],
    turn_start_ref: list[GameState | None],
) -> None:
    """
    Once per (round, active_faction) while still in MOVEMENT before any move/skip,
    deep-copy the full state as the \"turn start\" baseline for undo.
    """
    if state.current_phase is not Phase.MOVEMENT:
        return
    if state.action.movement_decided():
        return
    key: tuple[int, Faction] = (state.round_number, state.active_faction)
    if last_key_ref[0] == key:
        return
    last_key_ref[0] = key
    turn_start_ref[0] = copy.deepcopy(state)


def _apply_last_turn_undo(
    state: GameState,
    sel: SelectionState,
    *,
    undo_snapshot_ref: list[GameState | None],
    turn_start_snapshot_ref: list[GameState | None],
    last_undo_key_ref: list[tuple[int, Faction] | None],
    pending_attack_ref: list[dict | None],
    pending_event_ref: list[dict | None],
    pending_attack_commit_ref: list[dict | None],
    pending_retracts: list[RetractAnim],
    pending_kill_staging: list[dict],
    pending_kill_queue: list[dict],
    kill_modal_min_close_until_ref: list[int | None],
    death_history_cursor_ref: list[int],
    victory_overlay_ref: list[dict | None],
    game_over_ref: list[bool],
    action_streak_ref: list[dict],
    flip_cancel_streak_ref: list[dict],
    log: list[str],
    log_history: list[str],
) -> bool:
    """
    Restore *state* from undo_snapshot if allowed. Returns True if applied.
    """
    if undo_snapshot_ref[0] is None:
        return False
    if pending_attack_ref[0] is not None:
        return False
    if pending_event_ref[0] is not None:
        return False
    if pending_attack_commit_ref[0] is not None:
        return False
    if pending_kill_queue or pending_kill_staging:
        return False

    snap = undo_snapshot_ref[0]
    _restore_game_state_into(state, snap)
    undo_snapshot_ref[0] = None
    turn_start_snapshot_ref[0] = copy.deepcopy(state)
    last_undo_key_ref[0] = (state.round_number, state.active_faction)
    sel.deselect()
    pending_retracts.clear()
    kill_modal_min_close_until_ref[0] = None
    death_history_cursor_ref[0] = len(state.history)
    victory_overlay_ref[0] = None
    game_over_ref[0] = False
    action_streak_ref[0] = {}
    flip_cancel_streak_ref[0] = {}
    invalidate_board_image_cache()
    invalidate_layout_caches()
    _push(log, "悔棋：已回到上一回合行动前的状态。", history=log_history)
    return True


def _wizard_aoe_display_nodes(centers: list[tuple[int, int]]) -> list[tuple[int, int]]:
    nodes: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for cx, cy in centers:
        for pos in ((cx, cy), (cx, cy + 1), (cx, cy - 1), (cx - 1, cy), (cx + 1, cy)):
            if pos in seen or not is_within_board(*pos):
                continue
            seen.add(pos)
            nodes.append(pos)
    return nodes


# ---------------------------------------------------------------------------
# Auto-phase drain
# Called every frame until we land on an interactive phase (MOVEMENT/ATTACK).
# ---------------------------------------------------------------------------

def _drain_auto_phases(
    state: GameState,
    sel: SelectionState,
    log: list[str],
    log_history: list[str],
    game_over_ref: list[bool],
    pending_event_ref: list[dict | None],
    *,
    undo_snapshot_ref: list[GameState | None] | None = None,
    turn_start_snapshot_ref: list[GameState | None] | None = None,
) -> None:
    """
    Process all non-interactive phases in a tight loop so that the player
    only ever "sees" MOVEMENT and ATTACK.

    All informational messages are pushed to *log* (newest-first).
    """
    for _ in range(10):
        phase = state.current_phase

        if phase is Phase.MOVEMENT:
            break

        if phase == Phase.START:
            if should_spawn_event_point(state):
                spawn_event_point(state)
                descs = [
                    f"{ep.event_type.value}@{ep.pos}"
                    for ep in state.event_points
                ]
                _push(log, "✦ Spawned: " + "  /  ".join(descs), history=log_history)
            advance_phase(state)   # → MOVEMENT

        elif phase == Phase.RECOGNITION:
            triggers = get_all_triggers(state)
            for pid, ep in triggers:
                if pending_event_ref[0] is None:
                    pending_event_ref[0] = {
                        "piece_id": pid,
                        "event_point": ep,
                        "queued_at": pygame.time.get_ticks(),
                        "effect_started": False,
                        "heal_effect": None,
                    }
                    _push(log, f"✦ {pid} reached {ep.event_type.value}@{ep.pos}", history=log_history)
                    return
            # Skip the ATTACK phase entirely under the single-action turn rules.
            advance_phase(state)   # → ATTACK
            advance_phase(state)   # → RESOLVE

        elif phase == Phase.RESOLVE:
            if (
                undo_snapshot_ref is not None
                and turn_start_snapshot_ref is not None
                and turn_start_snapshot_ref[0] is not None
            ):
                undo_snapshot_ref[0] = copy.deepcopy(turn_start_snapshot_ref[0])
            if _is_game_over(state):
                game_over_ref[0] = True
                break
            end_turn(state)
            sel.deselect()

        else:
            break


def _push(log: list[str], msg: str, *, history: list[str] | None = None) -> None:
    """
    Prepend *msg* to *log* (newest first).

    - `log` is the short list used by the side panel.
    - `history` (optional) keeps a longer record for the Log modal.
    """
    if not msg.strip():
        return
    log.insert(0, msg)
    while len(log) > LOG_MAX:
        log.pop()
    if history is not None:
        history.insert(0, msg)
        while len(history) > LOG_HISTORY_MAX:
            history.pop()


# ---------------------------------------------------------------------------
# Interactive phase: MOVEMENT
# ---------------------------------------------------------------------------

def _handle_movement(
    state: GameState,
    sel: SelectionState,
    confirm: bool,
    click_node: tuple | None,
    pending_attack_ref: list[dict | None],
    *,
    camera_board_input: bool = False,
) -> str:
    active = state.active_faction

    if confirm:
        return "This turn requires exactly one action: move or attack."

    # With camera/ArUco input enabled, board clicks must not select or commit
    # pieces — only physical flip / vision pipeline drives that flow.
    if camera_board_input:
        return ""

    if click_node is None:
        return ""

    if sel.has_selection:
        pid = sel.selected_pid
        piece = state.pieces.get(pid)

        # Execute MOVE (one action per turn → proceed to RECOGNITION)
        if piece and not piece.is_dead and click_node in sel.valid_moves:
            apply_move(pid, click_node, state)
            sel.deselect()
            advance_phase(state)  # MOVEMENT → RECOGNITION
            return f"Moved {pid} → {click_node}"

        # Execute ATTACK directly from the action phase (one action per turn)
        if piece and not piece.is_dead and click_node in sel.valid_attacks:
            if piece.piece_type == PieceType.WIZARD:
                if is_ranged_attacker(pid):
                    trigger_attack_animation(pid, click_node, state)
                    pending_attack_ref[0] = make_pending_ranged_attack(
                        pid, click_node, state, is_wizard=True
                    )
                    sel.deselect()
                    return f"{pid} launched at {click_node}"
                apply_wizard_attack(pid, click_node, state)
            else:
                if is_ranged_attacker(pid):
                    trigger_attack_animation(pid, click_node, state)
                    pending_attack_ref[0] = make_pending_ranged_attack(
                        pid, click_node, state, is_wizard=False
                    )
                    sel.deselect()
                    return f"{pid} launched at {click_node}"
                apply_attack(pid, click_node, state)

            sel.deselect()
            advance_phase(state)  # MOVEMENT → RECOGNITION
            return f"{pid} attacked {click_node}"

    pid = _piece_at(state, click_node)
    if pid is None:
        sel.deselect()
        return ""

    piece = state.pieces.get(pid)
    if piece is None or piece.faction != active or piece.is_dead:
        sel.deselect()
        return ""

    if not can_select_piece(state, pid):
        sel.deselect()
        return f"{pid} cannot move this turn."

    moves = legal_moves(piece, state)
    attacks = legal_attack_targets(piece, state)
    sel.select(pid, click_node, moves=moves, attacks=attacks)
    return f"Selected {pid}  ({len(moves)} moves, {len(attacks)} targets)"


# ---------------------------------------------------------------------------
# Interactive phase: ATTACK
# ---------------------------------------------------------------------------

def _handle_attack(
    state: GameState,
    sel: SelectionState,
    confirm: bool,
    click_node: tuple | None,
    pending_attack_ref: list[dict | None],
    *,
    camera_board_input: bool = False,
) -> str:
    active = state.active_faction

    if pending_attack_ref[0] is not None:
        return ""

    if camera_board_input and click_node is not None:
        return ""

    if confirm:
        apply_skip_attack(state)
        advance_phase(state)
        sel.deselect()
        return "Attack skipped."

    if click_node is None:
        return ""

    if sel.has_selection:
        pid   = sel.selected_pid
        piece = state.pieces.get(pid)

        if piece and not piece.is_dead and click_node in sel.valid_attacks:
            if piece.piece_type == PieceType.WIZARD:
                if is_ranged_attacker(pid):
                    trigger_attack_animation(pid, click_node, state)
                    pending_attack_ref[0] = make_pending_ranged_attack(
                        pid, click_node, state, is_wizard=True
                    )
                    sel.deselect()
                    return f"{pid} launched at {click_node}"
                apply_wizard_attack(pid, click_node, state)
            else:
                if is_ranged_attacker(pid):
                    trigger_attack_animation(pid, click_node, state)
                    pending_attack_ref[0] = make_pending_ranged_attack(
                        pid, click_node, state, is_wizard=False
                    )
                    sel.deselect()
                    return f"{pid} launched at {click_node}"
                apply_attack(pid, click_node, state)
            advance_phase(state)
            sel.deselect()
            return f"{pid} attacked {click_node}"

        new_pid = _piece_at(state, click_node)
        if new_pid:
            new_piece = state.pieces.get(new_pid)
            if new_piece and new_piece.faction == active and not new_piece.is_dead:
                attacks = legal_attack_targets(new_piece, state)
                sel.select(new_pid, click_node, moves=[], attacks=attacks)
                return f"Selected {new_pid}  ({len(attacks)} targets)"

        sel.deselect()
        return ""

    pid = _piece_at(state, click_node)
    if pid is None:
        return ""
    piece = state.pieces.get(pid)
    if piece is None or piece.faction != active or piece.is_dead:
        return ""

    attacks = legal_attack_targets(piece, state)
    sel.select(pid, click_node, moves=[], attacks=attacks)
    return f"Selected {pid}  ({len(attacks)} targets)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _rebuild_ui_after_window_resize(new_w: int, new_h: int) -> pygame.Surface:
    """
    Recompute layout (panels, board rect, node snap, font scale) and
    refresh caches after the user resizes the window.
    """
    display_config.apply_layout_for_window_size(new_w, new_h)
    invalidate_board_image_cache()
    invalidate_layout_caches()
    reset_panel_fonts()
    sync_button_rects_from_config()
    return pygame.display.set_mode(
        (display_config.WINDOW_W, display_config.WINDOW_H),
        pygame.RESIZABLE,
    )


def main() -> None:
    args = _parse_args()

    pygame.init()
    screen = pygame.display.set_mode(
        (display_config.WINDOW_W, display_config.WINDOW_H),
        pygame.RESIZABLE,
    )
    pygame.display.set_caption(display_config.WINDOW_TITLE)
    clock  = pygame.time.Clock()

    state: GameState = build_default_state()
    sel           = SelectionState()
    log: list[str] = []
    log_history: list[str] = []
    game_over_ref  = [False]
    pending_attack_ref: list[dict | None] = [None]
    pending_event_ref: list[dict | None] = [None]
    pending_attack_commit_ref: list[dict | None] = [None]
    pending_retracts: list[RetractAnim] = []
    pending_kill_staging: list[dict] = []
    pending_kill_queue: list[dict] = []
    kill_modal_min_close_until_ref: list[int | None] = [None]
    turn_start_snapshot_ref: list[GameState | None] = [None]
    undo_snapshot_ref: list[GameState | None] = [None]
    last_undo_capture_key_ref: list[tuple[int, Faction] | None] = [None]
    # Cursor into ``state.history``; only deaths *after* this index will be
    # enqueued. Initialised after ``start_turn`` below so any setup-time
    # bookkeeping does not produce phantom kill popups.
    death_history_cursor_ref: list[int] = [0]
    action_streak_ref: list[dict] = [{}]
    flip_cancel_streak_ref: list[dict] = [{}]
    victory_overlay_ref: list[dict | None] = [None]
    vision_tracker: VisionTracker | None = None
    vision_status: VisionFrame | None = None
    next_vision_sync_ms = 0
    next_vision_status_log_ms = 0

    if args.vision:
        try:
            vision_tracker = VisionTracker(
                source=args.source,
                width=args.width,
                height=args.height,
                use_line_snap=not args.no_line_snap,
                snap_radius=args.snap_radius,
                warp_width=args.warp_width,
                warp_height=args.warp_height,
                warp_quad_expand=args.warp_quad_expand,
                piece_off_fwd=args.piece_off_fwd,
                piece_off_side=args.piece_off_side,
                piece_cell_mult=args.piece_cell_mult,
                aruco_strict=args.aruco_strict,
                flip_y=args.vision_flip_y,
                debug=args.vision_debug,
            )
            for _ in range(max(0, int(args.vision_warmup_frames))):
                vision_status = vision_tracker.read_positions(
                    frozenset(p.id for p in state.pieces.values() if p.is_dead),
                )
                if (
                    vision_status is not None
                    and vision_status.tracked_pieces >= max(1, int(args.vision_ready_pieces))
                ):
                    break
        except Exception as exc:
            print(f"[VISION] disabled: {exc}")
            vision_tracker = None

    setup_complete = False
    game_over = game_over_ref[0]
    faction = "HUMANSIDE" if state.active_faction == Faction.HumanSide else "ORCSIDE"

    _push(log, f"Round {state.round_number} — {faction}'s turn", history=log_history)
    if args.vision and vision_tracker is not None:
        tracked = vision_status.tracked_pieces if vision_status is not None else 0
        board_txt = "board ok" if vision_status is not None and vision_status.board_ok else "waiting for board"
        _push(log, f"Vision ON: {tracked}/14 pieces, {board_txt}", history=log_history)
    elif args.vision:
        _push(log, "Vision unavailable; using default positions.", history=log_history)
    setup_status = _setup_status_from_vision(
        state,
        vision_status,
        camera_connected=vision_tracker is not None,
        vision_enabled=args.vision,
    )
    log.clear()
    log_history.clear()
    _push(log, "Setup: check camera, board, and pieces.", history=log_history)
    if args.vision and vision_tracker is None:
        _push(log, "Vision unavailable; waiting for camera.", history=log_history)

    running = True
    log_modal_open = False
    log_modal_scroll = 0
    log_modal_dragging = False
    log_modal_drag_offset_y = 0
    while running:
        # ----------------------------------------------------------------
        # Event polling
        # ----------------------------------------------------------------
        confirm              = False
        click_node: tuple | None = None
        mouse_pos            = pygame.mouse.get_pos()
        btn_hover            = BUTTON_RECT.collidepoint(mouse_pos)
        surrender_hover      = SURRENDER_RECT.collidepoint(mouse_pos)
        draw_hover           = DRAW_RECT.collidepoint(mouse_pos)

        can_action_buttons = (
            (not game_over)
            and setup_complete
            and state.current_phase is Phase.MOVEMENT
        )
        active_player = state.players[state.active_faction]
        opponent_player = state.players[state.active_faction.opponent()]

        if not can_action_buttons:
            draw_label = "Request Draw [D]"
            draw_enabled = False
        else:
            if opponent_player.draw_requested and not active_player.draw_requested:
                draw_label = "Agree Draw [D]"
                draw_enabled = True
            elif active_player.draw_requested and not opponent_player.draw_requested:
                draw_label = "Waiting…"
                draw_enabled = False
            elif active_player.draw_requested and opponent_player.draw_requested:
                draw_label = "DRAW"
                draw_enabled = False
            else:
                draw_label = "Request Draw [D]"
                draw_enabled = True

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            elif ev.type == pygame.VIDEORESIZE:
                w, h = int(ev.w), int(ev.h)
                if w > 0 and h > 0:
                    screen = _rebuild_ui_after_window_resize(w, h)
                    # keep modal scroll in range after resize
                    log_modal_scroll = 0

            elif ev.type == pygame.MOUSEWHEEL:
                if log_modal_open:
                    # Scroll log modal (positive y = up). Prefer precise_y on mac trackpads.
                    dy = getattr(ev, "precise_y", None)
                    if dy is None:
                        dy = ev.y
                    step = max(1, int(round(float(dy) * 6)))
                    log_modal_scroll = max(0, min(ui_others.LOG_MODAL_MAX_SCROLL, log_modal_scroll - step))

            elif ev.type == pygame.KEYDOWN:
                ka = classify_key(ev)
                if not setup_complete and ka == KeyAction.CONFIRM:
                    if _setup_ready(setup_status):
                        game_over = _enter_game_from_setup(
                            state,
                            sel,
                            log,
                            log_history,
                            game_over_ref,
                            pending_event_ref,
                            undo_snapshot_ref,
                            turn_start_snapshot_ref,
                            last_undo_capture_key_ref,
                            death_history_cursor_ref,
                        )
                        setup_complete = True
                    else:
                        _push(log, "Start disabled: setup is not ready.", history=log_history)
                elif ka == KeyAction.CONFIRM:
                    confirm = True
                elif ka == KeyAction.UNDO:
                    if not log_modal_open:
                        if _apply_last_turn_undo(
                            state,
                            sel,
                            undo_snapshot_ref=undo_snapshot_ref,
                            turn_start_snapshot_ref=turn_start_snapshot_ref,
                            last_undo_key_ref=last_undo_capture_key_ref,
                            pending_attack_ref=pending_attack_ref,
                            pending_event_ref=pending_event_ref,
                            pending_attack_commit_ref=pending_attack_commit_ref,
                            pending_retracts=pending_retracts,
                            pending_kill_staging=pending_kill_staging,
                            pending_kill_queue=pending_kill_queue,
                            kill_modal_min_close_until_ref=kill_modal_min_close_until_ref,
                            death_history_cursor_ref=death_history_cursor_ref,
                            victory_overlay_ref=victory_overlay_ref,
                            game_over_ref=game_over_ref,
                            action_streak_ref=action_streak_ref,
                            flip_cancel_streak_ref=flip_cancel_streak_ref,
                            log=log,
                            log_history=log_history,
                        ):
                            game_over = game_over_ref[0]
                elif ka == KeyAction.CANCEL:
                    if game_over:
                        running = False
                    else:
                        flip_cancel_streak_ref[0] = {}
                        sel.deselect()
                elif ev.key == pygame.K_ESCAPE and log_modal_open:
                    log_modal_open = False
                elif can_action_buttons and ev.key == pygame.K_s:
                    game_over = _try_surrender(state, log, log_history)
                elif can_action_buttons and ev.key == pygame.K_d:
                    game_over = _try_draw(state, log, log_history)

            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                if log_modal_open:
                    if LOG_MODAL_CLOSE_RECT.collidepoint(mx, my):
                        log_modal_open = False
                        log_modal_dragging = False
                        continue
                    if LOG_MODAL_SCROLLBAR_RECT.collidepoint(mx, my) and not LOG_MODAL_THUMB_RECT.collidepoint(mx, my):
                        # Jump thumb toward click position.
                        track_top = LOG_MODAL_SCROLLBAR_RECT.y + 2
                        track_h = LOG_MODAL_SCROLLBAR_RECT.height - 4
                        thumb_h = LOG_MODAL_THUMB_RECT.height
                        usable = max(1, track_h - thumb_h)
                        new_thumb_y = max(track_top, min(track_top + usable, my - thumb_h // 2))
                        ratio = (new_thumb_y - track_top) / usable
                        log_modal_scroll = int(round(ratio * max(1, ui_others.LOG_MODAL_MAX_SCROLL)))
                        continue
                    if LOG_MODAL_THUMB_RECT.collidepoint(mx, my):
                        log_modal_dragging = True
                        log_modal_drag_offset_y = my - LOG_MODAL_THUMB_RECT.y
                        continue
                    # Click outside controls closes modal.
                    log_modal_open = False
                    log_modal_dragging = False
                    continue
                else:
                    if LOG_EXPAND_RECT.collidepoint(mx, my):
                        log_modal_open = True
                        log_modal_scroll = 0
                        log_modal_dragging = False
                        continue
                    if not setup_complete:
                        if BUTTON_RECT.collidepoint(mx, my):
                            if _setup_ready(setup_status):
                                game_over = _enter_game_from_setup(
                                    state,
                                    sel,
                                    log,
                                    log_history,
                                    game_over_ref,
                                    pending_event_ref,
                                    undo_snapshot_ref,
                                    turn_start_snapshot_ref,
                                    last_undo_capture_key_ref,
                                    death_history_cursor_ref,
                                )
                                setup_complete = True
                            else:
                                _push(log, "Start disabled: setup is not ready.", history=log_history)
                        continue
                    # Normal in-game clicks
                    if can_action_buttons and SURRENDER_RECT.collidepoint(mx, my):
                        game_over = _try_surrender(state, log, log_history)
                    elif can_action_buttons and draw_enabled and DRAW_RECT.collidepoint(mx, my):
                        game_over = _try_draw(state, log, log_history)
                    elif BUTTON_RECT.collidepoint(mx, my):
                        confirm = True
                    else:
                        click_node = pixel_to_node(mx, my)
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                if log_modal_dragging:
                    log_modal_dragging = False

            elif ev.type == pygame.MOUSEMOTION:
                if log_modal_open and log_modal_dragging:
                    mx, my = ev.pos
                    # Map thumb position to scroll index approximately.
                    track_top = LOG_MODAL_SCROLLBAR_RECT.y + 2
                    track_h = LOG_MODAL_SCROLLBAR_RECT.height - 4
                    thumb_h = LOG_MODAL_THUMB_RECT.height
                    usable = max(1, track_h - thumb_h)
                    new_thumb_y = max(track_top, min(track_top + usable, my - log_modal_drag_offset_y))
                    ratio = (new_thumb_y - track_top) / usable
                    log_modal_scroll = int(round(ratio * max(1, ui_others.LOG_MODAL_MAX_SCROLL)))

            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (4, 5):
                # mac / some mice emit wheel as buttons
                if log_modal_open:
                    delta = 1 if ev.button == 5 else -1
                    log_modal_scroll = max(0, min(ui_others.LOG_MODAL_MAX_SCROLL, log_modal_scroll + delta * 3))

        # Snapshot before any auto-phase drain this frame (used for turn-change log).
        snap_round = state.round_number
        snap_faction = state.active_faction

        _now_kill = pygame.time.get_ticks()
        _promote_pending_kill_staging(
            _now_kill,
            pending_kill_staging,
            pending_kill_queue,
        )
        if not pending_kill_queue:
            kill_modal_min_close_until_ref[0] = None
        elif kill_modal_min_close_until_ref[0] is None:
            kill_modal_min_close_until_ref[0] = _now_kill + KILL_MODAL_MIN_VISIBLE_MS

        # A pending kill (staging or visible modal) blocks turn changes until the
        # dead piece's ArUco marker is physically removed (see
        # _tick_pending_kills). Catch any deaths produced since last frame
        # *before* the drain check so the gate is in place this frame.
        _scan_new_deaths(
            state,
            death_history_cursor_ref,
            pending_kill_queue,
            pending_kill_staging,
            pending_attack_ref,
        )

        # Drain non-interactive phases before vision so _sync_state_to_vision sees the
        # same phase the player will render this frame (avoids stale legal_moves when
        # vision ran during START/RECOGNITION while selection already existed).
        if (
            not game_over
            and setup_complete
            and pending_attack_ref[0] is None
            and pending_event_ref[0] is None
            and not pending_kill_queue
            and not pending_kill_staging
        ):
            game_over_ref[0] = game_over
            _drain_auto_phases(
                state,
                sel,
                log,
                log_history,
                game_over_ref,
                pending_event_ref,
                undo_snapshot_ref=undo_snapshot_ref,
                turn_start_snapshot_ref=turn_start_snapshot_ref,
            )
            game_over = game_over_ref[0]
        if setup_complete:
            _maybe_capture_turn_start_snapshot(state, last_undo_capture_key_ref, turn_start_snapshot_ref)

        if vision_tracker is not None and not game_over:
            now_ms = pygame.time.get_ticks()
            if now_ms >= next_vision_sync_ms:
                vision_status = vision_tracker.read_positions(
                    frozenset(p.id for p in state.pieces.values() if p.is_dead),
                )
                next_vision_sync_ms = now_ms + max(1, int(args.vision_sync_ms))
                if not setup_complete:
                    setup_status = _setup_status_from_vision(
                        state,
                        vision_status,
                        camera_connected=True,
                        vision_enabled=args.vision,
                    )
                    vision_messages = []
                else:
                    vision_messages = _sync_state_to_vision(
                        state,
                        vision_status.positions,
                        sel,
                        pending_retracts,
                    )
                # While a kill confirmation is pending (delay or modal), freeze
                # new vision-driven actions / selections.
                if setup_complete and not pending_kill_queue and not pending_kill_staging:
                    # Action runs BEFORE selection so an in-flight attack-commit
                    # / move-commit consumes the "piece visible again" signal
                    # before the selection layer would (mistakenly) interpret it
                    # as a plain cancel-via-flip-back and clear the selection.
                    vision_messages.extend(
                        _resolve_vision_action(
                            state,
                            sel,
                            vision_status,
                            pending_attack_ref,
                            pending_attack_commit_ref,
                            pending_retracts,
                            action_streak_ref,
                        )
                    )
                    vision_messages.extend(
                        _resolve_vision_selection(state, sel, vision_status, flip_cancel_streak_ref)
                    )
                vision_messages.extend(vision_status.conflicts)
                if now_ms >= next_vision_status_log_ms:
                    board_txt = "board ok" if vision_status.board_ok else "no board"
                    vision_messages.append(
                        f"Vision: {vision_status.tracked_pieces}/14 pieces, "
                        f"{vision_status.detected_markers} markers, {board_txt}"
                    )
                    next_vision_status_log_ms = now_ms + 3000
                for msg in vision_messages[:3]:
                    _push(log, msg, history=log_history)
                # Re-scan after vision-driven commits (melee attacks resolve
                # synchronously inside _resolve_vision_action), then advance
                # the "marker physically gone" streaks once per vision tick.
                _scan_new_deaths(
                    state,
                    death_history_cursor_ref,
                    pending_kill_queue,
                    pending_kill_staging,
                    pending_attack_ref,
                )
                _tick_pending_kills(
                    pending_kill_queue,
                    vision_status,
                    min_close_until_ms=kill_modal_min_close_until_ref[0],
                )

        # ----------------------------------------------------------------
        # Interactive phase handling
        # ----------------------------------------------------------------
        if not game_over and setup_complete:
            phase = state.current_phase
            now_ticks = pygame.time.get_ticks()

            if pending_attack_ref[0] is not None:
                pending_attack = pending_attack_ref[0]
                if is_ranged_attack_finished(pending_attack):
                    attacker_id = str(pending_attack["attacker_id"])
                    target_pos = pending_attack["target_pos"]
                    if pending_attack["is_wizard"]:
                        apply_wizard_attack(attacker_id, target_pos, state)
                    else:
                        apply_attack(attacker_id, target_pos, state)
                    advance_phase(state)
                    pending_attack_ref[0] = None
                    _push(log, f"{attacker_id} hit {target_pos}", history=log_history)
            elif pending_event_ref[0] is not None:
                pending_event = pending_event_ref[0]
                piece_id = str(pending_event["piece_id"])
                event_point = pending_event["event_point"]
                piece = state.pieces.get(piece_id)
                if (
                    piece is None
                    or piece.is_dead
                    or tuple(piece.pos) != tuple(event_point.pos)
                ):
                    pending_event_ref[0] = None
                elif now_ticks - int(pending_event["queued_at"]) >= WALK_ANIM_MS:
                    if event_point.event_type == EventPointType.MEDICAL:
                        if pending_event["heal_effect"] is None:
                            pending_event["heal_effect"] = make_pending_heal_effect(event_point.pos)
                        elif is_pending_heal_effect_finished(pending_event["heal_effect"]):
                            apply_event_trigger(
                                piece_id,
                                event_point,
                                state,
                                spawn_heal_effect=False,
                            )
                            _push(log, f"✦ {piece_id} → {event_point.event_type.value}!", history=log_history)
                            pending_event_ref[0] = None
                    else:
                        apply_event_trigger(piece_id, event_point, state)
                        _push(log, f"✦ {piece_id} → {event_point.event_type.value}!", history=log_history)
                        pending_event_ref[0] = None

            elif pending_kill_queue or pending_kill_staging:
                # Kill confirmation delay or modal — block mouse-driven move/attack.
                pass

            elif phase == Phase.MOVEMENT:
                msg = _handle_movement(
                    state,
                    sel,
                    confirm,
                    click_node,
                    pending_attack_ref,
                    camera_board_input=args.vision,
                )
                if msg:
                    _push(log, msg, history=log_history)

            elif phase == Phase.ATTACK:
                if sel.has_selection and not sel.valid_attacks:
                    pid   = sel.selected_pid
                    piece = state.pieces.get(pid)
                    if piece and not piece.is_dead:
                        sel.valid_attacks = legal_attack_targets(piece, state)

                msg = _handle_attack(
                    state,
                    sel,
                    confirm,
                    click_node,
                    pending_attack_ref,
                    camera_board_input=args.vision,
                )
                if msg:
                    _push(log, msg, history=log_history)

            # Re-scan after this frame's pending_attack_ref / pending_event_ref
            # finalisation (those branches above call apply_attack /
            # apply_wizard_attack / apply_event_trigger and may produce new
            # death entries that must gate the inner drain below).
            _scan_new_deaths(
                state,
                death_history_cursor_ref,
                pending_kill_queue,
                pending_kill_staging,
                pending_attack_ref,
            )

            # ── Drain any auto-phases that were triggered ────────────────
            if (
                pending_attack_ref[0] is None
                and pending_event_ref[0] is None
                and not pending_kill_queue
                and not pending_kill_staging
            ):
                game_over_ref[0] = game_over
                _drain_auto_phases(
                    state,
                    sel,
                    log,
                    log_history,
                    game_over_ref,
                    pending_event_ref,
                    undo_snapshot_ref=undo_snapshot_ref,
                    turn_start_snapshot_ref=turn_start_snapshot_ref,
                )
                game_over = game_over_ref[0]
            _maybe_capture_turn_start_snapshot(state, last_undo_capture_key_ref, turn_start_snapshot_ref)

            # If the turn changed, log the new player's turn header
            if (state.round_number != snap_round
                    or state.active_faction != snap_faction):
                new_faction = ("HUMANSIDE" if state.active_faction == Faction.HumanSide
                               else "ORCSIDE")
                _push(log, f"Round {state.round_number} — {new_faction}'s turn", history=log_history)

            if _is_game_over(state) and not game_over:
                game_over = True
                if state.victory_state == VictoryState.HumanSide_WIN:
                    losing_general_id = "GeneralOrc"
                elif state.victory_state == VictoryState.OrcSide_WIN:
                    losing_general_id = "GeneralHuman"
                else:
                    losing_general_id = None
                victory_overlay_ref[0] = {
                    "general_id": losing_general_id,
                    "delay_started_at": None,
                    "death_seen": False,
                }

        # ----------------------------------------------------------------
        # Render
        # ----------------------------------------------------------------
        draw_global_background(screen)
        draw_top_bar(screen)
        draw_board(screen)
        draw_dead_pieces(screen, state)
        draw_event_points(screen, state, draw_heal_effects=False)

        if state.current_phase in (Phase.MOVEMENT, Phase.ATTACK):
            selected_piece = state.pieces.get(sel.selected_pid) if sel.has_selection else None
            show_attack_effect = False
            visible_attacks = sel.valid_attacks
            attack_arrow_nodes = sel.valid_attacks
            attack_effect_nodes: list[tuple[int, int]] = []

            if selected_piece is not None and selected_piece.piece_type is PieceType.WIZARD:
                visible_attacks = _wizard_aoe_display_nodes(sel.valid_attacks)
                attack_arrow_nodes = sel.valid_attacks
                show_attack_effect = True
                attack_effect_nodes = visible_attacks

            if pending_attack_ref[0] is not None and pending_attack_ref[0]["is_wizard"]:
                visible_attacks = _wizard_aoe_display_nodes([pending_attack_ref[0]["target_pos"]])
                attack_arrow_nodes = [pending_attack_ref[0]["target_pos"]]
                show_attack_effect = True
                attack_effect_nodes = visible_attacks

            draw_highlights(
                screen,
                selected_pos  = sel.selected_pos,
                valid_moves   = sel.valid_moves,
                valid_attacks = visible_attacks,
                show_attack_effect=False,
                attack_arrow_nodes=attack_arrow_nodes,
                show_selected_arrow=False,
            )

        visible_piece_ids: set[str] | None = None
        if setup_complete and args.vision and vision_status is not None:
            visible_piece_ids = set(vision_status.positions.keys())
        draw_pieces(
            screen,
            state,
            visible_piece_ids=visible_piece_ids,
            inactive_piece_ids=_inactive_setup_piece_ids(setup_status) if not setup_complete else None,
        )

        # Prune finished retract animations, then draw remaining ghosts
        # over the live pieces so the slide-back overlay is visible.
        now_overlay_ms = pygame.time.get_ticks()
        if pending_retracts:
            pending_retracts[:] = [r for r in pending_retracts if not r.is_finished(now_overlay_ms)]
        draw_retracts(screen, pending_retracts)

        # Order: pieces -> retracts -> kill dialog -> victory.
        draw_kill_dialog(screen, pending_kill_queue)

        draw_ranged_attack(screen, pending_attack_ref[0])
        if state.current_phase in (Phase.MOVEMENT, Phase.ATTACK):
            if show_attack_effect:
                draw_attack_effect_overlays(screen, attack_effect_nodes)
            draw_attack_target_arrows(screen, attack_arrow_nodes)
            draw_selected_arrow(screen, sel.selected_pos)
        draw_heal_effect_overlays(screen)
        draw_pending_heal_effect(
            screen,
            pending_event_ref[0]["heal_effect"] if pending_event_ref[0] is not None else None,
        )
        draw_attack_hit_effects(screen, state)

        btn_lbl = (
            "Action required (move or attack)" if state.current_phase is Phase.MOVEMENT else "…"
        )

        if not setup_complete:
            btn_lbl = "Start Game"

        log_modal_scroll = draw_panel(
            screen, state,
            log       = (log_history if log_modal_open else log),
            btn_label = btn_lbl,
            btn_hover = btn_hover,
            surrender_hover = surrender_hover,
            surrender_enabled = can_action_buttons,
            draw_label = draw_label,
            draw_hover = draw_hover,
            draw_enabled = (can_action_buttons and draw_enabled),
            selected_pid = sel.selected_pid,
            log_modal_open = log_modal_open,
            log_modal_scroll = log_modal_scroll,
            btn_enabled=(_setup_ready(setup_status) if not setup_complete else can_action_buttons),
            setup_status=(setup_status if not setup_complete else None),
        )

        if game_over:
            overlay_state = victory_overlay_ref[0]
            if overlay_state is None:
                draw_victory_overlay(screen, state)
            else:
                general_id = overlay_state["general_id"]
                if general_id is None:
                    if overlay_state["delay_started_at"] is None:
                        overlay_state["delay_started_at"] = pygame.time.get_ticks()
                    elif pygame.time.get_ticks() - int(overlay_state["delay_started_at"]) >= VICTORY_OVERLAY_DELAY_MS:
                        draw_victory_overlay(screen, state)
                else:
                    gid = str(general_id)
                    if not bool(overlay_state.get("death_seen", False)):
                        if is_death_animation_active(gid):
                            overlay_state["death_seen"] = True
                    elif has_death_animation_finished(gid):
                        if overlay_state["delay_started_at"] is None:
                            overlay_state["delay_started_at"] = pygame.time.get_ticks()
                        elif (
                            pygame.time.get_ticks() - int(overlay_state["delay_started_at"])
                            >= VICTORY_OVERLAY_DELAY_MS
                        ):
                            draw_victory_overlay(screen, state)

        pygame.display.flip()
        clock.tick(display_config.FPS)

    if vision_tracker is not None:
        vision_tracker.close()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
