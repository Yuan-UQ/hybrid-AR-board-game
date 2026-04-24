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
from xiangqi_arena.rules.piece_rules import legal_attack_targets, legal_moves
from xiangqi_arena.rules.victory_rules import check_victory
from xiangqi_arena.state.game_state import GameState, build_default_state

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
from xiangqi_arena.ui.others import (
    BUTTON_RECT, DRAW_RECT, SURRENDER_RECT,
    draw_panel, draw_victory_overlay,
)
from xiangqi_arena.ui.piece_renderer import draw_pieces


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LOG_MAX = 15   # keep at most this many log entries


def _piece_at(state: GameState, pos: tuple) -> str | None:
    return state.board._occupancy.get(pos)


def _is_game_over(state: GameState) -> bool:
    return state.victory_state != VictoryState.ONGOING


def _try_surrender(state: GameState, log: list[str]) -> bool:
    """
    Current active player surrenders immediately.
    Returns True if the game is now over.
    """
    state.players[state.active_faction].has_surrendered = True
    state.victory_state = check_victory(state)
    faction_name = "RED" if state.active_faction == Faction.RED else "BLACK"
    _push(log, f"{faction_name} surrendered!")
    return _is_game_over(state)


def _try_draw(state: GameState, log: list[str]) -> bool:
    """
    Current active player requests / agrees to a draw.
    Returns True if the game is now over (DRAW).
    """
    player = state.players[state.active_faction]
    opponent = state.players[state.active_faction.opponent()]

    # If already requested, do nothing (waiting for opponent).
    if player.draw_requested and not opponent.draw_requested:
        _push(log, "Draw request already sent; waiting for opponent.")
        return False

    if not player.draw_requested:
        player.draw_requested = True
        if opponent.draw_requested:
            result = check_victory(state)
            if result == VictoryState.DRAW:
                state.victory_state = result
                _push(log, "Both sides agreed — DRAW!")
                return True
        faction_name = "RED" if state.active_faction == Faction.RED else "BLACK"
        _push(log, f"{faction_name} requests a draw.")
        return False

    # Both already requested (should have ended, but keep it robust)
    result = check_victory(state)
    if result == VictoryState.DRAW:
        state.victory_state = result
        _push(log, "Both sides agreed — DRAW!")
        return True
    return False


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

def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption(WINDOW_TITLE)
    clock  = pygame.time.Clock()

    state: GameState = build_default_state()
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

    running = True
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
            and state.current_phase in (Phase.MOVEMENT, Phase.ATTACK)
        )
        active_player = state.players[state.active_faction]
        opponent_player = state.players[state.active_faction.opponent()]

        if not can_action_buttons:
            draw_label = "Request Draw  [D]"
            draw_enabled = False
        else:
            if opponent_player.draw_requested and not active_player.draw_requested:
                draw_label = "Agree Draw  [D]"
                draw_enabled = True
            elif active_player.draw_requested and not opponent_player.draw_requested:
                draw_label = "Waiting…"
                draw_enabled = False
            elif active_player.draw_requested and opponent_player.draw_requested:
                draw_label = "DRAW"
                draw_enabled = False
            else:
                draw_label = "Request Draw  [D]"
                draw_enabled = True

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
                elif can_action_buttons and ev.key == pygame.K_s:
                    game_over = _try_surrender(state, log)
                elif can_action_buttons and ev.key == pygame.K_d:
                    game_over = _try_draw(state, log)

            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                if can_action_buttons and SURRENDER_RECT.collidepoint(mx, my):
                    game_over = _try_surrender(state, log)
                elif can_action_buttons and draw_enabled and DRAW_RECT.collidepoint(mx, my):
                    game_over = _try_draw(state, log)
                elif BUTTON_RECT.collidepoint(mx, my):
                    confirm = True
                else:
                    click_node = pixel_to_node(mx, my)

        # ----------------------------------------------------------------
        # Interactive phase handling
        # ----------------------------------------------------------------
        if not game_over:
            phase = state.current_phase

            if phase == Phase.MOVEMENT:
                msg = _handle_movement(state, sel, confirm, click_node)
                if msg:
                    _push(log, msg)

            elif phase == Phase.ATTACK:
                if sel.has_selection and not sel.valid_attacks:
                    pid   = sel.selected_pid
                    piece = state.pieces.get(pid)
                    if piece and not piece.is_dead:
                        sel.valid_attacks = legal_attack_targets(piece, state)

                msg = _handle_attack(state, sel, confirm, click_node)
                if msg:
                    _push(log, msg)

            # ── Drain any auto-phases that were triggered ────────────────
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

        # ----------------------------------------------------------------
        # Render
        # ----------------------------------------------------------------
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

        draw_pieces(screen, state)

        btn_lbl = (
            "Skip Move  [Enter]"   if state.current_phase == Phase.MOVEMENT else
            "Skip Attack  [Enter]" if state.current_phase == Phase.ATTACK   else
            "…"
        )

        draw_panel(
            screen, state,
            log       = log,
            btn_label = btn_lbl,
            btn_hover = btn_hover,
            surrender_hover = surrender_hover,
            surrender_enabled = can_action_buttons,
            draw_label = draw_label,
            draw_hover = draw_hover,
            draw_enabled = (can_action_buttons and draw_enabled),
        )

        if game_over:
            draw_victory_overlay(screen, state)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
