from __future__ import annotations

import pygame
import sys
import os
from PIL import Image

from xiangqi_arena.core.enums import EventPointType
from xiangqi_arena.models.event_point import EventPoint
from xiangqi_arena.recognition.aruco_tracker import VisionTracker
from xiangqi_arena.modification.attack import apply_attack
from xiangqi_arena.modification.event import apply_event_trigger
from xiangqi_arena.modification.move import apply_move
from xiangqi_arena.input_control.selection_handler import pixel_to_node
from xiangqi_arena.rules.piece_rules import legal_attack_targets, legal_moves
from xiangqi_arena.state.game_state import build_default_state
from xiangqi_arena.ui import display_config
from xiangqi_arena.ui.board_renderer import draw_board, draw_global_background
from xiangqi_arena.ui.event_renderer import draw_event_points
from xiangqi_arena.ui.highlight_renderer import draw_highlights
from xiangqi_arena.ui.others import GUIDE_RECT, draw_top_bar
from xiangqi_arena.ui.piece_renderer import draw_pieces


def _wrap(text: str, font: pygame.font.Font, width: int) -> list[str]:
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        test = w if not cur else f"{cur} {w}"
        if font.size(test)[0] <= width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


_TUTORIAL_GIF_CACHE: dict[tuple[str, int], list[pygame.Surface]] = {}


def _tutorial_asset_path(filename: str) -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "ArtResource",
        "Tutorial",
        filename,
    )


def _load_tutorial_gif(path: str, target_w: int) -> list[pygame.Surface]:
    key = (path, target_w)
    cached = _TUTORIAL_GIF_CACHE.get(key)
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
            scale = target_w / max(1, w)
            new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
            frame = frame.resize(new_size)

            surf = pygame.image.fromstring(
                frame.tobytes(),
                frame.size,
                frame.mode,
            ).convert_alpha()
            frames.append(surf)

            gif.seek(gif.tell() + 1)
    except EOFError:
        pass

    _TUTORIAL_GIF_CACHE[key] = frames
    return frames


