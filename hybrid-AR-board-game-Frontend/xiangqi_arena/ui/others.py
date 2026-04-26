"""
HUD rendering.

Layout:
  - Left panel  : OrcSide roster cards
  - Right panel : HumanSide roster cards
  - Bottom panel: game status, events, log, skip button
"""

from __future__ import annotations

import pygame

from xiangqi_arena.core.enums import Faction, Phase, VictoryState
from xiangqi_arena.rules.buff_rules import (
    get_attack_bonus,
    get_base_attack,
    get_defence_bonus,
    get_permanent_attack_bonus,
)
from xiangqi_arena.state.game_state import GameState
from xiangqi_arena.ui import piece_renderer
from xiangqi_arena.ui.display_config import (
    C_AMMO, C_ORCSIDE_LABEL, C_BTN_BG, C_BTN_HOVER, C_BTN_TEXT,
    C_HP_EMPTY, C_HP_FULL, C_MED, C_MSG_TEXT, C_MUTED, C_PANEL_BG,
    C_PANEL_BORDER, C_PANEL_TEXT, C_HUMANSIDE_LABEL, C_TRAP,
    C_VICTORY_ORCSIDE, C_VICTORY_DRAW, C_VICTORY_HUMANSIDE,
    BOTTOM_PANEL_H, BOTTOM_PANEL_W, BOTTOM_PANEL_X, BOTTOM_PANEL_Y,
    LEFT_PANEL_X, PANEL_PAD, RIGHT_PANEL_X, SIDE_PANEL_H, SIDE_PANEL_W,
    SIDE_PANEL_Y, WINDOW_H, WINDOW_W,
)
from xiangqi_arena.core.enums import EventPointType

# Button rect (computed once)
BTN_W  = 220
BTN_H  = 36
BTN_X  = BOTTOM_PANEL_X + BOTTOM_PANEL_W - BTN_W - PANEL_PAD
BTN_Y  = BOTTOM_PANEL_Y + BOTTOM_PANEL_H - BTN_H - PANEL_PAD

BUTTON_RECT = pygame.Rect(BTN_X, BTN_Y, BTN_W, BTN_H)

_PHASE_INSTRUCTIONS: dict[Phase, str] = {
    Phase.START:       "",   # auto-processed, no instruction needed
    Phase.MOVEMENT:    "Click a piece → click green node  |  Enter = skip",
    Phase.RECOGNITION: "",   # auto-processed
    Phase.ATTACK:      "Click a HumanSide target to attack  |  Enter = skip",
    Phase.RESOLVE:     "",   # auto-processed
}

_PHASE_NAMES: dict[Phase, str] = {
    Phase.START:       "START",
    Phase.MOVEMENT:    "MOVEMENT",
    Phase.RECOGNITION: "RECOGNITION",
    Phase.ATTACK:      "ATTACK",
    Phase.RESOLVE:     "RESOLVE",
}

_FONT_TITLE:   pygame.font.Font | None = None
_FONT_BODY:    pygame.font.Font | None = None
_FONT_SMALL:   pygame.font.Font | None = None
_FONT_BTN:     pygame.font.Font | None = None
_FONT_CARD:    pygame.font.Font | None = None
_FONT_X:       pygame.font.Font | None = None
_STATUS_DEATH_LOCKED: set[str] = set()


def _fonts() -> tuple:
    global _FONT_TITLE, _FONT_BODY, _FONT_SMALL, _FONT_BTN, _FONT_CARD, _FONT_X
    if _FONT_TITLE is None:
        _FONT_TITLE = pygame.font.Font(None, 24)
        _FONT_TITLE.set_bold(True)
        _FONT_BODY  = pygame.font.Font(None, 20)
        _FONT_SMALL = pygame.font.Font(None, 16)
        _FONT_BTN   = pygame.font.Font(None, 20)
        _FONT_BTN.set_bold(True)
        _FONT_CARD  = pygame.font.Font(None, 18)
        _FONT_CARD.set_bold(True)
        _FONT_X = pygame.font.Font(None, 34)
        _FONT_X.set_bold(True)
    return _FONT_TITLE, _FONT_BODY, _FONT_SMALL, _FONT_BTN, _FONT_CARD, _FONT_X


