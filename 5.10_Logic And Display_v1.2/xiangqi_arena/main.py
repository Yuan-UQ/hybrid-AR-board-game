"""
Xiangqi Arena 鈥?main game loop.

Player-facing interaction is reduced to exactly TWO phases per turn:

  MOVEMENT  : click a piece, then click a green node  (Enter = skip)
  ATTACK    : click a HumanSide target                       (Enter = skip)

The other three phases (START, RECOGNITION, RESOLVE) are processed
automatically on the same frame they are enteHumanSide 鈥?players never see a
"Press Enter to continue" prompt for them.

Controls
--------
  Mouse click on board  : select piece / choose destination or attack target
  Enter                 : skip the current action (move or attack)
  Space                 : 鎮旀 鈥?瀵规柟鍥炲悎寮€濮嬪悗浠嶅彲鍥炲埌涓婁竴鏂瑰畬鏁村洖鍚堣鍔ㄥ墠
  Escape                : cancel current selection (or quit on game-over)
"""

from __future__ import annotations

import argparse
import copy
import sys
import os
import re

# Allow `python 鈥?xiangqi_arena/main.py` (or `python -m xiangqi_arena.main`) from any cwd.
# When run as a script the repo root (parent of the `xiangqi_arena` package dir) is not on sys.path.
if __package__ is None or __package__ == "":
    _main_dir = os.path.dirname(os.path.abspath(__file__))
    _repo_root = os.path.abspath(os.path.join(_main_dir, os.pardir))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)

import pygame

# ---------------------------------------------------------------------------
# Game-logic imports
# ---------------------------------------------------------------------------
from xiangqi_arena.core.enums import EventPointType, Faction, Phase, PieceType, VictoryState
from xiangqi_arena.core.utils import is_within_board, has_crossed_river
from xiangqi_arena.flow.phase import advance_phase
from xiangqi_arena.flow.round import should_spawn_event_point
from xiangqi_arena.flow.turn import can_select_piece, end_turn, start_turn
from xiangqi_arena.modification.attack import (
    apply_attack, apply_wizard_attack, apply_skip_attack,
)
from xiangqi_arena.modification.event import apply_event_trigger, spawn_event_point
from xiangqi_arena.modification.move import apply_move, apply_skip_move
from xiangqi_arena.modification.spatial_rule import get_soldier_bonus
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
    BUTTON_RECT, DRAW_RECT, GUIDE_RECT, SURRENDER_RECT, TUTORIAL_RECT,
    draw_kill_dialog, draw_panel, draw_top_bar, draw_victory_overlay,
    reset_panel_fonts, sync_button_rects_from_config,
    LOG_EXPAND_RECT, LOG_MODAL_CLOSE_RECT, LOG_MODAL_SCROLLBAR_RECT, LOG_MODAL_THUMB_RECT,
)
from xiangqi_arena.tutorial_mode import run_tutorial_mode
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

from PIL import Image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LOG_MAX = 15   # side panel uses only the latest few anyway
LOG_HISTORY_MAX = 2000
WALK_ANIM_MS = 1500
VICTORY_OVERLAY_DELAY_MS = 500

MENU_FONT_CANDIDATES = [
    "Cinzel",
    "Cinzel Decorative",
    "Trajan Pro",
    "Georgia",
    "Times New Roman",
]
_HOME_MENU_BG: pygame.Surface | None = None
_HOME_MENU_BG_SIZE: tuple[int, int] | None = None
_HOME_MENU_OVERLAY: pygame.Surface | None = None
_HOME_MENU_OVERLAY_SIZE: tuple[int, int] | None = None
_HOME_MENU_TITLE: pygame.Surface | None = None
_HOME_MENU_TITLE_SIZE: tuple[int, int] | None = None
_MENU_FONT_CACHE: dict[tuple[int, bool], pygame.font.Font] = {}
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
_MENU_TITLE_FONT_PATH = os.path.join(_PROJECT_ROOT, "assets", "fonts", "Cinzel-Bold.ttf")

# A queued kill is considered "physically removed" once the dead piece's
# marker has been absent from the camera for this many *consecutive vision
# updates*. ~6 ticks at the default vision_sync_ms (~80ms each) is roughly
# half a second of stable absence 鈥?short enough to feel responsive, long
# enough to absorb single-frame ArUco dropouts.
_KILL_REMOVED_STABLE_TICKS = 6

# After a death is recorded, hold the "remove fallen piece" modal closed this
# long (ms) while still blocking turn / vision commit 鈥?lets hit effects settle.
KILL_DIALOG_DELAY_MS = 1500

# Once the kill modal is visible, do not dismiss it (even if markers read as
# gone) until this many ms have elapsed 鈥?keeps the prompt readable.
KILL_MODAL_MIN_VISIBLE_MS = 3000

# Setup-only display grace: after the board has been seen once, keep the setup
# board UI active through short camera/lighting dropouts.
SETUP_BOARD_LOST_GRACE_MS = 5_000


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Xiangqi Arena UI")
    vision_group = parser.add_mutually_exclusive_group()
    vision_group.add_argument(
        "--vision",
        dest="vision",
        action="store_true",
        help="浣跨敤鎽勫儚澶磋瘑鍒殑瀹為檯妫嬪瓙浣嶇疆锛堥粯璁ゅ紑鍚級",
    )
    vision_group.add_argument(
        "--no-vision",
        dest="vision",
        action="store_false",
        help="鍏抽棴鎽勫儚澶磋瘑鍒紝浣跨敤棰勮妫嬪瓙浣嶇疆",
    )
    parser.set_defaults(vision=True)
    parser.add_argument("--source", default="1", help="Camera index or stream URL")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument(
        "--no-line-snap",
        action="store_true",
        help="Disable detected board-line snapping and use corner interpolation only.",
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
        help="鏄剧ず OpenCV 璋冭瘯绐楀彛锛堥粯璁ゅ紑鍚級",
    )
    parser.add_argument(
        "--no-vision-debug",
        dest="vision_debug",
        action="store_false",
        help="鍏抽棴 OpenCV 璋冭瘯绐楀彛",
    )
    parser.set_defaults(vision_debug=True)
    parser.add_argument(
        "--vision-flip-y",
        action="store_true",
        help="濡傛灉瀹炰綋妫嬬洏宸﹀彸鏂瑰悜涓?UI 鐩稿弽锛岀炕杞父鎴?y 鍧愭爣",
    )
    parser.add_argument(
        "--vision-sync-ms",
        type=int,
        default=100,
        help="鎽勫儚澶翠綅缃悓姝ラ棿闅旓紝姣",
    )
    parser.add_argument(
        "--vision-warmup-frames",
        type=int,
        default=90,
        help="Maximum startup frames to read while acquiring initial piece positions.",
    )
    parser.add_argument(
        "--vision-ready-pieces",
        type=int,
        default=14,
        help="鍚姩棰勭儹鏈熼棿绛夊緟绋冲畾璇嗗埆鍒扮殑妫嬪瓙鏁伴噺",
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
        "raw_board_detected": board_detected,
        "pieces": pieces,
        "ready": ready,
    }


def _apply_setup_board_display_grace(
    setup_status: dict,
    now_ms: int,
    *,
    board_seen_once_ref: list[bool],
    last_board_seen_ms_ref: list[int | None],
    board_lost_logged_ref: list[bool],
    log: list[str],
    log_history: list[str],
) -> None:
    """Stabilize Setup board display without changing raw vision readiness."""
    raw_board_detected = bool(setup_status.get("raw_board_detected", setup_status.get("board_detected", False)))

    if raw_board_detected:
        board_seen_once_ref[0] = True
        last_board_seen_ms_ref[0] = now_ms
        board_lost_logged_ref[0] = False
        setup_status["board_detected"] = True
        return

    if not board_seen_once_ref[0] or last_board_seen_ms_ref[0] is None:
        setup_status["board_detected"] = False
        return

    lost_ms = now_ms - int(last_board_seen_ms_ref[0])
    if lost_ms <= SETUP_BOARD_LOST_GRACE_MS:
        setup_status["board_detected"] = True
        return

    setup_status["board_detected"] = False
    if not board_lost_logged_ref[0]:
        _push(log, "Board lost. Please adjust.", history=log_history)
        board_lost_logged_ref[0] = True


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


def _wrong_position_setup_piece_ids(setup_status: dict | None) -> set[str]:
    """Pieces seen on camera but not at expected start cell (setup phase only)."""
    if setup_status is None:
        return set()
    return {
        pid
        for pid, info in setup_status.get("pieces", {}).items()
        if bool(info.get("detected", False)) and not bool(info.get("correct", False))
    }


