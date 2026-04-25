"""
Xiangqi Arena — main game loop.

Player-facing interaction is reduced to exactly TWO phases per turn:

  MOVEMENT  : click a piece, then click a green node  (Enter = skip)
  ATTACK    : click a red target                       (Enter = skip)

The other three phases (START, RECOGNITION, RESOLVE) are processed
automatically on the same frame they are entered — players never see a
"Press Enter to continue" prompt for them.

Controls
--------
  Mouse click on board  : select piece / choose destination or attack target
  Enter / Space         : skip the current action (move or attack)
  Escape                : cancel current selection (or quit on game-over)
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

# Allow `python xiangqi_arena/main.py` to work from the project root.
# When run as a script the package root is not on sys.path; add it here.
if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame

# ---------------------------------------------------------------------------
# Game-logic imports
# ---------------------------------------------------------------------------
from xiangqi_arena.core.enums import Faction, Phase, PieceType, VictoryState
from xiangqi_arena.flow.phase import advance_phase
from xiangqi_arena.flow.round import should_spawn_event_point
from xiangqi_arena.flow.turn import can_select_piece, end_turn, start_turn
from xiangqi_arena.modification.attack import (
    apply_attack, apply_cannon_attack, apply_skip_attack,
)
from xiangqi_arena.modification.event import apply_event_trigger, spawn_event_point
from xiangqi_arena.modification.move import apply_move, apply_skip_move
from xiangqi_arena.rules.event_rules import get_all_triggers
from xiangqi_arena.rules.illegal_rules import (
    IllegalMoveReport,
    validate_no_extra_moves,
    validate_recognised_move,
)
from xiangqi_arena.rules.piece_rules import legal_attack_targets, legal_moves
from xiangqi_arena.state.game_state import GameState, build_default_state
from xiangqi_arena.recognition.detect_marker_bridge import DetectMarkerScanner
from xiangqi_arena.recognition.marker_parser import build_game_state_from_snapshot
from xiangqi_arena.recognition.scanner_interface import (
    ScannerMoveEvent,
    ScannerSnapshot,
    VisionScanner,
)

# ---------------------------------------------------------------------------
# UI / input imports
# ---------------------------------------------------------------------------
from xiangqi_arena.input_control.keyboard_handler import KeyAction, classify_key
from xiangqi_arena.input_control.selection_handler import (
    SelectionState, pixel_to_node,
)
from xiangqi_arena.ui.board_renderer import draw_board
from xiangqi_arena.ui.death_marker_renderer import draw_dead_pieces
from xiangqi_arena.ui.display_config import (
    FPS, WINDOW_H, WINDOW_TITLE, WINDOW_W,
)
from xiangqi_arena.ui.event_renderer import draw_event_points
from xiangqi_arena.ui.highlight_renderer import draw_highlights
from xiangqi_arena.ui.others import BUTTON_RECT, draw_panel, draw_victory_overlay
from xiangqi_arena.ui.piece_renderer import draw_pieces


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LOG_MAX = 15   # keep at most this many log entries


@dataclass
class IllegalRecoveryState:
    piece_id: str
    reason: str
    legal_pos: tuple[int, int]
    illegal_pos: tuple[int, int]
    animation_started_at_ms: int
    animation_duration_ms: int = 420
    awaiting_physical_restore: bool = True
    restored_at_ms: int | None = None

    def animation_finished(self, now_ms: int) -> bool:
        return now_ms >= self.animation_started_at_ms + self.animation_duration_ms


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Xiangqi Arena")
    parser.add_argument(
        "--vision-source",
        default=1,
        help="Camera index or stream URL for physical-board recognition.",
    )
    parser.add_argument("--vision-width", type=int, default=1280)
    parser.add_argument("--vision-height", type=int, default=720)
    parser.add_argument(
        "--vision-no-line-snap",
        action="store_true",
        help="Disable line snapping when deriving the digital board grid.",
    )
    parser.add_argument("--vision-snap-radius", type=int, default=22)
    parser.add_argument("--vision-warp-width", type=int, default=900)
    parser.add_argument("--vision-warp-height", type=int, default=1000)
    parser.add_argument("--vision-warp-quad-expand", type=float, default=0.0)
    parser.add_argument("--vision-piece-off-fwd", type=float, default=0.0)
    parser.add_argument("--vision-piece-off-side", type=float, default=0.0)
    parser.add_argument("--vision-piece-cell-mult", type=float, default=None)
    parser.add_argument("--vision-aruco-strict", action="store_true")
    parser.add_argument(
        "--vision-init-frames",
        type=int,
        default=90,
        help="Maximum frames to wait for the first complete physical-board snapshot.",
    )
    return parser.parse_args(argv)


def _build_vision_scanner(args: argparse.Namespace) -> VisionScanner | None:
    if args.vision_source is None:
        return None
    return DetectMarkerScanner(
        source=args.vision_source,
        width=args.vision_width,
        height=args.vision_height,
        line_snap=not args.vision_no_line_snap,
        snap_radius=args.vision_snap_radius,
        warp_width=args.vision_warp_width,
        warp_height=args.vision_warp_height,
        warp_quad_expand=args.vision_warp_quad_expand,
        piece_off_fwd=args.vision_piece_off_fwd,
        piece_off_side=args.vision_piece_off_side,
        piece_cell_mult=args.vision_piece_cell_mult,
        aruco_strict=args.vision_aruco_strict,
    )


def _is_snapshot_usable(snapshot: ScannerSnapshot | None) -> bool:
    """A snapshot is usable when the board is visible and piece cells are coherent."""
    if snapshot is None:
        return False
    if not snapshot.board_visible:
        return False
    if not snapshot.piece_cells:
        return False
    return not snapshot.diagnostics


def _bootstrap_state_from_vision(
    scanner: VisionScanner | None,
    init_frames: int,
) -> tuple[GameState, list[str], bool]:
    if scanner is None:
        return build_default_state(), [], True

    last_snapshot: ScannerSnapshot | None = None
    for _ in range(max(1, init_frames)):
        snapshot = scanner.poll_snapshot()
        scanner.poll_move_events()
        if snapshot is None:
            continue
        last_snapshot = snapshot
        if _is_snapshot_usable(snapshot):
            completeness = "complete" if snapshot.complete else "partial"
            return (
                build_game_state_from_snapshot(snapshot.piece_cells),
                [
                    f"Vision board synced from {completeness} physical setup "
                    f"({len(snapshot.piece_cells)} pieces)."
                ],
                True,
            )

    if _is_snapshot_usable(last_snapshot):
        return (
            build_game_state_from_snapshot(last_snapshot.piece_cells),
            [
                "Vision board synced from late partial snapshot "
                f"({len(last_snapshot.piece_cells)} pieces)."
            ],
            True,
        )

    if last_snapshot is not None:
        details = []
        if last_snapshot.missing_aruco_ids:
            details.append(f"missing={list(last_snapshot.missing_aruco_ids)}")
        if last_snapshot.diagnostics:
            details.append(last_snapshot.diagnostics[0])
        suffix = f" ({'; '.join(details)})" if details else ""
    else:
        suffix = ""
    return (
        build_default_state(),
        [f"Vision init incomplete; using default setup{suffix}."],
        False,
    )


def _vision_instruction(vision_enabled: bool, phase: Phase) -> str | None:
    if not vision_enabled:
        return None
    if phase is Phase.MOVEMENT:
        return "Move a physical piece on the board  |  Enter = skip"
    if phase is Phase.ATTACK:
        return "Attack is still manual in this build  |  Click red target or Enter"
    return None


def _sync_state_from_snapshot(
    snapshot: ScannerSnapshot,
    state: GameState,
    sel: SelectionState,
    log: list[str],
) -> GameState:
    """
    Replace the arena state with the latest usable vision snapshot.

    This is only used before the first accepted physical move, so it is safe to
    rebuild the board state wholesale to match the real table setup.
    """
    new_state = build_game_state_from_snapshot(
        snapshot.piece_cells,
        active_faction=state.active_faction,
        round_number=state.round_number,
        current_phase=state.current_phase,
    )
    new_state.event_points = list(state.event_points)
    new_state.history = list(state.history)
    sel.deselect()
    _push(log, f"Vision state resynced ({len(snapshot.piece_cells)} pieces).")
    return new_state


def _format_attack_hint(piece_id: str, attacks: list[tuple[int, int]]) -> str:
    preview = ", ".join(str(pos) for pos in attacks[:4])
    if len(attacks) > 4:
        preview += ", ..."
    return f"Attack available for {piece_id}: {preview}"


def _make_illegal_recovery(
    piece_id: str,
    reason: str,
    legal_pos: tuple[int, int],
    illegal_pos: tuple[int, int],
    now_ms: int,
) -> IllegalRecoveryState:
    return IllegalRecoveryState(
        piece_id=piece_id,
        reason=reason,
        legal_pos=legal_pos,
        illegal_pos=illegal_pos,
        animation_started_at_ms=now_ms,
    )


def _messages_for_illegal_recovery(recovery: IllegalRecoveryState) -> list[str]:
    return [
        f"Illegal move detected: {recovery.reason}",
        f"Rollback shown. Restore {recovery.piece_id} to {recovery.legal_pos}.",
    ]


def _build_illegal_recovery_for_report(
    report: IllegalMoveReport,
    now_ms: int,
) -> IllegalRecoveryState:
    return _make_illegal_recovery(
        piece_id=report.piece.id,
        reason=report.reason,
        legal_pos=report.from_pos,
        illegal_pos=report.to_pos,
        now_ms=now_ms,
    )


def _handle_vision_movement(
    state: GameState,
    sel: SelectionState,
    event: ScannerMoveEvent,
    now_ms: int,
) -> tuple[list[str], IllegalRecoveryState | None]:
    if state.current_phase is not Phase.MOVEMENT:
        return [], None

    piece = state.pieces.get(event.piece_id)
    if piece is None:
        return [f"Vision move ignored: unknown piece {event.piece_id}."], None
    if piece.faction is not state.active_faction:
        recovery = _make_illegal_recovery(
            piece_id=event.piece_id,
            reason=f"{event.piece_id} is not the active side.",
            legal_pos=piece.pos,
            illegal_pos=event.to_pos,
            now_ms=now_ms,
        )
        return _messages_for_illegal_recovery(recovery), recovery
    if not can_select_piece(state, event.piece_id):
        recovery = _make_illegal_recovery(
            piece_id=event.piece_id,
            reason=f"{event.piece_id} cannot be selected now.",
            legal_pos=piece.pos,
            illegal_pos=event.to_pos,
            now_ms=now_ms,
        )
        return _messages_for_illegal_recovery(recovery), recovery
    if piece.pos != event.from_pos:
        if piece.pos == event.to_pos:
            return [], None
        recovery = _make_illegal_recovery(
            piece_id=event.piece_id,
            reason=(
                f"{event.piece_id} backend at {piece.pos}, "
                f"vision expected {event.from_pos}."
            ),
            legal_pos=piece.pos,
            illegal_pos=event.to_pos,
            now_ms=now_ms,
        )
        return _messages_for_illegal_recovery(recovery), recovery

    report = validate_recognised_move(piece, event.to_pos, state)
    if report is not None:
        recovery = _build_illegal_recovery_for_report(report, now_ms)
        return _messages_for_illegal_recovery(recovery), recovery

    apply_move(event.piece_id, event.to_pos, state)
    attacks = legal_attack_targets(piece, state)
    sel.select(event.piece_id, event.to_pos, moves=[], attacks=attacks)

    messages = [
        f"Vision move accepted: {event.piece_id} {event.from_pos} -> {event.to_pos}.",
    ]
    if attacks:
        messages.append(_format_attack_hint(event.piece_id, attacks))
    else:
        messages.append(f"No attack available for {event.piece_id}.")

    if any(ep.is_valid and not ep.is_triggered and ep.pos == event.to_pos for ep in state.event_points):
        messages.append(f"Event trigger pending at {event.to_pos}.")

    advance_phase(state)
    return messages, None


def _piece_at(state: GameState, pos: tuple) -> str | None:
    return state.board._occupancy.get(pos)


def _is_game_over(state: GameState) -> bool:
    return state.victory_state != VictoryState.ONGOING


# ---------------------------------------------------------------------------
# Auto-phase drain
# Called every frame until we land on an interactive phase (MOVEMENT/ATTACK).
# ---------------------------------------------------------------------------

def _drain_auto_phases(
    state: GameState,
    sel: SelectionState,
    log: list[str],
    game_over_ref: list[bool],
) -> None:
    """
    Process all non-interactive phases in a tight loop so that the player
    only ever "sees" MOVEMENT and ATTACK.

    All informational messages are pushed to *log* (newest-first).
    """
    for _ in range(10):
        phase = state.current_phase

        if phase in (Phase.MOVEMENT, Phase.ATTACK):
            break

        if phase == Phase.START:
            if should_spawn_event_point(state):
                spawn_event_point(state)
                descs = [
                    f"{ep.event_type.value}@{ep.pos}"
                    for ep in state.event_points
                ]
                _push(log, "✦ Spawned: " + "  /  ".join(descs))
            advance_phase(state)   # → MOVEMENT

        elif phase == Phase.RECOGNITION:
            triggers = get_all_triggers(state)
            for pid, ep in triggers:
                apply_event_trigger(pid, ep, state)
                _push(log, f"✦ {pid} → {ep.event_type.value}!")
            advance_phase(state)   # → ATTACK

            if sel.has_selection:
                pid = sel.selected_pid
                piece = state.pieces.get(pid)
                if piece and not piece.is_dead:
                    sel.valid_attacks = legal_attack_targets(piece, state)
                else:
                    sel.deselect()

        elif phase == Phase.RESOLVE:
            if _is_game_over(state):
                game_over_ref[0] = True
                break
            end_turn(state)
            sel.deselect()

        else:
            break


def _push(log: list[str], msg: str) -> None:
    """Prepend *msg* to *log* (newest first), trimming to LOG_MAX."""
    if msg.strip():
        log.insert(0, msg)
        while len(log) > LOG_MAX:
            log.pop()


def _active_illegal_status_lines(recovery: IllegalRecoveryState, now_ms: int) -> list[str]:
    if not recovery.animation_finished(now_ms):
        return [
            f"Illegal move: {recovery.piece_id} at {recovery.illegal_pos}.",
            f"Rolling back to {recovery.legal_pos}...",
        ]
    if recovery.awaiting_physical_restore:
        return [
            f"Illegal move: {recovery.reason}",
            f"Return the physical piece to {recovery.legal_pos}, then move again.",
        ]
    return [f"{recovery.piece_id} restored to {recovery.legal_pos}. Move again."]


# ---------------------------------------------------------------------------
# Interactive phase: MOVEMENT
# ---------------------------------------------------------------------------

def _handle_movement(
    state: GameState,
    sel: SelectionState,
    confirm: bool,
    click_node: tuple | None,
) -> str:
    active = state.active_faction

    if confirm:
        apply_skip_move(state)
        advance_phase(state)
        sel.deselect()
        return "Move skipped."

    if click_node is None:
        return ""

    if sel.has_selection and click_node in sel.valid_moves:
        pid   = sel.selected_pid
        piece = state.pieces[pid]
        apply_move(pid, click_node, state)
        sel.select(
            pid, click_node,
            moves=[],
            attacks=legal_attack_targets(piece, state),
        )
        advance_phase(state)
        return f"Moved {pid} → {click_node}"

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
    sel.select(pid, click_node, moves=moves, attacks=[])
    return f"Selected {pid}  ({len(moves)} moves)"


# ---------------------------------------------------------------------------
# Interactive phase: ATTACK
# ---------------------------------------------------------------------------

def _handle_attack(
    state: GameState,
    sel: SelectionState,
    confirm: bool,
    click_node: tuple | None,
) -> str:
    active = state.active_faction

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
            if piece.piece_type == PieceType.CANNON:
                apply_cannon_attack(pid, click_node, state)
            else:
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

def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    scanner: VisionScanner | None = None
    state: GameState
    startup_messages: list[str]
    vision_state_synced: bool

    try:
        scanner = _build_vision_scanner(args)
        state, startup_messages, vision_state_synced = _bootstrap_state_from_vision(
            scanner,
            args.vision_init_frames,
        )
    except Exception as exc:
        scanner = None
        state = build_default_state()
        startup_messages = [f"Vision disabled: {exc}"]
        vision_state_synced = True

    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption(WINDOW_TITLE)
    clock  = pygame.time.Clock()

    start_turn(state)

    sel           = SelectionState()
    log: list[str] = []
    game_over_ref  = [False]

    # Drain the first START phase so we land on MOVEMENT immediately
    _drain_auto_phases(state, sel, log, game_over_ref)
    game_over = game_over_ref[0]

    # Announce whose turn it is at startup
    faction = "RED" if state.active_faction == Faction.RED else "BLACK"
    _push(log, f"Round {state.round_number} — {faction}'s turn")
    for msg in startup_messages:
        _push(log, msg)

    running = True
    vision_warning_logged = False
    vision_hidden_streak = 0
    vision_visible_streak = 0
    illegal_recovery: IllegalRecoveryState | None = None
    restore_release_at_ms: int | None = None
    try:
        while running:
            # ------------------------------------------------------------
            # Event polling
            # ------------------------------------------------------------
            confirm              = False
            click_node: tuple | None = None
            mouse_pos            = pygame.mouse.get_pos()
            btn_hover            = BUTTON_RECT.collidepoint(mouse_pos)
            now_ms               = pygame.time.get_ticks()

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False

                elif ev.type == pygame.KEYDOWN:
                    ka = classify_key(ev)
                    if ka == KeyAction.CONFIRM:
                        confirm = True
                    elif ka == KeyAction.CANCEL:
                        if game_over:
                            running = False
                        else:
                            sel.deselect()

                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    mx, my = ev.pos
                    if BUTTON_RECT.collidepoint(mx, my):
                        confirm = True
                    else:
                        click_node = pixel_to_node(mx, my)

            vision_snapshot = scanner.poll_snapshot() if scanner is not None else None
            vision_events = scanner.poll_move_events() if scanner is not None else []
            if scanner is not None and vision_snapshot is not None and not vision_snapshot.board_visible:
                vision_hidden_streak += 1
                vision_visible_streak = 0
                if not vision_warning_logged and vision_hidden_streak >= 8:
                    _push(log, "Vision warning: board markers not visible.")
                    vision_warning_logged = True
            elif vision_snapshot is not None and vision_snapshot.board_visible:
                vision_visible_streak += 1
                vision_hidden_streak = 0
                if vision_visible_streak >= 5:
                    vision_warning_logged = False
                if (
                    not vision_state_synced
                    and _is_snapshot_usable(vision_snapshot)
                    and not state.action.movement_decided()
                    and state.current_phase is Phase.MOVEMENT
                ):
                    state = _sync_state_from_snapshot(
                        vision_snapshot,
                        state,
                        sel,
                        log,
                    )
                    vision_state_synced = True

            if illegal_recovery is not None and vision_snapshot is not None:
                restored_pos = vision_snapshot.piece_cells.get(illegal_recovery.piece_id)
                if restored_pos == illegal_recovery.legal_pos:
                    if illegal_recovery.awaiting_physical_restore:
                        illegal_recovery.awaiting_physical_restore = False
                        illegal_recovery.restored_at_ms = now_ms
                        restore_release_at_ms = max(
                            now_ms,
                            illegal_recovery.animation_started_at_ms + illegal_recovery.animation_duration_ms,
                        )
                        _push(
                            log,
                            f"Physical piece restored: {illegal_recovery.piece_id} -> {illegal_recovery.legal_pos}.",
                        )
                else:
                    restore_release_at_ms = None
                    if not illegal_recovery.awaiting_physical_restore:
                        illegal_recovery.awaiting_physical_restore = True
                        illegal_recovery.restored_at_ms = None

            if (
                illegal_recovery is not None
                and not illegal_recovery.awaiting_physical_restore
                and restore_release_at_ms is not None
                and now_ms >= restore_release_at_ms
            ):
                _push(log, f"Recovery complete: {illegal_recovery.piece_id} may move again.")
                illegal_recovery = None
                restore_release_at_ms = None
                sel.deselect()

            # ------------------------------------------------------------
            # Interactive phase handling
            # ------------------------------------------------------------
            if not game_over:
                phase = state.current_phase

                if (
                    illegal_recovery is None
                    and phase == Phase.MOVEMENT
                    and vision_snapshot is not None
                    and _is_snapshot_usable(vision_snapshot)
                ):
                    extra_reports = validate_no_extra_moves(
                        vision_snapshot.piece_cells,
                        state,
                        state.active_faction,
                    )
                    if extra_reports:
                        illegal_recovery = _build_illegal_recovery_for_report(extra_reports[0], now_ms)
                        for message in _messages_for_illegal_recovery(illegal_recovery):
                            _push(log, message)
                        sel.deselect()

                if illegal_recovery is None and phase == Phase.MOVEMENT:
                    msg = _handle_movement(
                        state,
                        sel,
                        confirm,
                        None if scanner is not None else click_node,
                    )
                    if msg:
                        _push(log, msg)

                    for event in vision_events:
                        messages, recovery = _handle_vision_movement(state, sel, event, now_ms)
                        for message in messages:
                            _push(log, message)
                        if recovery is not None:
                            illegal_recovery = recovery
                            sel.deselect()
                            break
                        if state.current_phase is not Phase.MOVEMENT:
                            break

                elif illegal_recovery is None and phase == Phase.ATTACK:
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
                    )
                    if msg:
                        _push(log, msg)

                # ── Drain any auto-phases that were triggered ────────────
                prev_round   = state.round_number
                prev_faction = state.active_faction

                game_over_ref[0] = game_over
                _drain_auto_phases(state, sel, log, game_over_ref)
                game_over = game_over_ref[0]

                # If the turn changed, log the new player's turn header
                if (state.round_number != prev_round
                        or state.active_faction != prev_faction):
                    new_faction = ("RED" if state.active_faction == Faction.RED
                                   else "BLACK")
                    _push(log, f"Round {state.round_number} — {new_faction}'s turn")

                if _is_game_over(state) and not game_over:
                    game_over = True

            # ------------------------------------------------------------
            # Render
            # ------------------------------------------------------------
            screen.fill((50, 40, 30))
            draw_board(screen)
            draw_dead_pieces(screen, state)
            draw_event_points(screen, state)

            if state.current_phase in (Phase.MOVEMENT, Phase.ATTACK):
                draw_highlights(
                    screen,
                    selected_pos  = sel.selected_pos,
                    valid_moves   = sel.valid_moves,
                    valid_attacks = sel.valid_attacks,
                )

            draw_pieces(
                screen,
                state,
                hidden_piece_ids=(
                    {illegal_recovery.piece_id}
                    if illegal_recovery is not None and not illegal_recovery.animation_finished(now_ms)
                    else None
                ),
                rollback_piece_id=illegal_recovery.piece_id if illegal_recovery is not None else None,
                rollback_from=illegal_recovery.illegal_pos if illegal_recovery is not None else None,
                rollback_to=illegal_recovery.legal_pos if illegal_recovery is not None else None,
                rollback_started_at_ms=(
                    illegal_recovery.animation_started_at_ms if illegal_recovery is not None else None
                ),
                rollback_duration_ms=(
                    illegal_recovery.animation_duration_ms if illegal_recovery is not None else None
                ),
                current_time_ms=now_ms,
            )

            btn_lbl = (
                "Skip Move  [Enter]"   if state.current_phase == Phase.MOVEMENT else
                "Skip Attack  [Enter]" if state.current_phase == Phase.ATTACK   else
                "…"
            )

            draw_panel(
                screen,
                state,
                log=log,
                btn_label=btn_lbl,
                btn_hover=btn_hover,
                instruction_override=(
                    _vision_instruction(scanner is not None, state.current_phase)
                    if illegal_recovery is None
                    else None
                ),
                status_lines=(
                    _active_illegal_status_lines(illegal_recovery, now_ms)
                    if illegal_recovery is not None
                    else None
                ),
            )

            if game_over:
                draw_victory_overlay(screen, state)

            pygame.display.flip()
            clock.tick(FPS)
    finally:
        if scanner is not None:
            scanner.close()
        pygame.quit()

    sys.exit(0)


if __name__ == "__main__":
    main()