def _draw_panel_box(screen: pygame.Surface, rect: pygame.Rect) -> None:
    pygame.draw.rect(screen, C_PANEL_BG, rect, border_radius=12)
    pygame.draw.rect(screen, C_PANEL_BORDER, rect, width=2, border_radius=12)


def _draw_event_info_row(
    screen: pygame.Surface,
    event_type: EventPointType,
    pos: tuple[int, int],
    x: int,
    y: int,
    font: pygame.font.Font,
) -> int:
    icon_cx = x + 10
    icon_cy = y + 10
    icon_unit = 2

    if event_type == EventPointType.AMMUNITION:
        colour = C_AMMO
        layout = {
            -2: [0],
            -1: [-1, 0, 1],
            0: [-2, -1, 0, 1, 2],
            1: [-1, 0, 1],
            2: [0],
        }
        _draw_pixel_icon(screen, icon_cx, icon_cy, icon_unit, layout, colour)
        text = f"Attack Boost (+2 ATK) at {pos}"
    elif event_type == EventPointType.MEDICAL:
        colour = C_MED
        layout = {
            -2: [0],
            -1: [0],
            0: [-2, -1, 0, 1, 2],
            1: [0],
            2: [0],
        }
        _draw_pixel_icon(screen, icon_cx, icon_cy, icon_unit, layout, colour)
        text = f"Healing Spot (+1 HP) at {pos}"
    else:
        colour = C_TRAP
        layout = {
            -2: [-2, 2],
            -1: [-1, 1],
            0: [0],
            1: [-1, 1],
            2: [-2, 2],
        }
        _draw_pixel_icon(screen, icon_cx, icon_cy, icon_unit, layout, colour)
        text = f"Trap Tile (-1 HP) at {pos}"

    text_surf = font.render(text, True, C_PANEL_TEXT)
    screen.blit(text_surf, (x + 24, y))
    return y + max(22, text_surf.get_height() + 3)


def _draw_pixel_icon(
    screen: pygame.Surface,
    cx: int,
    cy: int,
    unit: int,
    layout: dict[int, list[int]],
    colour: tuple[int, int, int],
) -> None:
    pixels = {(gx, gy) for gy, row in layout.items() for gx in row}
    for gx, gy in pixels:
        rect = pygame.Rect(cx + gx * unit, cy + gy * unit, unit, unit)
        pygame.draw.rect(screen, colour, rect)
    for gx, gy in pixels:
        if (
            (gx - 1, gy) not in pixels
            or (gx + 1, gy) not in pixels
            or (gx, gy - 1) not in pixels
            or (gx, gy + 1) not in pixels
        ):
            rect = pygame.Rect(cx + gx * unit, cy + gy * unit, unit, unit)
            pygame.draw.rect(screen, (240, 240, 240), rect, width=1)


def _piece_order_for(faction: Faction, state: GameState) -> list:
    return [p for p in state.pieces.values() if p.faction == faction]