def _push_setup_event_logs(
    log: list[str],
    log_history: list[str],
    setup_status: dict,
    *,
    board_logged_ref: list[bool],
    detected_piece_ids_ref: list[set[str]],
    wrong_position_ids_ref: list[set[str]],
    ready_prev_state_ref: list[bool],
) -> None:
    """Emit setup logs only when key setup milestones change."""
    pieces = setup_status.get("pieces", {})
    if bool(setup_status.get("board_detected", False)) and not board_logged_ref[0]:
        _push(log, "Setup: board detected.", history=log_history)
        board_logged_ref[0] = True

    detected_now = {
        pid
        for pid, info in pieces.items()
        if bool(info.get("detected", False))
    }
    newly_detected = sorted(detected_now - detected_piece_ids_ref[0])
    for pid in newly_detected:
        _push(log, f"Setup: detected piece {pid}.", history=log_history)
    detected_piece_ids_ref[0].update(newly_detected)

    wrong_now = _wrong_position_setup_piece_ids(setup_status)
    newly_wrong = sorted(wrong_now - wrong_position_ids_ref[0])
    for pid in newly_wrong:
        _push(log, f"Setup warning: {pid} is in the wrong position.", history=log_history)
    # Allow re-logging if a piece recovers then becomes wrong again later.
    wrong_position_ids_ref[0] = set(wrong_now)

    ready_now = bool(setup_status.get("ready", False))
    if ready_now and not ready_prev_state_ref[0]:
        _push(log, "Setup complete: all pieces detected at correct positions.", history=log_history)
    ready_prev_state_ref[0] = ready_now


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
                                f"Wrong turn: {pid} was moved to {target}. "
                                f"Return it to {old_gate}."
                            )
                        else:
                            messages.append(
                                f"Select before moving: {pid} was moved to {target}. "
                                f"Return it to {old_gate}."
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
            # Single-action turn: MOVEMENT behaves as ACTION 鈥?refresh both moves and
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
        # finished a physical move attempt 鈥?that case is owned by
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
            # Mid-move: face-up at a new cell 鈥?never treat as flip-back cancel.
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


def _get_active_flipped_candidates(state: GameState, vision_status: VisionFrame | None) -> list[str]:
    """Read-only copy of the active flipped-marker candidate detection."""
    if vision_status is None:
        return []

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
    return candidates


def _piece_rule_hint(piece, state: GameState) -> dict:
    """Return piece-specific Hint Bar copy without recalculating legal actions."""
    if piece.piece_type is PieceType.LEADER:
        return {
            "title": "General selected",
            "action_line": "Move 1 step inside your palace, or attack orthogonally. Palace defence reduces incoming damage.",
            "rule_line": "General moves 1 step inside the palace.",
            "detail_line": "Move diagonally, attack up, down, left, or right.",
            "animation_key": "leader_palace_move",
        }
    if piece.piece_type is PieceType.ARCHER:
        return {
            "title": "Archer selected",
            "action_line": "Move or attack in straight lines up to 3 nodes. Archer cannot jump over any piece.",
            "rule_line": "Archer moves and attacks orthogonally up to 3 nodes.",
            "detail_line": "Any piece on the path blocks spaces behind it.",
            "animation_key": "archer_straight_range",
        }
    if piece.piece_type is PieceType.LANCER:
        return {
            "title": "Lancer selected",
            "action_line": "Move or attack in an L-shape. If the leg cell is blocked, that direction is unavailable.",
            "rule_line": "Lancer moves and attacks in an L-shape.",
            "detail_line": "If the leg position is blocked, that L-shape direction is unavailable.",
            "animation_key": "lancer_l_shape",
        }
    if piece.piece_type is PieceType.WIZARD:
        return {
            "title": "Wizard selected",
            "action_line": "Move up to 2 nodes straight, or attack a red cross area. The center point may be empty.",
            "rule_line": "Wizard attacks a cross AOE centered exactly 3 nodes away.",
            "detail_line": "Place the marker on the red center point; enemies inside the red cross are hit.",
            "animation_key": "wizard_cross_aoe",
        }
    if piece.piece_type is PieceType.SOLDIER:
        x, y = piece.pos
        ally_bonus = get_soldier_bonus(piece, state)
        bonus_text = "Nearby ally: +1 attack." if ally_bonus else "No nearby ally bonus."
        if has_crossed_river(x, y, piece.faction):
            return {
                "title": "Soldier selected",
                "action_line": f"After crossing the river, move forward or sideways. Never backward. {bonus_text}",
                "rule_line": "After crossing the river, move forward or sideways.",
                "detail_line": "Soldier attacks forward and sideways; nearby allies give +1 attack.",
                "animation_key": "soldier_after_river",
            }
        return {
            "title": "Soldier selected",
            "action_line": f"Before crossing the river, move forward only. Attack forward or sideways. {bonus_text}",
            "rule_line": "Before crossing the river, move forward only.",
            "detail_line": "Soldier cannot move or attack backward; nearby allies give +1 attack.",
            "animation_key": "soldier_before_river",
        }
    return {
        "title": f"{piece.id} selected",
        "action_line": "Follow the highlighted legal positions for this piece.",
        "rule_line": "Follow the highlighted legal positions.",
        "detail_line": "Use the board highlights for this piece.",
        "animation_key": "move_green",
    }


def build_hint_context(
    state,
    sel,
    vision_status,
    pending_attack_ref,
    pending_attack_commit_ref,
    pending_event_ref,
    pending_retracts,
    pending_kill_queue,
    pending_kill_staging,
) -> dict:
    """Build the playing-stage Hint Bar context from existing state only."""
    if pending_kill_queue or pending_kill_staging:
        return {
            "title": "Remove fallen piece",
            "action_line": "Take the defeated physical piece off the board.",
            "rule_line": "The game continues when the marker is no longer detected.",
            "detail_line": "Do not operate other pieces before removing it.",
            "next_step_line": "Next: wait until the defeated marker disappears.",
            "severity": "error",
            "animation_key": "remove_dead_piece",
        }

    if pending_attack_commit_ref is not None:
        return {
            "title": "Attack target selected",
            "action_line": "Return the attacker to its original cell.",
            "rule_line": "Flip it face-up to confirm the attack.",
            "detail_line": "Do not move the target piece unless it is defeated.",
            "next_step_line": "Next: wait for attack resolution.",
            "severity": "warning",
            "animation_key": "attack_marker",
        }

    if pending_attack_ref is not None:
        return {
            "title": "Resolving attack",
            "action_line": "Do not move any pieces.",
            "rule_line": "The system is updating HP and damage.",
            "detail_line": "Wait until the attack result is shown.",
            "next_step_line": "Next: remove the defeated piece if HP reaches 0.",
            "severity": "warning",
            "animation_key": "attack_resolution",
        }

    if pending_event_ref is not None:
        event_point = pending_event_ref.get("event_point") if isinstance(pending_event_ref, dict) else None
        event_type = getattr(event_point, "event_type", None)
        if event_type is EventPointType.AMMUNITION:
            title = "Ammunition"
            action_line = "This piece gains permanent ATK +2."
            rule_line = "Future attacks will be stronger."
        elif event_type is EventPointType.MEDICAL:
            title = "Medical"
            action_line = "This piece recovers 1 HP."
            rule_line = "HP cannot go above the maximum."
        elif event_type is EventPointType.TRAP:
            title = "Trap"
            action_line = "This piece loses 1 HP."
            rule_line = "If HP reaches 0, remove it from the board."
        else:
            title = "Event"
            action_line = "This piece is resolving an event point."
            rule_line = "Wait for the event result."
        return {
            "title": title,
            "action_line": action_line,
            "rule_line": rule_line,
            "detail_line": "Do not move pieces during event resolution.",
            "next_step_line": "Next: wait until the event finishes.",
            "severity": "normal",
            "animation_key": "event_point",
        }

    if len(_get_active_flipped_candidates(state, vision_status)) > 1:
        return {
            "title": "Only one piece",
            "action_line": "Flip back the extra markers.",
            "rule_line": "You can only select one piece at a time.",
            "detail_line": "Keep only the piece you want to use this turn revealed.",
            "next_step_line": "Next: when only one marker remains flipped, that piece will be selected.",
            "severity": "warning",
            "animation_key": "flip_marker_warning",
        }

    if getattr(sel, "has_selection", False) and sel.selected_pid in state.pieces:
        piece = state.pieces.get(sel.selected_pid)
        rule_hint = _piece_rule_hint(piece, state)
        animation_key = rule_hint["animation_key"]
        if piece.piece_type is PieceType.LEADER and sel.valid_attacks:
            animation_key = "leader_attack"
        elif piece.piece_type is PieceType.ARCHER and sel.valid_attacks:
            animation_key = "archer_attack"
        elif piece.piece_type is PieceType.LANCER and sel.valid_attacks:
            animation_key = "lancer_attack"
        elif piece.piece_type is PieceType.WIZARD and sel.valid_attacks:
            animation_key = "wizard_attack"
        elif piece.piece_type is PieceType.SOLDIER and sel.valid_attacks:
            animation_key = "soldier_attack"
        return {
            "title": rule_hint["title"],
            "action_line": rule_hint["action_line"],
            "rule_line": rule_hint["rule_line"],
            "detail_line": rule_hint["detail_line"],
            "next_step_line": "Next: follow the green move points or red attack targets.",
            "severity": "normal",
            "animation_key": animation_key,
        }

    if not getattr(sel, "has_selection", False):
        return {
            "title": "Choose a piece",
            "action_line": "Flip one active piece from the current side.",
            "rule_line": "Only one piece can be selected at a time.",
            "detail_line": "Do not click the computer. The selected piece will glow yellow.",
            "next_step_line": "Next: after selection, green points show moves and red targets show attacks.",
            "severity": "normal",
            "animation_key": "flip_marker",
        }

    return {
        "title": "Choose a piece",
        "action_line": "Flip one active piece to reveal its marker.",
        "rule_line": "Only one piece can be selected at a time.",
        "detail_line": "Do not click the computer. The selected piece will glow yellow.",
        "next_step_line": "Next: follow the green move points or red attack targets.",
        "severity": "normal",
        "animation_key": "flip_marker",
    }


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
    select_cells = {
        (int(c[0]), int(c[1]))
        for c in (getattr(vision_status, "selection_cells", ()) or ())
    }
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
        item_pos = item.get("pos")
        if item_pos is not None and tuple(item_pos) in select_cells:
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
                _push(log, "Both sides agreed 鈥?DRAW!", history=history)
                return True
        faction_name = "HUMANSIDE" if state.active_faction == Faction.HumanSide else "ORCSIDE"
        _push(log, f"{faction_name} requests a draw.", history=history)
        return False

    result = check_victory(state)
    if result == VictoryState.DRAW:
        state.victory_state = result
        _push(log, "Both sides agreed 鈥?DRAW!", history=history)
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
    pending_attacker_return_ref: list[dict | None],
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
    if pending_attacker_return_ref[0] is not None:
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
    pending_attacker_return_ref[0] = None
    kill_modal_min_close_until_ref[0] = None
    death_history_cursor_ref[0] = len(state.history)
    victory_overlay_ref[0] = None
    game_over_ref[0] = False
    action_streak_ref[0] = {}
    flip_cancel_streak_ref[0] = {}
    invalidate_board_image_cache()
    invalidate_layout_caches()
    _push(log, "Undo: restored the previous turn state.", history=log_history)
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
                _push(log, "鉁?Spawned: " + "  /  ".join(descs), history=log_history)
            advance_phase(state)   # 鈫?MOVEMENT

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
                    _push(log, f"鉁?{pid} reached {ep.event_type.value}@{ep.pos}", history=log_history)
                    return
            # Skip the ATTACK phase entirely under the single-action turn rules.
            advance_phase(state)   # 鈫?ATTACK
            advance_phase(state)   # 鈫?RESOLVE

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


_DEDUP_LOG_KEYWORDS: tuple[str, ...] = (
    "illegal move",
    "cancelled attack",
    "wrong turn",
    "select before moving",
    "multiple flipped",
    "vision overlap",
    "vision rejected",
    "occupancy clash",
    "return to",
    "please return",
    "return attacker",
)


def _should_dedup_log_message(msg: str) -> bool:
    lower = msg.lower()
    return any(kw in lower for kw in _DEDUP_LOG_KEYWORDS)


def _push(log: list[str], msg: str, *, history: list[str] | None = None) -> None:
    """
    Prepend *msg* to *log* (newest first).

    - `log` is the short list used by the side panel.
    - `history` (optional) keeps a longer record for the Log modal.
    """
    if not msg.strip():
        return
    if _should_dedup_log_message(msg):
        if msg in log or (history is not None and msg in history):
            return
    log.insert(0, msg)
    while len(log) > LOG_MAX:
        log.pop()
    if history is not None:
        history.insert(0, msg)
        while len(history) > LOG_HISTORY_MAX:
            history.pop()


_NOTIFICATION_LOG_ERROR_KEYWORDS: tuple[str, ...] = (
    "illegal move",
    "cancelled attack",
    "wrong turn",
    "select before moving",
    "multiple flipped",
    "vision overlap",
    "overlaps",
    "out-of-board",
    "unknown piece",
    "vision rejected",
    "occupancy clash",
    "failed to read camera frame",
    "vision unavailable",
    "return to",
    "please return",
)

_MOVED_TO_RE = re.compile(r"\bwas\s+moved\s+to\s+\((\d+),\s*(\d+)\)", re.IGNORECASE)
_RETURN_TO_RE = re.compile(r"\breturn(?:\s+it)?\s+to\s+\((\d+),\s*(\d+)\)", re.IGNORECASE)
_RETURN_PIECE_RE = re.compile(
    r"\breturn\s+(?!it\b)(.+?)\s+to\s+\((\d+),\s*(\d+)\)",
    re.IGNORECASE,
)
_LEADING_PIECE_RE = re.compile(
    r"^(?:illegal move|wrong turn|select before moving):\s+(.+?)\s+(?:cannot|was)\b",
    re.IGNORECASE,
)


def _vision_current_piece_pos(
    vision_status: VisionFrame | None,
    pid: str,
) -> tuple[int, int] | None:
    if vision_status is None:
        return None
    raw = {
        piece_id: (int(x), int(y))
        for piece_id, x, y in getattr(vision_status, "raw_piece_positions", ()) or ()
    }
    if pid in raw:
        return raw[pid]
    pos = getattr(vision_status, "positions", {}).get(pid)
    if pos is None:
        return None
    return (int(pos[0]), int(pos[1]))


def _vision_front_marker_at(
    vision_status: VisionFrame | None,
    pid: str,
    pos: tuple[int, int],
) -> bool:
    """True when the piece's front marker is currently visible at *pos*."""
    if vision_status is None:
        return False
    front_ids = set(getattr(vision_status, "front_piece_ids_this_frame", set()) or set())
    if pid not in front_ids:
        return False
    return _vision_current_piece_pos(vision_status, pid) == tuple(pos)


def _try_complete_attacker_return_gate(
    state: GameState,
    pending_attacker_return_ref: list[dict | None],
    vision_status: VisionFrame | None,
) -> list[str]:
    pending = pending_attacker_return_ref[0]
    if pending is None:
        return []
    attacker_id = str(pending["attacker_id"])
    from_pos = tuple(pending["from_pos"])
    if not _vision_front_marker_at(vision_status, attacker_id, from_pos):
        return []
    pending_attacker_return_ref[0] = None
    advance_phase(state)
    return [f"Attacker returned: {attacker_id} is back at {from_pos}."]


def _return_request_from_log(
    entry: str,
) -> tuple[str | None, tuple[int, int], tuple[int, int] | None] | None:
    bad_pos: tuple[int, int] | None = None
    m_bad = _MOVED_TO_RE.search(entry)
    if m_bad:
        bad_pos = (int(m_bad.group(1)), int(m_bad.group(2)))

    m_piece = _RETURN_PIECE_RE.search(entry)
    if m_piece:
        return (
            m_piece.group(1).strip(),
            (int(m_piece.group(2)), int(m_piece.group(3))),
            bad_pos,
        )

    m_pos = _RETURN_TO_RE.search(entry)
    if not m_pos:
        return None

    pid: str | None = None
    m_lead = _LEADING_PIECE_RE.search(entry)
    if m_lead:
        pid = m_lead.group(1).strip()
    return pid, (int(m_pos.group(1)), int(m_pos.group(2))), bad_pos


def _return_request_resolved(entry: str, vision_status: VisionFrame | None) -> bool:
    request = _return_request_from_log(entry)
    if request is None:
        return False
    pid, target, bad_pos = request
    if pid is None:
        return False
    current_pos = _vision_current_piece_pos(vision_status, pid)
    if current_pos == target:
        return True
    # If the tracker has stopped reporting the bad square, remove the stale
    # notification instead of letting an old log line flash forever.
    return bad_pos is not None and current_pos is not None and current_pos != bad_pos


def _vision_live_clean_for_notification(
    vision_on: bool,
    vision_status: VisionFrame | None,
) -> bool:
    """True when live vision reports a healthy board with no active conflicts."""
    if not vision_on or vision_status is None:
        return False
    if not bool(getattr(vision_status, "board_ok", False)):
        return False
    if list(getattr(vision_status, "conflicts", ()) or ()):
        return False
    return True


def _log_line_suppressed_when_vision_clean(lower: str) -> bool:
    """
    Stale sidebar log lines from past camera issues must not keep the panel
    flashing after the live tracker has recovered.
    """
    if "vision overlap" in lower:
        return True
    if "vision rejected" in lower:
        return True
    if "vision ignored" in lower:
        return True
    if "failed to read camera frame" in lower:
        return True
    if "vision unavailable" in lower:
        return True
    if "multiple flipped" in lower:
        return True
    if "occupancy clash" in lower:
        return True
    if "outside game board" in lower or "physical cell" in lower:
        return True
    if "out-of-board" in lower:
        return True
    if " overlaps " in lower and " at (" in lower:
        return True
    return False


def _clarify_tracker_conflict_line(conflict: str) -> str:
    """Make ArUco conflict strings easier to read in the notification panel."""
    c = conflict.strip()
    low = c.lower()
    if " overlaps " in low and " at (" in low:
        return (
            "Two physical markers map to the same board square 鈥?fix overlap on the "
            f"board. ({c})"
        )
    if "outside game board" in low or "physical cell" in low:
        return (
            "A marker is detected outside the printed board grid 鈥?center the board "
            f"in frame. ({c})"
        )
    return c


def collect_playing_notification_errors(
    *,
    setup_complete: bool,
    args: argparse.Namespace,
    vision_tracker: VisionTracker | None,
    vision_status: VisionFrame | None,
    pending_kill_queue: list[dict],
    log: list[str],
) -> list[str]:
    """
    Collect human-readable issues for the playing-stage bottom-left Notification
    panel. Returns an empty list during setup or when there are no problems.
    """
    if not setup_complete:
        return []

    out: list[str] = []
    seen: set[str] = set()

    def add(msg: str) -> None:
        t = msg.strip()
        if not t or t in seen:
            return
        seen.add(t)
        out.append(t)

    vision_on = bool(getattr(args, "vision", False))
    if vision_on:
        if vision_tracker is None:
            add("Vision is enabled but the camera tracker is not running.")
        if vision_status is None:
            add("Vision is enabled but no vision frame is available.")
    if vision_on and vision_status is not None:
        if not bool(getattr(vision_status, "board_ok", True)):
            add("Vision reports the board layout is not ok.")
        for c in getattr(vision_status, "conflicts", ()) or ():
            if c:
                add(_clarify_tracker_conflict_line(str(c)))

    if pending_kill_queue:
        add("Kill confirmation dialog is pending.")

    vision_clean = _vision_live_clean_for_notification(vision_on, vision_status)
    for entry in log:
        stripped = entry.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if vision_clean and _log_line_suppressed_when_vision_clean(lower):
            continue
        if _return_request_resolved(stripped, vision_status):
            continue
        hit = False
        for kw in _NOTIFICATION_LOG_ERROR_KEYWORDS:
            if kw.isascii():
                if kw in lower:
                    hit = True
                    break
            else:
                if kw in stripped:
                    hit = True
                    break
        if hit:
            add(stripped)

    return out


def _derive_minor_warning(log_entries: list[str]) -> str | None:
    """
    Surface a recent non-blocking warning string for top-bar display.
    Uses existing logs only; does not add new detection logic.
    """
    for entry in log_entries[:6]:
        low = entry.lower()
        # Setup piece-position issue.
        if low.startswith("setup warning") and "wrong position" in low:
            return "Position Warning"
        if "not detected" in low or "missing piece" in low:
            return "Missing piece"
        if "board lost" in low or "board detected" in low and "waiting" in low:
            return "Board/camera mismatch"
        if "vision unavailable" in low or "camera" in low and ("fail" in low or "lost" in low):
            return "Camera unstable"
        if "wrong position" in low or "position warning" in low:
            return "Position Warning"
        if "camera unstable" in low or "unstable" in low:
            return "Camera unstable"
        if "offset" in low:
            return "Piece slightly offset"
    return None


# ---------------------------------------------------------------------------
# MENU
# ---------------------------------------------------------------------------
MENU_CHARACTER_FORMATIONS = (
    # side, folder, x, bottom_y, target_h, flip_x
    ("OrcSide", "General_Orc", 0.130, 0.805, 0.122, False),
    ("OrcSide", "Rider_Orc", 0.255, 0.785, 0.118, False),
    ("OrcSide", "Archer_Skeleton", 0.205, 0.720, 0.098, False),
    ("OrcSide", "Slime_Orc", 0.190, 0.875, 0.084, False),
    ("HumanSide", "General_Human", 0.870, 0.805, 0.122, True),
    ("HumanSide", "Rider_Human", 0.745, 0.785, 0.118, True),
    ("HumanSide", "Archer_Human", 0.795, 0.720, 0.098, True),
    ("HumanSide", "Wizard_Human", 0.810, 0.875, 0.092, True),
)


def _menu_font(size: int, *, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    cached = _MENU_FONT_CACHE.get(key)
    if cached is not None:
        return cached

    if os.path.exists(_MENU_TITLE_FONT_PATH):
        try:
            font = pygame.font.Font(_MENU_TITLE_FONT_PATH, size)
            _MENU_FONT_CACHE[key] = font
            return font
        except (OSError, pygame.error):
            # If the font file is corrupted/unreadable, continue to safe fallbacks.
            pass

    for name in MENU_FONT_CANDIDATES:
        font = pygame.font.SysFont(name, size, bold=bold)
        if font is not None:
            _MENU_FONT_CACHE[key] = font
            return font
    font = pygame.font.Font(None, size)
    _MENU_FONT_CACHE[key] = font
    return font


def _load_home_menu_background() -> pygame.Surface:
    global _HOME_MENU_BG, _HOME_MENU_BG_SIZE
    target_size = (display_config.WINDOW_W, display_config.WINDOW_H)
    if _HOME_MENU_BG is not None and _HOME_MENU_BG_SIZE == target_size:
        return _HOME_MENU_BG

    image_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "ArtResource",
        "Home",
        "HomeBackground.png",
    )
    base = pygame.image.load(image_path).convert()
    _HOME_MENU_BG = pygame.transform.smoothscale(base, target_size)
    _HOME_MENU_BG_SIZE = target_size
    return _HOME_MENU_BG


def _load_home_menu_title() -> pygame.Surface:
    global _HOME_MENU_TITLE, _HOME_MENU_TITLE_SIZE
    target_box = (
        max(780, int(display_config.WINDOW_W * 1.5)),
        max(250, int(display_config.WINDOW_H * 0.65)),
    )
    if _HOME_MENU_TITLE is not None and _HOME_MENU_TITLE_SIZE == target_box:
        return _HOME_MENU_TITLE

    image_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "ArtResource",
        "Home",
        "Title.png",
    )
    base = pygame.image.load(image_path).convert_alpha()
    bw, bh = base.get_size()
    box_w, box_h = target_box
    scale = min(box_w / max(1, bw), box_h / max(1, bh))
    target_size = (max(1, int(bw * scale)), max(1, int(bh * scale)))
    _HOME_MENU_TITLE = pygame.transform.smoothscale(base, target_size)
    _HOME_MENU_TITLE_SIZE = target_box
    return _HOME_MENU_TITLE