def _draw_button(screen: pygame.Surface, rect: pygame.Rect, label: str, *, hovered: bool) -> None:
    bg = (58, 68, 105) if hovered else (47, 54, 86)
    pygame.draw.rect(screen, bg, rect, border_radius=8)
    pygame.draw.rect(screen, (176, 152, 102), rect, width=1, border_radius=8)
    f = pygame.font.Font(None, max(20, int(24 * display_config.UI_SCALE)))
    f.set_bold(True)
    t = f.render(label, True, (232, 224, 207))
    screen.blit(t, (rect.centerx - t.get_width() // 2, rect.centery - t.get_height() // 2))


def _draw_demo_panel(
    screen: pygame.Surface,
    rect: pygame.Rect,
    *,
    side_label: str,
    active: bool,
    step: int,
    gif_names: tuple[str, str] | None = None,
) -> None:
    panel_bg = (31, 36, 58) if active else (24, 28, 44)
    is_human_side = side_label == "HumanSide"
    if active and is_human_side:
        border = (236, 90, 90)
        title_color = (255, 172, 172)
        hint_color = (244, 150, 150)
        status_color = (255, 168, 168)
    elif active:
        border = (244, 206, 94)
        title_color = (255, 226, 132)
        hint_color = (238, 188, 120)
        status_color = (255, 226, 132)
    else:
        border = (92, 100, 132)
        title_color = (196, 202, 220)
        hint_color = (150, 156, 178)
        status_color = (176, 182, 204)

    pygame.draw.rect(screen, panel_bg, rect, border_radius=12)
    pygame.draw.rect(screen, border, rect, width=2, border_radius=12)

    pad = max(10, int(12 * display_config.UI_SCALE))
    title_font = pygame.font.Font(None, max(18, int(22 * display_config.UI_SCALE)))
    body_font = pygame.font.Font(None, max(16, int(20 * display_config.UI_SCALE)))
    small_font = pygame.font.Font(None, max(14, int(17 * display_config.UI_SCALE)))
    title_font.set_bold(True)
    body_font.set_bold(True)

    tx = rect.x + pad
    ty = rect.y + pad

    title = title_font.render(side_label, True, title_color)
    screen.blit(title, (tx, ty))
    ty += title.get_height() + 4

    step_text = f"Step {step:02d}" if step <= 8 else "Completed"
    step_surf = small_font.render(step_text, True, hint_color)
    screen.blit(step_surf, (tx, ty))

    if gif_names is not None:
        gif_w = rect.width - pad * 2
        top_gif = _load_tutorial_gif(_tutorial_asset_path(gif_names[0]), gif_w)
        bottom_gif = _load_tutorial_gif(_tutorial_asset_path(gif_names[1]), gif_w)

        gif_y = ty + 14
        frame_tick = pygame.time.get_ticks() // 90

        if top_gif:
            frame = top_gif[frame_tick % len(top_gif)]
            if gif_y + frame.get_height() < rect.bottom - 90:
                screen.blit(frame, (rect.centerx - frame.get_width() // 2, gif_y))
                gif_y += frame.get_height() + 12

        if bottom_gif:
            frame = bottom_gif[frame_tick % len(bottom_gif)]
            max_h = rect.bottom - 70 - gif_y
            if max_h > 30:
                if frame.get_height() > max_h:
                    scale = max_h / max(1, frame.get_height())
                    frame = pygame.transform.smoothscale(
                        frame,
                        (int(frame.get_width() * scale), int(frame.get_height() * scale)),
                    )
                screen.blit(frame, (rect.centerx - frame.get_width() // 2, gif_y))

    status = "ACTIVE SIDE" if active else "WAITING"
    status_surf = small_font.render(status, True, status_color)
    screen.blit(status_surf, (tx, rect.bottom - pad - status_surf.get_height()))


def _fmt_node(pos: tuple[int, int]) -> str:
    """Format internal (x, y) as on-screen board-style (col, row)."""
    return f"({int(pos[1])}, {int(pos[0])})"


def _pick_first_legal_move(piece_id: str, state, *, avoid: set[tuple[int, int]] | None = None) -> tuple[int, int]:
    moves = sorted(legal_moves(state.pieces[piece_id], state))
    avoid = avoid or set()
    for m in moves:
        if m not in avoid:
            return m
    if not moves:
        raise RuntimeError(f"No legal moves for tutorial piece {piece_id}")
    return moves[0]


def _build_tutorial_state():
    # Start from the same standard initial deployment as setup-complete state.
    state = build_default_state()
    movement_piece_id = "Soldier1Human"
    orc_select_piece_id = "Soldier1Orc"
    event_piece_id = "WizardHuman"
    orc_event_piece_id = "Soldier2Skeleton"

    movement_target = _pick_first_legal_move(movement_piece_id, state)
    apply_move(movement_piece_id, movement_target, state)

    orc_move_target = _pick_first_legal_move(orc_select_piece_id, state)
    apply_move(orc_select_piece_id, orc_move_target, state)

    if orc_move_target not in legal_attack_targets(state.pieces[movement_piece_id], state):
        raise RuntimeError("Tutorial path invalid: Human attack target not legal after movement steps.")
    if movement_target not in legal_attack_targets(state.pieces[orc_select_piece_id], state):
        raise RuntimeError("Tutorial path invalid: Orc attack target not legal after movement steps.")

    # Revert temporary movement simulation; runtime steps will apply them again.
    state = build_default_state()

    med_target = _pick_first_legal_move(event_piece_id, state)
    ammo_target = _pick_first_legal_move(orc_event_piece_id, state, avoid={med_target})
    trap_target = (5, 4) if (5, 4) not in {med_target, ammo_target} else (4, 4)

    fixed_event_positions = {
        "Medical": med_target,
        "Ammunition": ammo_target,
        "Trap": trap_target,
    }
    state.event_points = [
        EventPoint(EventPointType.MEDICAL, fixed_event_positions["Medical"], spawn_round=state.round_number),
        EventPoint(EventPointType.AMMUNITION, fixed_event_positions["Ammunition"], spawn_round=state.round_number),
        EventPoint(EventPointType.TRAP, fixed_event_positions["Trap"], spawn_round=state.round_number),
    ]
    return state, fixed_event_positions


def run_tutorial_mode(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    *,
    vision_tracker: VisionTracker | None = None,
    vision_sync_ms: int = 100,
) -> pygame.Surface:
    tutorial_state, fixed_event_positions = _build_tutorial_state()

    tutorial_step = 1
    selected_piece = ""
    error_message = ""
    success_message = ""

    movement_piece_id = "Soldier1Human"
    attack_piece_id = "Soldier1Human"
    event_piece_id = "WizardHuman"
    orc_select_piece_id = "Soldier1Orc"
    orc_event_piece_id = "Soldier2Skeleton"
    origin_pos: tuple[int, int] | None = None

    movement_target = _pick_first_legal_move(movement_piece_id, tutorial_state)
    orc_move_target = _pick_first_legal_move(orc_select_piece_id, tutorial_state)
    attack_target = orc_move_target
    orc_attack_target = movement_target
    medical_target = fixed_event_positions["Medical"]
    ammo_target = fixed_event_positions["Ammunition"]
    attack_piece_selected = False
    orc_attack_piece_selected = False
    human_event_piece_selected = False
    orc_event_piece_selected = False
    next_vision_sync_ms = 0
    vision_select_prev: set[tuple[int, int]] = set()
    guide_open = False
    guide_clickable_rects: dict[str, object] = {}
    guide_section_idx = 0
    guide_page_by_section: dict[str, int] = {}

    def _main_guide_hooks():
        main_mod = sys.modules.get("__main__")
        if main_mod is None:
            return None, None, ()
        draw_fn = getattr(main_mod, "_draw_game_guide_panel", None)
        click_fn = getattr(main_mod, "_apply_guide_click", None)
        sections = getattr(main_mod, "GUIDE_SECTIONS", ())
        if callable(draw_fn) and callable(click_fn):
            return draw_fn, click_fn, sections
        return None, None, ()

    _draw_guide_panel, _apply_guide_click, _guide_sections = _main_guide_hooks()
    _rebuild_ui_after_resize = getattr(sys.modules.get("__main__"), "_rebuild_ui_after_window_resize", None)
    if _guide_sections:
        guide_page_by_section = {section: 0 for section in _guide_sections}

    def _handle_tutorial_node(click_node: tuple[int, int] | None) -> None:
        nonlocal tutorial_step
        nonlocal selected_piece
        nonlocal error_message
        nonlocal success_message
        nonlocal origin_pos
        nonlocal attack_piece_selected
        nonlocal orc_attack_piece_selected
        nonlocal human_event_piece_selected
        nonlocal orc_event_piece_selected

        error_message = ""
        success_message = ""

        if tutorial_step == 1:
            if click_node == tutorial_state.pieces[movement_piece_id].pos:
                selected_piece = movement_piece_id
                origin_pos = tuple(tutorial_state.pieces[movement_piece_id].pos)
                tutorial_step = 2
                success_message = f"{movement_piece_id} selected."
            else:
                error_message = "Please select the highlighted piece."

        elif tutorial_step == 2:
            piece = tutorial_state.pieces[movement_piece_id]
            if click_node == movement_target and click_node in legal_moves(piece, tutorial_state):
                apply_move(movement_piece_id, movement_target, tutorial_state)
                selected_piece = movement_piece_id
                tutorial_step = 3
                success_message = "Movement successful."
            else:
                error_message = "Please select the green highlighted position."

        elif tutorial_step == 3:
            if click_node == tutorial_state.pieces[orc_select_piece_id].pos:
                selected_piece = orc_select_piece_id
                origin_pos = tuple(tutorial_state.pieces[orc_select_piece_id].pos)
                tutorial_step = 4
                success_message = f"{orc_select_piece_id} selected."
            else:
                error_message = "Please select the highlighted piece."

        elif tutorial_step == 4:
            piece = tutorial_state.pieces[orc_select_piece_id]
            if click_node == orc_move_target and click_node in legal_moves(piece, tutorial_state):
                apply_move(orc_select_piece_id, orc_move_target, tutorial_state)
                selected_piece = attack_piece_id
                tutorial_step = 5
                success_message = "Movement successful."
            else:
                error_message = "Please select the green highlighted position."

        elif tutorial_step == 5:
            piece = tutorial_state.pieces[attack_piece_id]
            if not attack_piece_selected:
                if click_node == piece.pos:
                    attack_piece_selected = True
                    selected_piece = attack_piece_id
                    origin_pos = tuple(piece.pos)
                    success_message = "Piece selected. Now select the red attack target."
                else:
                    error_message = "Please select the highlighted piece."
            else:
                if click_node == attack_target and click_node in legal_attack_targets(piece, tutorial_state):
                    apply_attack(attack_piece_id, attack_target, tutorial_state)
                    selected_piece = orc_select_piece_id
                    tutorial_step = 6
                    attack_piece_selected = False
                    success_message = "Attack resolved."
                else:
                    error_message = "This target is not attackable."

        elif tutorial_step == 6:
            piece = tutorial_state.pieces.get(orc_select_piece_id)
            if piece is None or piece.is_dead:
                error_message = "This target is not attackable."
            else:
                if not orc_attack_piece_selected:
                    if click_node == piece.pos:
                        orc_attack_piece_selected = True
                        selected_piece = orc_select_piece_id
                        origin_pos = tuple(piece.pos)
                        success_message = "Piece selected. Now select the red attack target."
                    else:
                        error_message = "Please select the highlighted piece."
                elif click_node == orc_attack_target and click_node in legal_attack_targets(piece, tutorial_state):
                    apply_attack(orc_select_piece_id, orc_attack_target, tutorial_state)
                    selected_piece = event_piece_id
                    tutorial_step = 7
                    orc_attack_piece_selected = False
                    success_message = "Attack resolved."
                else:
                    error_message = "This target is not attackable."

        elif tutorial_step == 7:
            piece = tutorial_state.pieces[event_piece_id]
            if not human_event_piece_selected:
                if click_node == piece.pos:
                    human_event_piece_selected = True
                    selected_piece = event_piece_id
                    origin_pos = tuple(piece.pos)
                    success_message = "Piece selected. Now select the event point."
                else:
                    error_message = "Please select the highlighted piece."
            else:
                if click_node == medical_target and click_node in legal_moves(piece, tutorial_state):
                    apply_move(event_piece_id, medical_target, tutorial_state)
                    medical_ep = next(
                        (ep for ep in tutorial_state.event_points if ep.is_valid and ep.pos == medical_target),
                        None,
                    )
                    if medical_ep is not None:
                        apply_event_trigger(event_piece_id, medical_ep, tutorial_state, spawn_heal_effect=False)
                    selected_piece = orc_event_piece_id
                    tutorial_step = 8
                    human_event_piece_selected = False
                    success_message = "Event triggered."
                else:
                    error_message = "Please select the highlighted event point."

        elif tutorial_step == 8:
            piece = tutorial_state.pieces[orc_event_piece_id]
            if not orc_event_piece_selected:
                if click_node == piece.pos:
                    orc_event_piece_selected = True
                    selected_piece = orc_event_piece_id
                    origin_pos = tuple(piece.pos)
                    success_message = "Piece selected. Now select the event point."
                else:
                    error_message = "Please select the highlighted piece."
            else:
                if click_node == ammo_target and click_node in legal_moves(piece, tutorial_state):
                    apply_move(orc_event_piece_id, ammo_target, tutorial_state)
                    ammo_ep = next(
                        (ep for ep in tutorial_state.event_points if ep.is_valid and ep.pos == ammo_target),
                        None,
                    )
                    if ammo_ep is not None:
                        apply_event_trigger(orc_event_piece_id, ammo_ep, tutorial_state, spawn_heal_effect=False)
                    tutorial_step = 9
                    orc_event_piece_selected = False
                    success_message = "Event triggered."
                else:
                    error_message = "Please select the highlighted event point."

    while True:
        mouse_pos = pygame.mouse.get_pos()

        bottom_rect = pygame.Rect(
            display_config.HUD_MARGIN,
            display_config.BOTTOM_PANEL_Y,
            display_config.BOTTOM_PANEL_W,
            display_config.BOTTOM_PANEL_H,
        )
        info_rect = bottom_rect.inflate(-24, -20)
        button_font = pygame.font.Font(None, max(20, int(24 * display_config.UI_SCALE)))
        button_font.set_bold(True)
        exit_label = "Exit Tutorial (Esc)"
        exit_w = max(120, button_font.size(exit_label)[0] + 22)
        exit_rect = pygame.Rect(info_rect.right - (exit_w + 12), info_rect.y, exit_w, 32)
        finish_rect = pygame.Rect(info_rect.right - 174, info_rect.bottom - 40, 162, 34)

        if not guide_open:
            is_hovering_button = GUIDE_RECT.collidepoint(mouse_pos)
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
                return screen
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                if guide_open:
                    guide_open = False
                    continue
                return screen
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN and tutorial_step == 9:
                if guide_open:
                    continue
                return screen
            if ev.type == pygame.VIDEORESIZE:
                w, h = int(ev.w), int(ev.h)
                if w > 0 and h > 0:
                    if callable(_rebuild_ui_after_resize):
                        screen = _rebuild_ui_after_resize(w, h)
                    else:
                        display_config.apply_layout_for_window_size(w, h)
                        screen = pygame.display.set_mode(
                            (display_config.WINDOW_W, display_config.WINDOW_H),
                            pygame.RESIZABLE,
                        )
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if (
                    guide_open
                    and _apply_guide_click is not None
                    and _guide_sections
                ):
                    guide_section_idx, should_close = _apply_guide_click(
                        ev.pos,
                        guide_section_idx,
                        guide_page_by_section,
                        guide_clickable_rects,
                    )
                    if should_close:
                        guide_open = False
                    continue
                if GUIDE_RECT.collidepoint(ev.pos) and _draw_guide_panel is not None:
                    guide_open = True
                    continue
                if not guide_open:
                    click_node = pixel_to_node(ev.pos[0], ev.pos[1])
                    _handle_tutorial_node(click_node)

        if vision_tracker is not None and tutorial_step <= 8:
            now_ms = pygame.time.get_ticks()
            if now_ms >= next_vision_sync_ms:
                vision_status = vision_tracker.read_positions(
                    frozenset(p.id for p in tutorial_state.pieces.values() if p.is_dead),
                )
                next_vision_sync_ms = now_ms + max(1, int(vision_sync_ms))
                select_cells = set(tuple(c) for c in (vision_status.selection_cells or ()))
                new_cells = sorted(c for c in select_cells if c not in vision_select_prev)
                if new_cells:
                    _handle_tutorial_node(tuple(new_cells[0]))
                vision_select_prev = select_cells

        draw_global_background(screen)
        guide_hover = GUIDE_RECT.collidepoint(mouse_pos)
        draw_top_bar(screen, guide_hover=guide_hover, setup_stage_label="Tutorial Stage")
        draw_board(screen)
        draw_event_points(screen, tutorial_state, draw_heal_effects=False)
        tutorial_highlight_piece_ids: set[str] = set()
        if tutorial_step in {1, 2}:
            tutorial_highlight_piece_ids.add(movement_piece_id)
        elif tutorial_step in {3, 4, 6}:
            if orc_select_piece_id in tutorial_state.pieces and not tutorial_state.pieces[orc_select_piece_id].is_dead:
                tutorial_highlight_piece_ids.add(orc_select_piece_id)
        elif tutorial_step == 5:
            tutorial_highlight_piece_ids.add(attack_piece_id)
        elif tutorial_step == 7:
            tutorial_highlight_piece_ids.add(event_piece_id)
        elif tutorial_step == 8:
            tutorial_highlight_piece_ids.add(orc_event_piece_id)

        draw_pieces(
            screen,
            tutorial_state,
            visible_piece_ids=set(p.id for p in tutorial_state.pieces.values() if not p.is_dead),
            setup_wrong_position_ids=tutorial_highlight_piece_ids,
        )

        selected_pos = tutorial_state.pieces[selected_piece].pos if selected_piece in tutorial_state.pieces else None
        show_selected_arrow = True
        valid_moves: list[tuple[int, int]] = []
        valid_attacks: list[tuple[int, int]] = []
        if tutorial_step == 1:
            show_selected_arrow = False
        elif tutorial_step == 2:
            p = tutorial_state.pieces[movement_piece_id]
            valid_moves = legal_moves(p, tutorial_state)
        elif tutorial_step == 3:
            show_selected_arrow = False
        elif tutorial_step == 4:
            p = tutorial_state.pieces[orc_select_piece_id]
            valid_moves = legal_moves(p, tutorial_state)
        elif tutorial_step == 5:
            p = tutorial_state.pieces[attack_piece_id]
            if attack_piece_selected:
                valid_attacks = legal_attack_targets(p, tutorial_state)
            else:
                selected_pos = None
                show_selected_arrow = False
        elif tutorial_step == 6:
            p = tutorial_state.pieces.get(orc_select_piece_id)
            if p is not None and not p.is_dead:
                if orc_attack_piece_selected:
                    valid_attacks = legal_attack_targets(p, tutorial_state)
                else:
                    selected_pos = None
                    show_selected_arrow = False
        elif tutorial_step == 7:
            p = tutorial_state.pieces[event_piece_id]
            if human_event_piece_selected:
                valid_moves = legal_moves(p, tutorial_state)
            else:
                selected_pos = None
                show_selected_arrow = False
        elif tutorial_step == 8:
            p = tutorial_state.pieces[orc_event_piece_id]
            if orc_event_piece_selected:
                valid_moves = legal_moves(p, tutorial_state)
            else:
                selected_pos = None
                show_selected_arrow = False
        elif tutorial_step == 9:
            show_selected_arrow = False

        draw_highlights(
            screen,
            selected_pos=selected_pos,
            valid_moves=valid_moves,
            valid_attacks=valid_attacks,
            show_attack_effect=False,
            attack_arrow_nodes=valid_attacks,
            show_selected_arrow=show_selected_arrow,
        )

        active_side = None
        if tutorial_step in {1, 2, 5, 7}:
            active_side = "HumanSide"
        elif tutorial_step in {3, 4, 6, 8}:
            active_side = "OrcSide"
        
        left_gifs = None
        right_gifs = None

        if tutorial_step == 1:
            right_gifs = ("Selection1.gif", "Selection.gif")
        elif tutorial_step == 2:
            right_gifs = ("Movement1.gif", "Movement.gif")
        elif tutorial_step == 3:
            left_gifs = ("Selection1.gif", "Selection.gif")
        elif tutorial_step == 4:
            left_gifs = ("Movement1.gif", "Movement.gif")
        elif tutorial_step == 5:
            right_gifs = ("Attack1.gif", "Attack.gif")
        elif tutorial_step == 6:
            left_gifs = ("Attack1.gif", "Attack.gif")
        elif tutorial_step == 7:
            right_gifs = ("Movement1.gif", "Movement.gif")
        elif tutorial_step == 8:
            left_gifs = ("Movement1.gif", "Movement.gif")

        left_demo_rect = pygame.Rect(
            display_config.LEFT_PANEL_X,
            display_config.SIDE_PANEL_Y,
            display_config.SIDE_PANEL_W,
            display_config.SIDE_PANEL_H,
        )
        right_demo_rect = pygame.Rect(
            display_config.RIGHT_PANEL_X,
            display_config.SIDE_PANEL_Y,
            display_config.SIDE_PANEL_W,
            display_config.SIDE_PANEL_H,
        )
        _draw_demo_panel(
            screen,
            left_demo_rect,
            side_label="OrcSide",
            active=active_side == "OrcSide",
            step=tutorial_step,
            gif_names=left_gifs,
        )
        _draw_demo_panel(
            screen,
            right_demo_rect,
            side_label="HumanSide",
            active=active_side == "HumanSide",
            step=tutorial_step,
            gif_names=right_gifs,
        )

        pygame.draw.rect(screen, (24, 26, 44), bottom_rect, border_radius=12)
        pygame.draw.rect(screen, (148, 126, 82), bottom_rect, width=2, border_radius=12)

        title_font = pygame.font.Font(None, max(23, int(27 * display_config.UI_SCALE)))
        body_font = pygame.font.Font(None, max(19, int(23 * display_config.UI_SCALE)))
        title_font.set_bold(True)
        body_font.set_bold(True)

        step_titles = {
            1: "Step 1: Human Piece Selection",
            2: "Step 2: Human Movement Practice",
            3: "Step 3: Orc Piece Selection",
            4: "Step 4: Orc Movement Practice",
            5: "Step 5: Human Attack Practice",
            6: "Step 6: Orc Attack Practice",
            7: "Step 7: Special Event Practice - Human",
            8: "Step 8: Special Event Practice - Orc",
            9: "Step 9: Tutorial Completion",
        }
        stage_labels = {
            1: ("SELECTION TUTORIAL", (255, 223, 120)),
            2: ("MOVEMENT TUTORIAL", (110, 230, 146)),
            3: ("SELECTION TUTORIAL", (255, 223, 120)),
            4: ("MOVEMENT TUTORIAL", (110, 230, 146)),
            5: ("ATTACK TUTORIAL", (255, 126, 126)),
            6: ("ATTACK TUTORIAL", (255, 126, 126)),
            7: ("EVENT TUTORIAL", (124, 186, 255)),
            8: ("EVENT TUTORIAL", (124, 186, 255)),
            9: ("TUTORIAL COMPLETE", (174, 238, 160)),
        }
        step_instructions = {
            1: f"Side: Human | Piece: {movement_piece_id} | Select the highlighted piece.",
            2: (
                f"Side: Human | Move {movement_piece_id} from "
                f"{_fmt_node((6, 6))} to {_fmt_node(movement_target)}. "
                "Move to the highlighted green position."
            ),
            3: f"Side: Orc | Piece: {orc_select_piece_id} | Select the highlighted piece.",
            4: (
                f"Side: Orc | Move {orc_select_piece_id} from "
                f"{_fmt_node((3, 6))} to {_fmt_node(orc_move_target)}. "
                "Move to the highlighted green position."
            ),
            5: (
                f"Side: Human | Use {attack_piece_id}. Select the piece first, "
                f"then attack red target {_fmt_node(attack_target)}."
            ),
            6: (
                f"Side: Orc | Use {orc_select_piece_id}. Select the piece first, "
                f"then attack red target {_fmt_node(orc_attack_target)}."
            ),
            7: (
                f"Side: Human | Use {event_piece_id}. Select the piece first, "
                f"then move to Medical {_fmt_node(medical_target)}."
            ),
            8: (
                f"Side: Orc | Use {orc_event_piece_id}. Select the piece first, "
                f"then move to Ammunition {_fmt_node(ammo_target)}."
            ),
            9: "Tutorial completed. Movement, attack and event flow have been demonstrated. Press Enter to finish.",
        }

        tx = info_rect.x
        ty = info_rect.y
        stage_text, stage_color = stage_labels[tutorial_step]
        stage_font = pygame.font.Font(None, max(24, int(28 * display_config.UI_SCALE)))
        stage_font.set_bold(True)
        stage = stage_font.render(stage_text, True, stage_color)
        screen.blit(stage, (tx, ty))
        ty += stage.get_height() + 2
        title = title_font.render(step_titles[tutorial_step], True, (232, 224, 207))
        screen.blit(title, (tx, ty))
        ty += title.get_height() + 4
        for line in _wrap(step_instructions[tutorial_step], body_font, info_rect.width - 180):
            s = body_font.render(line, True, (216, 209, 194))
            screen.blit(s, (tx, ty))
            ty += s.get_height() + 2

        if success_message:
            ok = body_font.render(success_message, True, (108, 224, 132))
            screen.blit(ok, (tx, min(info_rect.bottom - 28, ty + 4)))
        elif error_message:
            err = body_font.render(error_message, True, (244, 156, 116))
            screen.blit(err, (tx, min(info_rect.bottom - 28, ty + 4)))

        _draw_button(screen, exit_rect, "Exit Tutorial (Esc)", hovered=False)
        if tutorial_step == 9:
            _draw_button(screen, finish_rect, "Finish Tutorial (Enter)", hovered=False)
        if guide_open and _draw_guide_panel is not None:
            _draw_guide_panel(
                screen,
                selected_section_idx=guide_section_idx,
                page_index_by_section=guide_page_by_section,
                clickable_rects=guide_clickable_rects,
            )

        pygame.display.flip()
        clock.tick(display_config.FPS)