def _idle_frame(piece_id: str) -> pygame.Surface | None:
    if piece_id not in piece_renderer._SPRITE_CONFIG:
        return None
    frames = piece_renderer._get_sprite_frames(piece_id, "Idle")
    if not frames:
        return None
    frame_idx = (pygame.time.get_ticks() // 140) % len(frames)
    return frames[int(frame_idx)]


def _status_panel_frame(piece) -> pygame.Surface | None:
    if piece.id not in piece_renderer._SPRITE_CONFIG:
        return None

    animation = piece_renderer._active_sprite_animation(piece.id)
    dead = piece.is_dead or piece.hp <= 0
    if not dead:
        _STATUS_DEATH_LOCKED.discard(piece.id)
    if dead:
        death_frames = piece_renderer._get_sprite_frames(piece.id, "Death")
        if not death_frames:
            return _idle_frame(piece.id)
        if piece.id in _STATUS_DEATH_LOCKED:
            return death_frames[-1]
        if animation is not None and str(animation.get("name")) == "Death":
            elapsed = pygame.time.get_ticks() - int(animation.get("started_at", 0))
            duration = int(animation.get("duration_ms", 0))
            if duration > 0 and elapsed >= duration:
                _STATUS_DEATH_LOCKED.add(piece.id)
                return death_frames[-1]
            return piece_renderer._sprite_frame(piece.id, animation)
        _STATUS_DEATH_LOCKED.add(piece.id)
        return death_frames[-1]

    if animation is None:
        return _idle_frame(piece.id)
    return piece_renderer._sprite_frame(piece.id, animation)


def _draw_piece_card(
    screen: pygame.Surface,
    piece,
    state: GameState,
    rect: pygame.Rect,
    f_card: pygame.font.Font,
    f_small: pygame.font.Font,
    f_x: pygame.font.Font,
    is_selected: bool = False,
) -> None:
    card_bg = (34, 34, 55)
    card_border = (255, 220, 70) if is_selected else C_PANEL_BORDER
    text_color = C_PANEL_TEXT
    pygame.draw.rect(screen, card_bg, rect, border_radius=8)
    pygame.draw.rect(screen, card_border, rect, width=2 if is_selected else 1, border_radius=8)

    name = f_card.render(piece.id, True, text_color)
    screen.blit(name, (rect.x + 8, rect.y + 6))

    sprite_box = pygame.Rect(rect.x + 8, rect.y + 26, rect.width - 16, max(22, rect.height - 58))
    frame = _status_panel_frame(piece)
    if frame is not None:
        max_h = max(18, sprite_box.height - 4)
        scale = min(1.0, max_h / max(1, frame.get_height()))
        draw_w = max(1, int(frame.get_width() * scale * 1.5))
        draw_h = max(1, int(frame.get_height() * scale * 1.5))
        draw_frame = pygame.transform.smoothscale(frame, (draw_w, draw_h))
        if piece.faction == Faction.HumanSide:
            draw_frame = pygame.transform.flip(draw_frame, True, False)
        draw_x = sprite_box.centerx - draw_w // 2
        draw_y = sprite_box.bottom - draw_h
        screen.blit(draw_frame, (draw_x, draw_y))

    hp_ratio = 0.0 if piece.max_hp <= 0 else max(0.0, min(1.0, piece.hp / piece.max_hp))
    bar_rect = pygame.Rect(rect.x + 8, rect.bottom - 18, rect.width - 16, 8)
    pygame.draw.rect(screen, C_HP_EMPTY, bar_rect, border_radius=4)
    if hp_ratio > 0:
        fill_w = int(bar_rect.width * hp_ratio)
        pygame.draw.rect(screen, C_HP_FULL, (bar_rect.x, bar_rect.y, fill_w, bar_rect.height), border_radius=4)
    base_atk = get_base_attack(piece)
    atk_bonus = get_permanent_attack_bonus(piece) + get_attack_bonus(piece, state)
    def_bonus = get_defence_bonus(piece)
    atk_text = (
        f"Attack: {base_atk} + {atk_bonus}"
        if atk_bonus > 0
        else f"Attack: {base_atk}"
    )
    def_text = (
        f"Defence: 0 + {def_bonus}"
        if def_bonus > 0
        else "Defence: 0"
    )
    atk_surf = f_small.render(atk_text, True, text_color)
    def_surf = f_small.render(def_text, True, text_color)
    hp_text = f_small.render(f"HP: {max(0, piece.hp)}/{piece.max_hp}", True, text_color)
    screen.blit(atk_surf, (rect.x + 8, rect.bottom - 54))
    screen.blit(def_surf, (rect.x + 8, rect.bottom - 44))
    screen.blit(hp_text, (rect.x + 8, rect.bottom - 34))

def _draw_roster_panel(
    screen: pygame.Surface,
    state: GameState,
    panel_rect: pygame.Rect,
    faction: Faction,
    active_faction: Faction,
    selected_pid: str | None,
    title: str,
    title_color: tuple[int, int, int],
    f_title: pygame.font.Font,
    f_card: pygame.font.Font,
    f_small: pygame.font.Font,
    f_x: pygame.font.Font,
) -> None:
    is_active = faction == active_faction
    if is_active and faction == Faction.HumanSide:
        panel_bg = (95, 28, 28)
        panel_border = (255, 150, 210)
    elif is_active and faction == Faction.OrcSide:
        panel_bg = (45, 65, 105)
        panel_border = (140, 210, 255)
    else:
        panel_bg = C_PANEL_BG
        panel_border = C_PANEL_BORDER
    pygame.draw.rect(screen, panel_bg, panel_rect, border_radius=12)
    pygame.draw.rect(screen, panel_border, panel_rect, width=2, border_radius=12)
    title_surf = f_title.render(title, True, title_color)
    screen.blit(title_surf, (panel_rect.x + PANEL_PAD, panel_rect.y + PANEL_PAD))

    pieces = _piece_order_for(faction, state)
    if not pieces:
        return
    cards_y = panel_rect.y + PANEL_PAD + title_surf.get_height() + 8
    cards_h = panel_rect.bottom - PANEL_PAD - cards_y
    gap = 6
    card_h = max(72, min(98, (cards_h - gap * (len(pieces) - 1)) // len(pieces)))
    y = cards_y
    for piece in pieces:
        card_rect = pygame.Rect(panel_rect.x + PANEL_PAD, y, panel_rect.width - PANEL_PAD * 2, card_h)
        _draw_piece_card(
            screen, piece, state, card_rect, f_card, f_small, f_x,
            is_selected=(selected_pid == piece.id),
        )
        y += card_h + gap
        if y > panel_rect.bottom - PANEL_PAD:
            break


def draw_panel(
    screen: pygame.Surface,
    state: GameState,
    log: list[str] | None = None,
    btn_label: str = "Skip / End Turn",
    btn_hover: bool = False,
    selected_pid: str | None = None,
) -> None:
    ft, fb, fs, fbtn, fcard, fx = _fonts()
    f_section = pygame.font.Font(None, 24)
    f_section.set_bold(True)

    left_rect = pygame.Rect(LEFT_PANEL_X, SIDE_PANEL_Y, SIDE_PANEL_W, SIDE_PANEL_H)
    right_rect = pygame.Rect(RIGHT_PANEL_X, SIDE_PANEL_Y, SIDE_PANEL_W, SIDE_PANEL_H)
    bottom_rect = pygame.Rect(BOTTOM_PANEL_X, BOTTOM_PANEL_Y, BOTTOM_PANEL_W, BOTTOM_PANEL_H)

    _draw_roster_panel(
        screen, state, left_rect, Faction.OrcSide, state.active_faction, selected_pid,
        "OrcSide", C_ORCSIDE_LABEL, ft, fcard, fs, fx
    )
    _draw_roster_panel(
        screen, state, right_rect, Faction.HumanSide, state.active_faction, selected_pid,
        "HumanSide", C_HUMANSIDE_LABEL, ft, fcard, fs, fx
    )
    _draw_panel_box(screen, bottom_rect)

    inner_x = bottom_rect.x + PANEL_PAD
    inner_y = bottom_rect.y + PANEL_PAD
    inner_w = bottom_rect.width - PANEL_PAD * 2
    inner_h = bottom_rect.height - PANEL_PAD * 2
    col_gap = 10
    col_w = (inner_w - col_gap * 2) // 3
    left_col = pygame.Rect(inner_x, inner_y, col_w, inner_h)
    mid_col = pygame.Rect(left_col.right + col_gap, inner_y, col_w, inner_h)
    right_col = pygame.Rect(mid_col.right + col_gap, inner_y, col_w, inner_h)

    div1_x = left_col.right + col_gap // 2
    div2_x = mid_col.right + col_gap // 2
    pygame.draw.line(screen, C_PANEL_BORDER, (div1_x, inner_y), (div1_x, inner_y + inner_h), 1)
    pygame.draw.line(screen, C_PANEL_BORDER, (div2_x, inner_y), (div2_x, inner_y + inner_h), 1)

    # --- Middle column: turn/phase/instruction ---
    y_mid = mid_col.y
    active = state.active_faction
    faction_colour = C_HUMANSIDE_LABEL if active == Faction.HumanSide else C_ORCSIDE_LABEL
    faction_name   = "HUMANSIDE" if active == Faction.HumanSide else "ORCSIDE"
    banner = ft.render(f"{faction_name}'s Turn  |  Round {state.round_number}", True, faction_colour)
    screen.blit(banner, (mid_col.centerx - banner.get_width() // 2, y_mid))
    y_mid += banner.get_height() + 4

    phase_name = _PHASE_NAMES.get(state.current_phase, str(state.current_phase))
    phase_surf = fb.render(f"Phase: {phase_name}", True, C_PANEL_TEXT)
    screen.blit(phase_surf, (mid_col.centerx - phase_surf.get_width() // 2, y_mid))
    y_mid += phase_surf.get_height() + 3

    instr = _PHASE_INSTRUCTIONS.get(state.current_phase, "")
    for line in _wrap(instr, fs, mid_col.width - 8):
        s = fs.render(line, True, C_MSG_TEXT)
        screen.blit(s, (mid_col.centerx - s.get_width() // 2, y_mid))
        y_mid += s.get_height() + 1

    enter_hint = fs.render("Press Enter to skip", True, C_MUTED)
    screen.blit(
        enter_hint,
        (
            mid_col.centerx - enter_hint.get_width() // 2,
            mid_col.bottom - enter_hint.get_height() - 2,
        ),
    )

    # --- Left column: events ---
    y_left = left_col.y
    x_left = left_col.x + 4
    active_eps = [ep for ep in state.event_points if ep.is_valid and not ep.is_triggered]
    event_label = f_section.render("Events:", True, C_MSG_TEXT)
    screen.blit(event_label, (x_left, y_left))
    y_left += event_label.get_height() + 2
    if active_eps:
        for ep in active_eps:
            y_left = _draw_event_info_row(
                screen,
                ep.event_type,
                ep.pos,
                x_left + 2,
                y_left,
                fb,
            )
    else:
        no_event = fb.render("No active event points.", True, C_MUTED)
        screen.blit(no_event, (x_left, y_left))
        y_left += no_event.get_height() + 2

    # --- Right column: log ---
    y_right = right_col.y
    x_right = right_col.x + 4
    log_entries = log if log else []
    if log_entries:
        lbl_hdr = f_section.render("Log (latest first)", True, C_MSG_TEXT)
        screen.blit(lbl_hdr, (x_right, y_right))
        y_right += lbl_hdr.get_height() + 2
        for entry in log_entries:
            ec = C_AMMO if ("✦" in entry or "triggered" in entry or "Spawned" in entry) else C_MSG_TEXT
            for line in _wrap(entry, fb, right_col.width - 10):
                s = fb.render(line, True, ec)
                screen.blit(s, (x_right + 6, y_right))
                y_right += s.get_height() + 1
            if y_right > right_col.bottom - 6:
                break
    else:
        s = fb.render("Log: (empty)", True, C_MUTED)
        screen.blit(s, (x_right, y_right))

    # Keep click-to-skip button in the middle column bottom.
    BUTTON_RECT.update(
        mid_col.x + (mid_col.width - BTN_W) // 2,
        mid_col.bottom - BTN_H - 24,
        BTN_W,
        BTN_H,
    )
    btn_colour = C_BTN_HOVER if btn_hover else C_BTN_BG
    pygame.draw.rect(screen, btn_colour, BUTTON_RECT, border_radius=8)
    pygame.draw.rect(screen, C_PANEL_BORDER, BUTTON_RECT, 1, border_radius=8)
    btn_surf = fbtn.render(btn_label, True, C_BTN_TEXT)
    screen.blit(
        btn_surf,
        (
            BUTTON_RECT.centerx - btn_surf.get_width() // 2,
            BUTTON_RECT.centery - btn_surf.get_height() // 2,
        ),
    )


def draw_victory_overlay(screen: pygame.Surface, state: GameState) -> None:
    """
    Modal victory dialog.

    Layout (centered on screen):
      ┌──────────────────────────────┐
      │   ★  HUMANSIDE WINS!  ★            │
      │                              │
      │   General has fallen.       │
      │                              │
      │   Press Escape to quit       │
      └──────────────────────────────┘
    """
    vs = state.victory_state

    # Choose copy and colour by outcome
    if vs == VictoryState.HumanSide_WIN:
        title     = "HUMANSIDE  WINS!"
        subtitle  = "GeneralOrc has fallen."
        box_fill  = (90, 20, 20)
        box_border= C_VICTORY_HUMANSIDE
        title_c   = C_VICTORY_HUMANSIDE
    elif vs == VictoryState.OrcSide_WIN:
        title     = "ORCSIDE  WINS!"
        subtitle  = "GeneralHuman has fallen."
        box_fill  = (20, 20, 70)
        box_border= C_VICTORY_ORCSIDE
        title_c   = C_VICTORY_ORCSIDE
    else:
        title     = "DRAW"
        subtitle  = "Both sides have agreed to a draw."
        box_fill  = (50, 50, 20)
        box_border= C_VICTORY_DRAW
        title_c   = C_VICTORY_DRAW

    # ── Dim the whole screen ──────────────────────────────────────────────
    dim = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 180))
    screen.blit(dim, (0, 0))

    # ── Dialog box ────────────────────────────────────────────────────────
    BOX_W, BOX_H = 480, 260
    bx = WINDOW_W // 2 - BOX_W // 2
    by = WINDOW_H // 2 - BOX_H // 2

    # Shadow
    shadow = pygame.Rect(bx + 6, by + 6, BOX_W, BOX_H)
    pygame.draw.rect(screen, (0, 0, 0), shadow, border_radius=14)

    # Box background
    box_rect = pygame.Rect(bx, by, BOX_W, BOX_H)
    pygame.draw.rect(screen, box_fill, box_rect, border_radius=14)
    pygame.draw.rect(screen, box_border, box_rect, 3, border_radius=14)

    # ── Title ─────────────────────────────────────────────────────────────
    font_title = pygame.font.Font(None, 52)
    font_title.set_bold(True)
    font_sub   = pygame.font.Font(None, 19)
    font_hint  = pygame.font.Font(None, 14)

    stars = "★  " + title + "  ★"
    t_surf = font_title.render(stars, True, title_c)
    screen.blit(t_surf, (
        WINDOW_W // 2 - t_surf.get_width() // 2,
        by + 42,
    ))

    # Divider line
    pygame.draw.line(screen, box_border,
                     (bx + 30, by + 110), (bx + BOX_W - 30, by + 110), 1)

    # ── Subtitle ──────────────────────────────────────────────────────────
    s_surf = font_sub.render(subtitle, True, (220, 220, 220))
    screen.blit(s_surf, (
        WINDOW_W // 2 - s_surf.get_width() // 2,
        by + 130,
    ))

    # ── Hint ──────────────────────────────────────────────────────────────
    h_surf = font_hint.render("Press  Escape  to quit", True, (160, 160, 160))
    screen.blit(h_surf, (
        WINDOW_W // 2 - h_surf.get_width() // 2,
        by + BOX_H - 36,
    ))


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _wrap(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
    """Very simple word-wrap returning a list of lines."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if font.size(test)[0] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]