def _render_gradient_text(
    font: pygame.font.Font,
    text: str,
    top_color: tuple[int, int, int],
    bottom_color: tuple[int, int, int],
) -> pygame.Surface:
    alpha_mask = font.render(text, True, (255, 255, 255))
    w, h = alpha_mask.get_size()
    gradient = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        t = 0.0 if h <= 1 else y / (h - 1)
        color = (
            int(top_color[0] * (1 - t) + bottom_color[0] * t),
            int(top_color[1] * (1 - t) + bottom_color[1] * t),
            int(top_color[2] * (1 - t) + bottom_color[2] * t),
            255,
        )
        pygame.draw.line(gradient, color, (0, y), (w, y))
    gradient.blit(alpha_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return gradient


def _render_tracked_gradient_text(
    font: pygame.font.Font,
    text: str,
    top_color: tuple[int, int, int],
    bottom_color: tuple[int, int, int],
    tracking: int,
) -> pygame.Surface:
    glyphs: list[pygame.Surface] = []
    width = 0
    height = 0
    for ch in text:
        glyph = _render_gradient_text(font, ch, top_color, bottom_color)
        glyphs.append(glyph)
        width += glyph.get_width()
        height = max(height, glyph.get_height())
    width += max(0, len(glyphs) - 1) * tracking
    out = pygame.Surface((max(1, width), max(1, height)), pygame.SRCALPHA)
    x = 0
    for glyph in glyphs:
        out.blit(glyph, (x, 0))
        x += glyph.get_width() + tracking
    return out


def _draw_focus_overlay(screen: pygame.Surface) -> None:
    global _HOME_MENU_OVERLAY, _HOME_MENU_OVERLAY_SIZE
    target_size = (display_config.WINDOW_W, display_config.WINDOW_H)
    if _HOME_MENU_OVERLAY is None or _HOME_MENU_OVERLAY_SIZE != target_size:
        w, h = target_size
        _HOME_MENU_OVERLAY = pygame.Surface(target_size, pygame.SRCALPHA)
        cx, cy = w // 2, int(h * 0.48)
        radius_x = max(1, int(w * 0.38))
        radius_y = max(1, int(h * 0.33))
        for y in range(h):
            dy = (y - cy) / radius_y
            for x in range(w):
                dx = (x - cx) / radius_x
                dist = dx * dx + dy * dy
                alpha = int(90 + min(130, max(0.0, dist - 0.12) * 180))
                _HOME_MENU_OVERLAY.set_at((x, y), (0, 0, 0, min(190, alpha)))
        _HOME_MENU_OVERLAY_SIZE = target_size
    screen.blit(_HOME_MENU_OVERLAY, (0, 0))


def _draw_title_image(screen: pygame.Surface) -> int:
    title_img = _load_home_menu_title()
    center_x = display_config.WINDOW_W // 2
    title_x = center_x - title_img.get_width() // 2
    title_y = int(display_config.WINDOW_H * 0.06 * 0.85)
    screen.blit(title_img, (title_x, title_y))
    return title_y + title_img.get_height()


def _draw_menu_button(
    screen: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    *,
    hovered: bool,
) -> None:
    y_offset = -3 if hovered else 0
    draw_rect = rect.move(0, y_offset)

    shadow_rect = draw_rect.move(0, 7)
    pygame.draw.rect(screen, (8, 10, 16, 170), shadow_rect, border_radius=14)

    fill = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
    for y in range(draw_rect.height):
        t = 0.0 if draw_rect.height <= 1 else y / (draw_rect.height - 1)
        base = (
            int(34 * (1 - t) + 16 * t),
            int(44 * (1 - t) + 22 * t),
            int(56 * (1 - t) + 28 * t),
            250 if hovered else 236,
        )
        pygame.draw.line(fill, base, (0, y), (draw_rect.width, y))
    screen.blit(fill, draw_rect.topleft)

    pygame.draw.rect(screen, (190, 151, 78), draw_rect, width=2, border_radius=14)
    inner_rect = draw_rect.inflate(-6, -6)
    pygame.draw.rect(screen, (230, 208, 148, 80), inner_rect, width=1, border_radius=11)
    low_inner = pygame.Rect(inner_rect.x + 2, inner_rect.centery, inner_rect.width - 4, inner_rect.height // 2 - 1)
    pygame.draw.rect(screen, (22, 26, 36, 95), low_inner, border_radius=8)

    if hovered:
        glow = pygame.Surface((draw_rect.width + 30, draw_rect.height + 30), pygame.SRCALPHA)
        pygame.draw.rect(glow, (235, 196, 108, 30), glow.get_rect(), border_radius=22)
        pygame.draw.rect(glow, (255, 218, 132, 84), glow.get_rect().inflate(-8, -8), border_radius=18, width=2)
        screen.blit(glow, (draw_rect.x - 15, draw_rect.y - 15))

    # Small ornamental side accents to mimic fantasy UI frames.
    mid_y = draw_rect.centery
    pygame.draw.polygon(
        screen,
        (178, 140, 72),
        [(draw_rect.x + 10, mid_y), (draw_rect.x + 18, mid_y - 8), (draw_rect.x + 18, mid_y + 8)],
    )
    pygame.draw.polygon(
        screen,
        (178, 140, 72),
        [(draw_rect.right - 10, mid_y), (draw_rect.right - 18, mid_y - 8), (draw_rect.right - 18, mid_y + 8)],
    )

    font = _menu_font(max(31, int(37 * display_config.UI_SCALE)), bold=True)
    label = font.render(text, True, (236, 223, 198))
    screen.blit(
        label,
        (
            draw_rect.centerx - label.get_width() // 2,
            draw_rect.centery - label.get_height() // 2,
        ),
    )


def _draw_simple_button(screen, rect, text, hovered):
    color = (40, 55, 75) if hovered else (28, 39, 56)
    pygame.draw.rect(screen, color, rect, border_radius=8)
    pygame.draw.rect(screen, (160, 140, 100), rect, width=1, border_radius=8)

    font = _menu_font(26, bold=True)
    label = font.render(text, True, (230, 220, 190))

    screen.blit(
        label,
        (
            rect.centerx - label.get_width() // 2,
            rect.centery - label.get_height() // 2,
        ),
    )


def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    words = text.split(" ")
    lines = []
    current = ""

    for word in words:
        test = word if current == "" else current + " " + word

        if font.size(test)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


_GUIDE_SPRITE_CACHE: dict[tuple[str, int, bool], list[pygame.Surface]] = {}
_GUIDE_GIF_CACHE: dict[tuple[str, int], list[pygame.Surface]] = {}


def _load_gif_frames(path: str, target_height: int) -> list[pygame.Surface]:
    key = (path, target_height)
    cached = _GUIDE_GIF_CACHE.get(key)
    if cached is not None:
        return cached

    if not os.path.exists(path):
        return []

    frames: list[pygame.Surface] = []
    gif = Image.open(path)

    try:
        while True:
            frame = gif.convert("RGBA")
            w, h = frame.size
            scale = target_height / max(1, h)
            new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
            frame = frame.resize(new_size)

            mode = frame.mode
            size = frame.size
            data = frame.tobytes()
            surf = pygame.image.fromstring(data, size, mode).convert_alpha()
            frames.append(surf)

            gif.seek(gif.tell() + 1)
    except EOFError:
        pass

    _GUIDE_GIF_CACHE[key] = frames
    return frames


def _load_sprite_strip(path: str, target_height: int = 90, *, smooth: bool = True) -> list[pygame.Surface]:
    key = (path, target_height, smooth)
    cached = _GUIDE_SPRITE_CACHE.get(key)
    if cached is not None:
        return cached

    if not os.path.exists(path):
        return []

    sheet = pygame.image.load(path).convert_alpha()
    sheet_w, sheet_h = sheet.get_size()

    # Most Idle sprite sheets are horizontal strips with square-like frames.
    frame_w = sheet_h
    frame_count = max(1, sheet_w // frame_w)

    frames: list[pygame.Surface] = []
    for i in range(frame_count):
        frame = sheet.subsurface(pygame.Rect(i * frame_w, 0, frame_w, sheet_h)).copy()

        # Crop transparent padding around the character.
        bbox = frame.get_bounding_rect()
        if bbox.width > 0 and bbox.height > 0:
            frame = frame.subsurface(bbox).copy()

        scale = target_height / max(1, frame.get_height())
        target_size = (int(frame.get_width() * scale), int(frame.get_height() * scale))
        scaler = pygame.transform.smoothscale if smooth else pygame.transform.scale
        frame = scaler(frame, target_size)

        frames.append(frame)

    _GUIDE_SPRITE_CACHE[key] = frames
    return frames


def _character_idle_path(side: str, folder: str) -> str:
    base = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "ArtResource",
        "Character",
        side,
        folder,
    )

    candidates = [
        "Idle.png",
        f"{folder.split('_')[0]}-Idle.png",
        "Wizard-Idle.png",
    ]

    for filename in candidates:
        path = os.path.join(base, filename)
        if os.path.exists(path):
            return path

    return os.path.join(base, "Idle.png")


def _draw_main_menu_characters(screen: pygame.Surface) -> None:
    """Draw lower-corner faction formations on the main menu only."""
    frame_index = (pygame.time.get_ticks() // 180) % 12
    for side, folder, nx, bottom_ny, target_h_ratio, flip_x in MENU_CHARACTER_FORMATIONS:
        target_h = max(42, int(display_config.WINDOW_H * float(target_h_ratio)))
        frames = _load_sprite_strip(
            _character_idle_path(str(side), str(folder)),
            target_height=target_h,
            smooth=False,
        )
        if not frames:
            continue

        frame = frames[frame_index % len(frames)]
        if bool(flip_x):
            frame = pygame.transform.flip(frame, True, False)

        x = int(display_config.WINDOW_W * float(nx) - frame.get_width() // 2)
        y = int(display_config.WINDOW_H * float(bottom_ny) - frame.get_height())

        shadow_w = max(24, int(frame.get_width() * 0.72))
        shadow_h = max(8, int(frame.get_height() * 0.12))
        shadow = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 82), shadow.get_rect())
        screen.blit(
            shadow,
            (
                x + frame.get_width() // 2 - shadow_w // 2,
                y + frame.get_height() - shadow_h // 2,
            ),
        )
        screen.blit(frame, (x, y))


GUIDE_SECTIONS = (
    "Piece Identity",
    "Game Objective",
    "Setup Phase",
    "Core Gameplay",
    "Special Events",
    "Game Notifications",
)


def _build_game_guide_content() -> dict[str, list[dict[str, object]]]:
    return {
        "Piece Identity": [
            {
                "title": "GeneralOrc / GeneralHuman",
                "sprites": [
                    ("GeneralOrc", _character_idle_path("OrcSide", "General_Orc")),
                    ("GeneralHuman", _character_idle_path("HumanSide", "General_Human")),
                ],
                "images": [
                    ("Movement Range",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "GeneralMove.png")),
                ],
            },
            {
                "title": "ArcherSkeleton / ArcherHuman",
                "sprites": [
                    ("ArcherSkeleton", _character_idle_path("OrcSide", "Archer_Skeleton")),
                    ("ArcherHuman", _character_idle_path("HumanSide", "Archer_Human")),
                ],
                "images": [
                    ("Movement Range",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "ArcherMove.png")),
                ],
            },
            {
                "title": "RiderOrc / LancerHuman",
                "sprites": [
                    ("RiderOrc", _character_idle_path("OrcSide", "Rider_Orc")),
                    ("LancerHuman", _character_idle_path("HumanSide", "Rider_Human")),
                ],
                "images": [
                    ("Movement Range",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "LancerMove.png")),
                ],
            },
            {
                "title": "SlimeOrc / WizardHuman",
                "sprites": [
                    ("SlimeOrc", _character_idle_path("OrcSide", "Slime_Orc")),
                    ("WizardHuman", _character_idle_path("HumanSide", "Wizard_Human")),
                ],
                "images": [
                    ("Movement Range",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "WizardMove.png")),
                ],
            },
            {
                "title": "Soldiers: Orc Side / Human Side",
                "sprites": [
                    ("Soldier1Orc", _character_idle_path("OrcSide", "Soldier1_Orc")),
                    ("Soldier2Skeleton", _character_idle_path("OrcSide", "Soldier2_Skeleton")),
                    ("Soldier3Skeleton", _character_idle_path("OrcSide", "Soldier3_Skeleton")),
                    ("Soldier1Human", _character_idle_path("HumanSide", "Soldier1_Human")),
                    ("Soldier2Human", _character_idle_path("HumanSide", "Soldier2_Human")),
                    ("Soldier3Human", _character_idle_path("HumanSide", "Soldier3_Human")),
                ],
                "images": [
                    ("Movement Range",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "SoldierMove.png")),
                ],
            },
        ],

        "Game Objective": [
            {
                "title": "Win Condition",
                "text": (
                    "Two factions: OrcSide and HumanSide.\n"
                    "Defeat the enemy General to win the game.\n"
                    "Once a General falls, the battle ends immediately."
                ),
                "images": [
                    ("Orc General Defeated",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "OrcGeneralDeath.png")),
                    ("Human General Defeated",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "HumanGeneralDeath.png")),
                ],
            }
        ],

       "Setup Phase": [
            {
                "title": "Board Not Detected",
                "text": (
                    "At the beginning of the setup phase, the system first tries to detect the physical chessboard.\n"
                    "If the board is not detected, the board area is shown in black and white.\n"
                    "The player needs to adjust the camera or board position before continuing."
                ),
                "layout": "single_center_image",
                "images": [
                    ("Board Not Detected",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "BoardDetectionFail.png")),
                ],
            },
            {
                "title": "Board Detected",
                "text": (
                    "When the board is successfully detected, the board area becomes coloured.\n"
                    "This means the system has recognised the board and can continue to detect the pieces."
                ),
                "layout": "single_center_image",
                "images": [
                    ("Board Detected",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "BoardDetectionSuccess.png")),
                ],
            },
            {
                "title": "Piece Detection Process",
                "text": (
                    "After the board is detected, the system checks whether each physical piece can be recognised.\n"
                    "During this process, detected pieces are shown in colour, while undetected pieces remain black and white."
                ),
                "layout": "single_center_image",
                "images": [
                    ("Piece Detection Process",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "PieceDetection.png")),
                ],
            },
            {
                "title": "All Pieces Detected",
                "text": (
                    "All pieces are successfully recognised by the system.\n"
                    "Every piece is displayed in colour, which means detection is complete.\n"
                    "The system is now ready to check whether the pieces are placed correctly."
                ),
                "layout": "single_center_image",
                "images": [
                    ("Detected Pieces",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "PieceDetectionSuccess.png")),
                ],
            },
            {
                "title": "Incorrect Placement",
                "text": (
                    "The game can only start when all pieces are detected and placed in the correct starting positions.\n"
                    "If a piece is placed incorrectly, the system shows a wrong position warning.\n"
                    "The correct target area is highlighted so the player knows where to move the piece."
                ),
                "layout": "single_center_image",
                "images": [
                    ("Wrong Position",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "WrongPosition.png")),
                ],
            },
        ],

        "Core Gameplay": [
            {
                "title": "Selection",
                "text": (
                    "Flip the target physical piece to reveal its marker.\n"
                    "The system recognises the marker and treats this as selecting that piece.\n"
                    "After selection, the digital board highlights the available actions for that piece."
                ),
                "layout": "gif_pair",
                "gifs": [
                    ("Physical Selection", os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "ArtResource", "Tutorial", "Selection1.gif")),
                    ("Digital Selection", os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "ArtResource", "Tutorial", "Selection.gif")),
                ],
            },
            {
                "title": "Movement",
                "text": (
                    "Flip the selected physical piece and move it to the target position.\n"
                    "After the system recognises the new position, the digital character moves to the same location.\n"
                    "This connects the physical board action with the on-screen game state."
                ),
                "layout": "gif_pair",
                "gifs": [
                    ("Physical Movement", os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "ArtResource", "Tutorial", "Movement1.gif")),
                    ("Digital Movement", os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "ArtResource", "Tutorial", "Movement.gif")),
                ],
            },
            {
                "title": "Attack",
                "text": (
                    "Flip the attacking piece and place it near the centre of the target attack area.\n"
                    "Then flip it back after the attack position is recognised.\n"
                    "The system resolves the attack and updates the digital board."
                ),
                "layout": "gif_pair",
                "gifs": [
                    ("Physical Attack", os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "ArtResource", "Tutorial", "Attack1.gif")),
                    ("Digital Attack", os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "ArtResource", "Tutorial", "Attack.gif")),
                ],
            },
        ],

        "Special Events": [
            {
                "title": "Event Types",
                "layout": "vertical_images",
                "text": (
                    "Special event points can appear on the board during the game.\n"
                    "When a piece moves onto an event point, the effect is triggered immediately."
                ),
                "images": [
                    ("Attack Boost", "Increases the piece's ATK by 2.",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "AttackBoost.png")),
                    ("Healing Spot", "Restores 1 HP to the piece.",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "HealingSpot.png")),
                    ("Trap Tile", "Reduces the piece's HP by 1.",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "TrapTile.png")),
                ],
            },
        ],

        "Game Notifications": [
            {
                "title": "System Feedback",
                "layout": "single_center_image",
                "images": [
                    ("System Feedback",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "SystemFeedback.png")),
                ],
            },
            {
                "title": "Error Handling",
                "layout": "single_center_image",
                "images": [
                    ("Error Handling",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ArtResource", "Home", "Guide", "ErrorHandling.png")),
                ],
            },
        ],
    }


