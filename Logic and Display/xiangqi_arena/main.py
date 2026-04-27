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
from xiangqi_arena.state.game_state import GameState, build_default_state

# ---------------------------------------------------------------------------
# UI / input imports
# ---------------------------------------------------------------------------
from xiangqi_arena.input_control.keyboard_handler import KeyAction, classify_key
from xiangqi_arena.input_control.selection_handler import (
    SelectionState, pixel_to_node,
)
from xiangqi_arena.ui import display_config
from xiangqi_arena.ui.board_renderer import draw_board, invalidate_board_image_cache
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
    draw_panel, draw_top_bar, draw_victory_overlay, reset_panel_fonts, sync_button_rects_from_config,
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LOG_MAX = 15   # side panel uses only the latest few anyway
LOG_HISTORY_MAX = 2000
WALK_ANIM_MS = 1500
VICTORY_OVERLAY_DELAY_MS = 500


def _piece_at(state: GameState, pos: tuple) -> str | None:
    return state.board._occupancy.get(pos)


def _is_game_over(state: GameState) -> bool:
    return state.victory_state != VictoryState.ONGOING


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
    pending_attack_ref: list[dict | None],
) -> str:
    active = state.active_faction

    if pending_attack_ref[0] is not None:
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
    pygame.init()
    screen = pygame.display.set_mode(
        (display_config.WINDOW_W, display_config.WINDOW_H),
        pygame.RESIZABLE,
    )
    pygame.display.set_caption(display_config.WINDOW_TITLE)
    clock  = pygame.time.Clock()

    state: GameState = build_default_state()
    start_turn(state)

    sel           = SelectionState()
    log: list[str] = []
    log_history: list[str] = []
    game_over_ref  = [False]
    pending_attack_ref: list[dict | None] = [None]
    pending_event_ref: list[dict | None] = [None]
    victory_overlay_ref: list[dict | None] = [None]

    # Drain the first START phase so we land on MOVEMENT immediately
    _drain_auto_phases(state, sel, log, log_history, game_over_ref, pending_event_ref)
    game_over = game_over_ref[0]

    # Announce whose turn it is at startup
    faction = "HUMANSIDE" if state.active_faction == Faction.HumanSide else "ORCSIDE"
    _push(log, f"Round {state.round_number} — {faction}'s turn", history=log_history)

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
            and state.current_phase in (Phase.MOVEMENT, Phase.ATTACK)
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
                if ka == KeyAction.CONFIRM:
                    confirm = True
                elif ka == KeyAction.CANCEL:
                    if game_over:
                        running = False
                    else:
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

        # ----------------------------------------------------------------
        # Interactive phase handling
        # ----------------------------------------------------------------
        if not game_over:
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

            elif phase == Phase.MOVEMENT:
                msg = _handle_movement(state, sel, confirm, click_node)
                if msg:
                    _push(log, msg, history=log_history)

            elif phase == Phase.ATTACK:
                if sel.has_selection and not sel.valid_attacks:
                    pid   = sel.selected_pid
                    piece = state.pieces.get(pid)
                    if piece and not piece.is_dead:
                        sel.valid_attacks = legal_attack_targets(piece, state)

                msg = _handle_attack(state, sel, confirm, click_node, pending_attack_ref)
                if msg:
                    _push(log, msg, history=log_history)

            # ── Drain any auto-phases that were triggered ────────────────
            prev_round   = state.round_number
            prev_faction = state.active_faction

            if pending_attack_ref[0] is None and pending_event_ref[0] is None:
                game_over_ref[0] = game_over
                _drain_auto_phases(state, sel, log, log_history, game_over_ref, pending_event_ref)
                game_over = game_over_ref[0]

            # If the turn changed, log the new player's turn header
            if (state.round_number != prev_round
                    or state.active_faction != prev_faction):
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
        screen.fill((50, 40, 30))
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

        draw_pieces(screen, state)
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
            "Skip Move  [Enter]"   if state.current_phase == Phase.MOVEMENT else
            "Skip Attack  [Enter]" if state.current_phase == Phase.ATTACK   else
            "…"
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
            selected_pid = sel.selected_pid,
            log_modal_open = log_modal_open,
            log_modal_scroll = log_modal_scroll,
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

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