def _draw_game_guide_panel(
    screen: pygame.Surface,
    *,
    selected_section_idx: int,
    page_index_by_section: dict[str, int],
    clickable_rects: dict[str, object],
) -> None:
    dim = pygame.Surface((display_config.WINDOW_W, display_config.WINDOW_H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 170))
    screen.blit(dim, (0, 0))

    guide_content = _build_game_guide_content()
    selected_section = GUIDE_SECTIONS[selected_section_idx]
    section_pages = guide_content[selected_section]
    current_page = int(page_index_by_section.get(selected_section, 0))
    current_page = max(0, min(current_page, len(section_pages) - 1))
    page_index_by_section[selected_section] = current_page

    box_w = int(display_config.WINDOW_W * 0.82)
    box_y = int(display_config.WINDOW_H * 0.04)
    box_bottom_margin = int(display_config.WINDOW_H * 0.04)
    box_h = display_config.WINDOW_H - box_y - box_bottom_margin
    box = pygame.Rect(
        display_config.WINDOW_W // 2 - box_w // 2,
        box_y,
        box_w,
        box_h,
    )
    pygame.draw.rect(screen, (13, 18, 26), box, border_radius=18)
    pygame.draw.rect(screen, (176, 149, 92), box, width=2, border_radius=18)

    title_font = _menu_font(max(38, int(46 * display_config.UI_SCALE)), bold=True)
    nav_font = _menu_font(max(18, int(21 * display_config.UI_SCALE)), bold=True)
    body_font = _menu_font(max(21, int(25 * display_config.UI_SCALE)))
    meta_font = _menu_font(max(18, int(21 * display_config.UI_SCALE)))

    title = _render_gradient_text(title_font, "Game Guide", (235, 204, 135), (150, 102, 38))
    screen.blit(title, (box.centerx - title.get_width() // 2, box.y + 30))

    inner_x = box.x + 19
    inner_y = box.y + int(box.height * 0.13)
    inner_w = box.width - int(box.width * 0.04)
    inner_h = int(box.height * 0.70)

    panel_inner = pygame.Rect(inner_x, inner_y, inner_w, inner_h)
    nav_w = max(210, int(panel_inner.width * 0.29))
    nav_rect = pygame.Rect(panel_inner.x, panel_inner.y, nav_w, panel_inner.height)
    content_rect = pygame.Rect(nav_rect.right + 16, panel_inner.y, panel_inner.width - nav_w - 16, panel_inner.height)

    pygame.draw.rect(screen, (18, 25, 36), nav_rect, border_radius=14)
    pygame.draw.rect(screen, (108, 92, 62), nav_rect, width=1, border_radius=14)
    pygame.draw.rect(screen, (14, 20, 29), content_rect, border_radius=14)
    pygame.draw.rect(screen, (108, 92, 62), content_rect, width=1, border_radius=14)

    item_gap = 8
    item_h = max(40, int((nav_rect.height - 16 - item_gap * (len(GUIDE_SECTIONS) - 1)) / len(GUIDE_SECTIONS)))
    item_y = nav_rect.y + 8
    nav_item_rects: list[pygame.Rect] = []
    mouse_pos = pygame.mouse.get_pos()

    for i, label in enumerate(GUIDE_SECTIONS):
        item_rect = pygame.Rect(nav_rect.x + 8, item_y, nav_rect.width - 16, item_h)
        nav_item_rects.append(item_rect)
        item_y += item_h + item_gap

        is_active = i == selected_section_idx
        is_hovered = item_rect.collidepoint(mouse_pos)
        bg = (52, 65, 86) if is_active else ((36, 48, 66) if is_hovered else (22, 31, 44))
        border = (202, 170, 104) if is_active else ((150, 128, 88) if is_hovered else (78, 68, 52))
        pygame.draw.rect(screen, bg, item_rect, border_radius=9)
        pygame.draw.rect(screen, border, item_rect, width=2 if is_active else 1, border_radius=9)

        label_surf = nav_font.render(label, True, (237, 222, 190) if is_active else (223, 206, 172))
        screen.blit(
            label_surf,
            (item_rect.x + 14, item_rect.centery - label_surf.get_height() // 2),
        )

    content_title = _render_gradient_text(
        _menu_font(max(29, int(33 * display_config.UI_SCALE)), bold=True),
        selected_section,
        (236, 217, 172),
        (157, 124, 72),
    )
    screen.blit(content_title, (content_rect.x + 24, content_rect.y + 16))

    content_text_y = content_rect.y + 66
    content_text_x = content_rect.x + 24
    content_text_w = content_rect.width - 48
    page_title_font = _menu_font(max(26, int(30 * display_config.UI_SCALE)), bold=True)

    page_data = section_pages[current_page]
    page_title = str(page_data.get("title", ""))
    sprites = page_data.get("sprites", [])
    text = page_data.get("text", "")
    images = page_data.get("images", [])
    gifs = page_data.get("gifs", [])

    wrapped_lines = _wrap_text(page_title, page_title_font, content_text_w)
    for wrapped in wrapped_lines:
        surf = page_title_font.render(wrapped, True, (233, 223, 204))
        screen.blit(surf, (content_text_x, content_text_y))
        content_text_y += surf.get_height() + 9

    if text:
        content_text_y += 8
        for raw_line in str(text).split("\n"):
            if raw_line.strip() == "":
                content_text_y += body_font.get_height() // 2
                continue

            wrapped_text_lines = _wrap_text(raw_line, body_font, content_text_w)
            for line in wrapped_text_lines:
                surf = body_font.render(line, True, (220, 210, 190))
                screen.blit(surf, (content_text_x, content_text_y))
                content_text_y += surf.get_height() + 6

    layout = page_data.get("layout", "")
    if layout == "gif_pair" and isinstance(gifs, list) and gifs:
        gif_y = content_text_y + 22
        target_h = int(content_rect.height * 0.36)
        gap = 34
        gif_surfaces = []

        for name, path in gifs:
            frames = _load_gif_frames(str(path), target_h)
            if not frames:
                continue
            frame_index = (pygame.time.get_ticks() // 90) % len(frames)
            gif_surfaces.append((str(name), frames[frame_index]))

        if gif_surfaces:
            total_w = sum(frame.get_width() for _, frame in gif_surfaces) + gap * (len(gif_surfaces) - 1)
            start_x = content_rect.centerx - total_w // 2

            for name, frame in gif_surfaces:
                screen.blit(frame, (start_x, gif_y))

                label = meta_font.render(name, True, (220, 201, 166))
                screen.blit(
                    label,
                    (
                        start_x + frame.get_width() // 2 - label.get_width() // 2,
                        gif_y + frame.get_height() + 8,
                    ),
                )

                start_x += frame.get_width() + gap

    if selected_section != "Piece Identity" and isinstance(images, list) and images:
        img_y = content_text_y + 18

        if layout == "single_center_image":
            for name, path in images:
                if not os.path.exists(str(path)):
                    continue

                img = pygame.image.load(str(path)).convert_alpha()
                target_h = int(content_rect.height * 0.42)
                scale = target_h / max(1, img.get_height())
                img = pygame.transform.smoothscale(
                    img,
                    (int(img.get_width() * scale), target_h),
                )

                img_x = content_rect.centerx - img.get_width() // 2
                screen.blit(img, (img_x, img_y))

                label = meta_font.render(str(name), True, (220, 201, 166))
                screen.blit(
                    label,
                    (
                        content_rect.centerx - label.get_width() // 2,
                        img_y + img.get_height() + 8,
                    ),
                )

        elif layout == "vertical_images":
            target_h = 58

            for item in images:
                name, description, path = item

                if not os.path.exists(str(path)):
                    continue

                img = pygame.image.load(str(path)).convert_alpha()
                scale = target_h / max(1, img.get_height())
                img = pygame.transform.smoothscale(
                    img,
                    (int(img.get_width() * scale), target_h),
                )

                img_x = content_rect.x + 55
                screen.blit(img, (img_x, img_y))

                name_surf = meta_font.render(str(name), True, (236, 217, 172))
                desc_surf = body_font.render(str(description), True, (220, 210, 190))

                text_x = img_x + img.get_width() + 24
                screen.blit(name_surf, (text_x, img_y + 2))
                screen.blit(desc_surf, (text_x, img_y + 30))

                img_y += target_h + 28

        else:
            img_x = content_rect.x + 55

            for name, path in images:
                if not os.path.exists(str(path)):
                    continue

                img = pygame.image.load(str(path)).convert_alpha()
                target_h = 115
                scale = target_h / max(1, img.get_height())
                img = pygame.transform.smoothscale(
                    img,
                    (int(img.get_width() * scale), target_h),
                )

                screen.blit(img, (img_x, img_y))

                label = meta_font.render(str(name), True, (220, 201, 166))
                screen.blit(
                    label,
                    (
                        img_x + img.get_width() // 2 - label.get_width() // 2,
                        img_y + img.get_height() + 8,
                    ),
                )

                img_x += img.get_width() + 55

    sprite_y = content_text_y + 15
    last_sprite_bottom = sprite_y
    sprite_x = content_rect.x + 35
    frame_index = (pygame.time.get_ticks() // 180) % 12

    if isinstance(sprites, list):
        for name, path in sprites:
            frames = _load_sprite_strip(str(path), target_height=65)
            if not frames:
                continue

            frame = frames[frame_index % len(frames)]
            screen.blit(frame, (sprite_x, sprite_y))
            last_sprite_bottom = max(last_sprite_bottom, sprite_y + frame.get_height() + 40)

            label = meta_font.render(str(name), True, (220, 201, 166))
            screen.blit(
                label,
                (
                    sprite_x + frame.get_width() // 2 - label.get_width() // 2,
                    sprite_y + frame.get_height() + 10,
                ),
            )

            sprite_x += 150
            if sprite_x > content_rect.right - 140:
                sprite_x = content_rect.x + 35
                sprite_y += 120
    
    if selected_section == "Piece Identity" and isinstance(images, list) and images:
        img_y = last_sprite_bottom + 22
        img_x = content_rect.x + 150

        for name, path in images:
            if not os.path.exists(str(path)):
                continue

            img = pygame.image.load(str(path)).convert_alpha()
            if current_page == 4:
                target_h = int(content_rect.height * 0.18)
            else:
                target_h = int(content_rect.height * 0.28)

            scale = target_h / max(1, img.get_height())
            img = pygame.transform.smoothscale(
                img,
                (int(img.get_width() * scale), target_h),
            )

            draw_x = img_x - img.get_width() // 2
            screen.blit(img, (draw_x, img_y))

            label = meta_font.render("Movement Range", True, (220, 201, 166))
            screen.blit(
                label,
                (
                    img_x - label.get_width() // 2,
                    img_y + img.get_height() + 6,
                ),
            )

    arrow_y = content_rect.bottom - 56
    left_arrow_rect = pygame.Rect(content_rect.x + 24, arrow_y, 52, 36)
    right_arrow_rect = pygame.Rect(content_rect.right - 76, arrow_y, 52, 36)

    page_indicator = meta_font.render(
        f"Page {current_page + 1}/{len(section_pages)}",
        True,
        (220, 201, 166),
    )
    screen.blit(
        page_indicator,
        (content_rect.centerx - page_indicator.get_width() // 2, arrow_y + 7),
    )

    can_go_prev = current_page > 0
    can_go_next = current_page < len(section_pages) - 1

    _draw_simple_button(
        screen,
        left_arrow_rect,
        "<",
        hovered=left_arrow_rect.collidepoint(mouse_pos) and can_go_prev,
    )

    _draw_simple_button(
        screen,
        right_arrow_rect,
        ">",
        hovered=right_arrow_rect.collidepoint(mouse_pos) and can_go_next,
    )

    close_w = int(box.width * 0.24)
    close_h = int(box.height * 0.055)
    close_rect = pygame.Rect(
        box.centerx - close_w // 2,
        box.bottom - int(box.height * 0.10),
        close_w,
        close_h,
    )
    _draw_menu_button(screen, close_rect, "Back", hovered=close_rect.collidepoint(mouse_pos))

    clickable_rects["close"] = close_rect
    clickable_rects["nav_items"] = nav_item_rects
    clickable_rects["left_arrow"] = left_arrow_rect
    clickable_rects["right_arrow"] = right_arrow_rect
    clickable_rects["left_arrow_enabled"] = can_go_prev
    clickable_rects["right_arrow_enabled"] = can_go_next


def _apply_guide_click(
    click_pos: tuple[int, int],
    selected_section_idx: int,
    page_index_by_section: dict[str, int],
    clickable_rects: dict[str, object],
) -> tuple[int, bool]:
    close_rect = clickable_rects.get("close")
    if isinstance(close_rect, pygame.Rect) and close_rect.collidepoint(click_pos):
        return selected_section_idx, True

    nav_item_rects = clickable_rects.get("nav_items", [])
    if isinstance(nav_item_rects, list):
        for idx, rect in enumerate(nav_item_rects):
            if isinstance(rect, pygame.Rect) and rect.collidepoint(click_pos):
                selected_section_idx = idx
                section = GUIDE_SECTIONS[idx]
                page_index_by_section[section] = 0
                return selected_section_idx, False

    section = GUIDE_SECTIONS[selected_section_idx]
    section_pages = _build_game_guide_content().get(section, [""])
    current_page = int(page_index_by_section.get(section, 0))
    current_page = max(0, min(current_page, len(section_pages) - 1))

    left_arrow_rect = clickable_rects.get("left_arrow")
    if (
        isinstance(left_arrow_rect, pygame.Rect)
        and bool(clickable_rects.get("left_arrow_enabled", False))
        and left_arrow_rect.collidepoint(click_pos)
    ):
        page_index_by_section[section] = max(0, current_page - 1)
        return selected_section_idx, False

    right_arrow_rect = clickable_rects.get("right_arrow")
    if (
        isinstance(right_arrow_rect, pygame.Rect)
        and bool(clickable_rects.get("right_arrow_enabled", False))
        and right_arrow_rect.collidepoint(click_pos)
    ):
        page_index_by_section[section] = min(len(section_pages) - 1, current_page + 1)
        return selected_section_idx, False

    return selected_section_idx, False


def _run_main_menu(screen: pygame.Surface, clock: pygame.time.Clock) -> bool:
    show_guide = False
    start_btn = pygame.Rect(0, 0, 390, 74)
    guide_btn = pygame.Rect(0, 0, 390, 74)
    guide_clickable_rects: dict[str, object] = {}
    guide_section_idx = 0
    guide_page_by_section: dict[str, int] = {section: 0 for section in GUIDE_SECTIONS}

    while True:
        mouse_pos = pygame.mouse.get_pos()
        center_x = display_config.WINDOW_W // 2
        btn_gap = max(20, int(22 * display_config.UI_SCALE))
        start_y = int(display_config.WINDOW_H * 0.65)
        start_btn.update(
            center_x - start_btn.width // 2,
            start_y,
            start_btn.width,
            start_btn.height,
        )
        guide_btn.update(
            center_x - guide_btn.width // 2,
            start_y + start_btn.height + btn_gap,
            guide_btn.width,
            guide_btn.height,
        )

        if not show_guide:
            is_hovering_button = (
                start_btn.collidepoint(mouse_pos)
                or guide_btn.collidepoint(mouse_pos)
            )
        else:
            is_hovering_button = False
            for key in ("close", "left_arrow", "right_arrow"):
                rect = guide_clickable_rects.get(key)
                if not isinstance(rect, pygame.Rect):
                    continue
                if key == "left_arrow" and not bool(guide_clickable_rects.get("left_arrow_enabled", False)):
                    continue
                if key == "right_arrow" and not bool(guide_clickable_rects.get("right_arrow_enabled", False)):
                    continue
                if rect.collidepoint(mouse_pos):
                    is_hovering_button = True
                    break
            if not is_hovering_button:
                nav_item_rects = guide_clickable_rects.get("nav_items", [])
                if isinstance(nav_item_rects, list):
                    is_hovering_button = any(
                        isinstance(rect, pygame.Rect) and rect.collidepoint(mouse_pos)
                        for rect in nav_item_rects
                    )

        if is_hovering_button:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
        else:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if ev.type == pygame.VIDEORESIZE:
                w, h = int(ev.w), int(ev.h)
                if w > 0 and h > 0:
                    screen = _rebuild_ui_after_window_resize(w, h)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                if show_guide:
                    show_guide = False
                else:
                    return False
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if show_guide:
                    guide_section_idx, should_close = _apply_guide_click(
                        ev.pos,
                        guide_section_idx,
                        guide_page_by_section,
                        guide_clickable_rects,
                    )
                    if should_close:
                        show_guide = False
                else:
                    if start_btn.collidepoint(ev.pos):
                        return True
                    if guide_btn.collidepoint(ev.pos):
                        show_guide = True

        screen.blit(_load_home_menu_background(), (0, 0))
        if not show_guide:
            _draw_main_menu_characters(screen)
        title_bottom_y = _draw_title_image(screen)
        btn_gap = max(20, int(22 * display_config.UI_SCALE))
    
        if not show_guide:
            _draw_menu_button(screen, start_btn, "Start Set Up", hovered=start_btn.collidepoint(mouse_pos))
            _draw_menu_button(screen, guide_btn, "Game Guide", hovered=guide_btn.collidepoint(mouse_pos))
        else:
            _draw_game_guide_panel(
                screen,
                selected_section_idx=guide_section_idx,
                page_index_by_section=guide_page_by_section,
                clickable_rects=guide_clickable_rects,
            )

        pygame.display.flip()
        clock.tick(display_config.FPS)


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
    # pieces 鈥?only physical flip / vision pipeline drives that flow.
    if camera_board_input:
        return ""

    if click_node is None:
        return ""

    if sel.has_selection:
        pid = sel.selected_pid
        piece = state.pieces.get(pid)

        # Execute MOVE (one action per turn 鈫?proceed to RECOGNITION)
        if piece and not piece.is_dead and click_node in sel.valid_moves:
            apply_move(pid, click_node, state)
            sel.deselect()
            advance_phase(state)  # MOVEMENT 鈫?RECOGNITION
            return f"Moved {pid} 鈫?{click_node}"

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
            advance_phase(state)  # MOVEMENT 鈫?RECOGNITION
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

    if not _run_main_menu(screen, clock):
        pygame.quit()
        return

    state: GameState = build_default_state()
    sel           = SelectionState()
    log: list[str] = []
    log_history: list[str] = []
    game_over_ref  = [False]
    pending_attack_ref: list[dict | None] = [None]
    pending_event_ref: list[dict | None] = [None]
    pending_attack_commit_ref: list[dict | None] = [None]
    pending_attacker_return_ref: list[dict | None] = [None]
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

    _push(log, f"Round {state.round_number} 鈥?{faction}'s turn", history=log_history)
    if args.vision and vision_tracker is not None:
        tracked = vision_status.tracked_pieces if vision_status is not None else 0
        board_txt = "board ok" if vision_status is not None and vision_status.board_ok else "waiting for board"
        _push(log, f"Vision ON: {tracked}/14 pieces, {board_txt}", history=log_history)
    elif args.vision:
        _push(log, "Vision unavailable; using default positions.", history=log_history)
    setup_board_seen_once_ref: list[bool] = [False]
    setup_last_board_seen_ms_ref: list[int | None] = [None]
    setup_board_lost_logged_ref: list[bool] = [False]
    setup_board_logged_ref: list[bool] = [False]
    setup_detected_piece_ids_ref: list[set[str]] = [set()]
    setup_wrong_position_ids_ref: list[set[str]] = [set()]
    setup_ready_prev_state_ref: list[bool] = [False]

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
    _apply_setup_board_display_grace(
        setup_status,
        pygame.time.get_ticks(),
        board_seen_once_ref=setup_board_seen_once_ref,
        last_board_seen_ms_ref=setup_last_board_seen_ms_ref,
        board_lost_logged_ref=setup_board_lost_logged_ref,
        log=log,
        log_history=log_history,
    )
    _push_setup_event_logs(
        log,
        log_history,
        setup_status,
        board_logged_ref=setup_board_logged_ref,
        detected_piece_ids_ref=setup_detected_piece_ids_ref,
        wrong_position_ids_ref=setup_wrong_position_ids_ref,
        ready_prev_state_ref=setup_ready_prev_state_ref,
    )

    running = True
    log_modal_open = False
    log_modal_scroll = 0
    log_modal_dragging = False
    log_modal_drag_offset_y = 0
    setup_guide_open = False
    setup_guide_clickable_rects: dict[str, object] = {}
    setup_guide_section_idx = 0
    setup_guide_page_by_section: dict[str, int] = {section: 0 for section in GUIDE_SECTIONS}
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
        ui_others.sync_top_bar_button_rects(show_tutorial=not setup_complete)
        tutorial_hover       = (not setup_complete) and TUTORIAL_RECT.collidepoint(mouse_pos)
        guide_hover          = GUIDE_RECT.collidepoint(mouse_pos)

        can_action_buttons = (
            (not game_over)
            and setup_complete
            and state.current_phase is Phase.MOVEMENT
            and pending_attacker_return_ref[0] is None
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
                draw_label = "Waiting..."
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
                if setup_guide_open:
                    if ev.key == pygame.K_ESCAPE:
                        setup_guide_open = False
                    continue
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
                            pending_attacker_return_ref=pending_attacker_return_ref,
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
                if setup_guide_open:
                    setup_guide_section_idx, should_close = _apply_guide_click(
                        ev.pos,
                        setup_guide_section_idx,
                        setup_guide_page_by_section,
                        setup_guide_clickable_rects,
                    )
                    if should_close:
                        setup_guide_open = False
                    continue
                if GUIDE_RECT.collidepoint(mx, my):
                    setup_guide_open = True
                    log_modal_open = False
                    log_modal_dragging = False
                    continue
                if not setup_complete and TUTORIAL_RECT.collidepoint(mx, my):
                    screen = run_tutorial_mode(
                        screen,
                        clock,
                        vision_tracker=vision_tracker,
                        vision_sync_ms=args.vision_sync_ms,
                    )
                    log_modal_open = False
                    log_modal_dragging = False
                    continue
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
            and pending_attacker_return_ref[0] is None
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
                    _apply_setup_board_display_grace(
                        setup_status,
                        now_ms,
                        board_seen_once_ref=setup_board_seen_once_ref,
                        last_board_seen_ms_ref=setup_last_board_seen_ms_ref,
                        board_lost_logged_ref=setup_board_lost_logged_ref,
                        log=log,
                        log_history=log_history,
                    )
                    _push_setup_event_logs(
                        log,
                        log_history,
                        setup_status,
                        board_logged_ref=setup_board_logged_ref,
                        detected_piece_ids_ref=setup_detected_piece_ids_ref,
                        wrong_position_ids_ref=setup_wrong_position_ids_ref,
                        ready_prev_state_ref=setup_ready_prev_state_ref,
                    )
                    vision_messages = []
                else:
                    if pending_kill_queue or pending_kill_staging:
                        # During the kill dialog/delay, vision is used only to
                        # detect removal of fallen pieces. Do not sync live
                        # piece positions into GameState, otherwise a player
                        # can move a live piece during the modal and have that
                        # illegal position accepted before normal validation
                        # resumes.
                        vision_messages = []
                    else:
                        vision_messages = _sync_state_to_vision(
                            state,
                            vision_status.positions,
                            sel,
                            pending_retracts,
                        )
                if setup_complete:
                    vision_messages.extend(
                        _try_complete_attacker_return_gate(
                            state,
                            pending_attacker_return_ref,
                            vision_status,
                        )
                    )
                # While an attacker-return gate or kill confirmation is pending,
                # freeze new vision-driven actions / selections.
                if (
                    setup_complete
                    and pending_attacker_return_ref[0] is None
                    and not pending_kill_queue
                    and not pending_kill_staging
                ):
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
                if setup_complete:
                    vision_messages.extend(vision_status.conflicts)
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
                    from_pos = tuple(pending_attack["from_pos"])
                    target_pos = pending_attack["target_pos"]
                    if pending_attack["is_wizard"]:
                        apply_wizard_attack(attacker_id, target_pos, state)
                    else:
                        apply_attack(attacker_id, target_pos, state)
                    pending_attack_ref[0] = None
                    _push(log, f"{attacker_id} hit {target_pos}", history=log_history)

                    if args.vision and not _vision_front_marker_at(vision_status, attacker_id, from_pos):
                        pending_attacker_return_ref[0] = {
                            "attacker_id": attacker_id,
                            "from_pos": from_pos,
                        }
                        _push(
                            log,
                            f"Return attacker: place {attacker_id} face-up at {from_pos}.",
                            history=log_history,
                        )
                    else:
                        advance_phase(state)
            elif pending_attacker_return_ref[0] is not None:
                pass
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
                            _push(log, f"鉁?{piece_id} 鈫?{event_point.event_type.value}!", history=log_history)
                            pending_event_ref[0] = None
                    else:
                        apply_event_trigger(piece_id, event_point, state)
                        _push(log, f"鉁?{piece_id} 鈫?{event_point.event_type.value}!", history=log_history)
                        pending_event_ref[0] = None

            elif pending_kill_queue or pending_kill_staging:
                # Kill confirmation delay or modal 鈥?block mouse-driven move/attack.
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

            # 鈹€鈹€ Drain any auto-phases that were triggered 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
            if (
                pending_attack_ref[0] is None
                and pending_attacker_return_ref[0] is None
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
                _push(log, f"Round {state.round_number} 鈥?{new_faction}'s turn", history=log_history)

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
        current_warning = _derive_minor_warning(log)
        # PLAYING-only error gate for top-bar flashing.
        playing_error_active = False
        top_minor_warning = None
        if setup_complete:
            blocking_issue = bool(pending_kill_queue)
            top_minor_warning = current_warning
            playing_error_active = (current_warning is not None) or blocking_issue
            if blocking_issue and top_minor_warning is None:
                top_minor_warning = "Remove captured piece"
        draw_top_bar(
            screen,
            show_tutorial=not setup_complete,
            tutorial_hover=tutorial_hover,
            guide_hover=guide_hover,
            state=(state if setup_complete else None),
            selected_pid=sel.selected_pid,
            minor_warning=top_minor_warning,
            status_is_error=playing_error_active,
        )
        draw_board(screen)
        draw_dead_pieces(screen, state)
        draw_event_points(screen, state, draw_heal_effects=False)

        # Setup-only rendering: before the board is detected, dim the whole board
        # and hide pieces on it. Once the board is detected, keep the board bright
        # but render pieces muted until setup completes.
        setup_board_detected = True
        if not setup_complete and args.vision:
            setup_board_detected = bool((setup_status or {}).get("board_detected", False))
            if not setup_board_detected:
                board_rect = pygame.Rect(
                    display_config.BOARD_IMAGE_LEFT,
                    display_config.BOARD_IMAGE_TOP,
                    display_config.BOARD_IMAGE_W,
                    display_config.BOARD_IMAGE_H,
                )
                dim = pygame.Surface(board_rect.size, pygame.SRCALPHA)
                dim.fill((0, 0, 0, 165))
                screen.blit(dim, board_rect.topleft)

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
        if setup_complete or (not args.vision) or setup_board_detected:
            draw_pieces(
                screen,
                state,
                visible_piece_ids=visible_piece_ids,
                inactive_piece_ids=_inactive_setup_piece_ids(setup_status) if not setup_complete else None,
                setup_wrong_position_ids=(
                    _wrong_position_setup_piece_ids(setup_status) if not setup_complete else None
                ),
                draw_inactive_hp=setup_complete or (not args.vision),
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
            "Action required (move or attack)" if state.current_phase is Phase.MOVEMENT else ""
        )

        if not setup_complete:
            btn_lbl = "Start Game"

        notification_errors = collect_playing_notification_errors(
            setup_complete=setup_complete,
            args=args,
            vision_tracker=vision_tracker,
            vision_status=vision_status,
            pending_kill_queue=pending_kill_queue,
            log=log,
        )
        hint_context = build_hint_context(
            state=state,
            sel=sel,
            vision_status=vision_status,
            pending_attack_ref=pending_attack_ref[0],
            pending_attack_commit_ref=pending_attack_commit_ref[0],
            pending_event_ref=pending_event_ref[0],
            pending_retracts=pending_retracts,
            pending_kill_queue=pending_kill_queue,
            pending_kill_staging=pending_kill_staging,
        )

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
            tutorial_hover = tutorial_hover,
            selected_pid = sel.selected_pid,
            log_modal_open = log_modal_open,
            log_modal_scroll = log_modal_scroll,
            btn_enabled=(_setup_ready(setup_status) if not setup_complete else can_action_buttons),
            setup_status=(setup_status if not setup_complete else None),
            notification_errors=notification_errors,
            hint_context=hint_context,
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

        if setup_guide_open:
            _draw_game_guide_panel(
                screen,
                selected_section_idx=setup_guide_section_idx,
                page_index_by_section=setup_guide_page_by_section,
                clickable_rects=setup_guide_clickable_rects,
            )

        pygame.display.flip()
        clock.tick(display_config.FPS)

    if vision_tracker is not None:
        vision_tracker.close()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
