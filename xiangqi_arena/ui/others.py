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
import xiangqi_arena.ui.display_config as dcfg
from xiangqi_arena.ui.display_config import (
    C_AMMO, C_ORCSIDE_LABEL, C_BTN_BG, C_BTN_HOVER, C_BTN_TEXT,
    C_HP_EMPTY, C_HP_FULL, C_MED, C_MSG_TEXT, C_MUTED, C_PANEL_BG,
    C_PANEL_BORDER, C_PANEL_TEXT, C_HUMANSIDE_LABEL, C_TRAP,
    C_VICTORY_ORCSIDE, C_VICTORY_DRAW, C_VICTORY_HUMANSIDE,
    PIECE_LABELS,
)
from xiangqi_arena.core.enums import EventPointType

# Kept in sync with `dcfg` each frame in draw_panel; initialised below.
BUTTON_RECT: pygame.Rect = pygame.Rect(0, 0, 1, 1)
SURRENDER_RECT: pygame.Rect = pygame.Rect(0, 0, 1, 1)
DRAW_RECT: pygame.Rect = pygame.Rect(0, 0, 1, 1)
# IMPORTANT: never reassign these Rect objects after import; main.py imports the
# objects directly and relies on .update() to mutate them across frames/resizes.
LOG_EXPAND_RECT: pygame.Rect = pygame.Rect(0, 0, 1, 1)
LOG_MODAL_CLOSE_RECT: pygame.Rect = pygame.Rect(0, 0, 1, 1)
LOG_MODAL_SCROLLBAR_RECT: pygame.Rect = pygame.Rect(0, 0, 1, 1)
LOG_MODAL_THUMB_RECT: pygame.Rect = pygame.Rect(0, 0, 1, 1)
LOG_MODAL_MAX_SCROLL: int = 0
LOG_MODAL_VISIBLE_LINES: int = 0
LOG_MODAL_TOTAL_LINES: int = 0


def sync_button_rects_from_config() -> None:
    """Set module-level click rects from current `dcfg` (after resize or import)."""
    bw, bh = dcfg.SKIP_BTN_W, dcfg.SKIP_BTN_H
    bx = dcfg.BOTTOM_PANEL_X + dcfg.BOTTOM_PANEL_W - bw - dcfg.PANEL_PAD
    by = dcfg.BOTTOM_PANEL_Y + dcfg.BOTTOM_PANEL_H - bh - dcfg.PANEL_PAD
    gap = dcfg.ACTION_BTN_GAP_X
    aw, a_h = dcfg.ACTION_BTN_W, dcfg.ACTION_BTN_H
    BUTTON_RECT.update(bx, by, bw, bh)
    SURRENDER_RECT.update(bx - gap - aw * 2, by, aw, a_h)
    DRAW_RECT.update(bx - gap - aw, by, aw, a_h)
    LOG_EXPAND_RECT.update(0, 0, 1, 1)
    LOG_MODAL_CLOSE_RECT.update(0, 0, 1, 1)
    LOG_MODAL_SCROLLBAR_RECT.update(0, 0, 1, 1)
    LOG_MODAL_THUMB_RECT.update(0, 0, 1, 1)


sync_button_rects_from_config()

_PHASE_INSTRUCTIONS: dict[Phase, str] = {
    Phase.START:       "",   # auto-processed, no instruction needed
    Phase.MOVEMENT:    "Click a piece → move (green) OR attack (targets)  |  One action per turn",
    Phase.RECOGNITION: "",   # auto-processed
    Phase.ATTACK:      "",   # skipped under single-action turns (auto-processed)
    Phase.RESOLVE:     "",   # auto-processed
}

_PHASE_NAMES: dict[Phase, str] = {
    Phase.START:       "START",
    Phase.MOVEMENT:    "ACTION",
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


def reset_panel_fonts() -> None:
    """Clear cached fonts after a layout / UI_SCALE change (e.g. window resize)."""
    global _FONT_TITLE, _FONT_BODY, _FONT_SMALL, _FONT_BTN, _FONT_CARD, _FONT_X
    _FONT_TITLE = None
    _FONT_BODY = None
    _FONT_SMALL = None
    _FONT_BTN = None
    _FONT_CARD = None
    _FONT_X = None


def _fonts() -> tuple:
    global _FONT_TITLE, _FONT_BODY, _FONT_SMALL, _FONT_BTN, _FONT_CARD, _FONT_X
    if _FONT_TITLE is None:
        s = dcfg.UI_SCALE
        t = max(16, int(24 * s))
        b = max(14, int(20 * s))
        sm = max(12, int(16 * s))
        bt = max(14, int(20 * s))
        cr = max(14, int(18 * s))
        xsz = max(20, int(34 * s))
        _FONT_TITLE = pygame.font.Font(None, t)
        _FONT_TITLE.set_bold(True)
        _FONT_BODY  = pygame.font.Font(None, b)
        _FONT_SMALL = pygame.font.Font(None, sm)
        _FONT_BTN   = pygame.font.Font(None, bt)
        _FONT_BTN.set_bold(True)
        _FONT_CARD  = pygame.font.Font(None, cr)
        _FONT_CARD.set_bold(True)
        _FONT_X = pygame.font.Font(None, xsz)
        _FONT_X.set_bold(True)
    return _FONT_TITLE, _FONT_BODY, _FONT_SMALL, _FONT_BTN, _FONT_CARD, _FONT_X


def _draw_panel_box(screen: pygame.Surface, rect: pygame.Rect) -> None:
    pygame.draw.rect(screen, C_PANEL_BG, rect, border_radius=12)
    pygame.draw.rect(screen, C_PANEL_BORDER, rect, width=2, border_radius=12)


def draw_top_bar(screen: pygame.Surface) -> None:
    """
    Top header bar.

    Left:  XIANGQI_ARENA (project title / logo placeholder)
    Middle: system status (Vision / Backend / Frontend) placeholders
    Right: placeholder icons (Settings / Help / Info)
    """
    s = dcfg.UI_SCALE
    h = dcfg.TOP_BAR_H
    rect = pygame.Rect(dcfg.HUD_MARGIN, dcfg.HUD_MARGIN, dcfg.WINDOW_W - dcfg.HUD_MARGIN * 2, h)
    pygame.draw.rect(screen, (18, 18, 26), rect, border_radius=14)
    pygame.draw.rect(screen, (80, 80, 120), rect, 2, border_radius=14)

    # Fonts
    title_font = pygame.font.Font(None, max(20, int(30 * s)))
    title_font.set_bold(True)
    body_font = pygame.font.Font(None, max(14, int(20 * s)))
    body_font.set_bold(True)
    # Middle status should be slightly larger for readability.
    small_font = pygame.font.Font(None, max(14, int(20 * s)))

    # Left: title
    title = title_font.render("XIANGQI_ARENA", True, (245, 245, 245))
    screen.blit(title, (rect.x + int(16 * s), rect.centery - title.get_height() // 2))

    # Middle: system status
    mid_x = rect.x + rect.width // 2
    labels = [
        ("Vision", True),
        ("Backend", True),
        ("Frontend", True),
    ]
    dot_r = max(5, int(6 * s))
    gap = max(10, int(16 * s))
    item_w = max(90, int(110 * s))
    total_w = item_w * len(labels) + gap * (len(labels) - 1)
    start_x = mid_x - total_w // 2
    y = rect.centery
    for i, (name, ok) in enumerate(labels):
        x = start_x + i * (item_w + gap)
        dot_c = (60, 220, 120) if ok else (220, 80, 80)
        pygame.draw.circle(screen, dot_c, (x + dot_r, y), dot_r)
        txt = small_font.render(name, True, (225, 225, 225))
        screen.blit(txt, (x + dot_r * 2 + int(6 * s), y - txt.get_height() // 2))

    # Right: icons (placeholders)
    icon_gap = max(12, int(14 * s))
    icon_r = max(13, int(16 * s))
    right_x = rect.right - int(16 * s)
    icons = [
        ("?", (240, 240, 240)),
        ("i", (240, 240, 240)),
        ("⚙", (240, 240, 240)),
    ]
    for label, col in icons:
        cx = right_x - icon_r
        cy = rect.centery
        pygame.draw.circle(screen, (45, 45, 65), (cx, cy), icon_r)
        pygame.draw.circle(screen, (120, 120, 160), (cx, cy), icon_r, 2)
        icon_font = pygame.font.Font(None, max(18, int(26 * s)))
        icon_font.set_bold(True)
        t = icon_font.render(label, True, col)
        screen.blit(t, (cx - t.get_width() // 2, cy - t.get_height() // 2))
        right_x -= (icon_r * 2 + icon_gap)


def _draw_event_info_row(
    screen: pygame.Surface,
    event_type: EventPointType,
    pos: tuple[int, int],
    x: int,
    y: int,
    font: pygame.font.Font,
) -> int:
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
        text = f"Trap Tile (-1 HP) at {pos}"

    text_surf = font.render(text, True, C_PANEL_TEXT)
    # Align icon and text to a shared row baseline.
    icon_size = icon_unit * 5
    row_h = max(icon_size + 2, text_surf.get_height() + 2)
    cy = y + row_h // 2
    icon_cx = x + 10
    icon_cy = cy
    _draw_pixel_icon(screen, icon_cx, icon_cy, icon_unit, layout, colour)

    text_x = x + 24
    text_y = cy - text_surf.get_height() // 2
    screen.blit(text_surf, (text_x, text_y))
    return y + row_h + 2


def _draw_expand_icon(screen: pygame.Surface, rect: pygame.Rect) -> None:
    """Simple 'expand' glyph in a rounded box."""
    pygame.draw.rect(screen, (50, 50, 78), rect, border_radius=8)
    pygame.draw.rect(screen, (165, 165, 210), rect, 2, border_radius=8)
    pad = max(4, rect.width // 6)
    x0, y0 = rect.x + pad, rect.y + pad
    x1, y1 = rect.right - pad, rect.bottom - pad
    c = (245, 245, 250)
    w = 3 if rect.width >= 22 else 2
    # Top-left corner arrow
    pygame.draw.line(screen, c, (x0, y0 + pad), (x0, y0), w)
    pygame.draw.line(screen, c, (x0, y0), (x0 + pad, y0), w)
    # Bottom-right corner arrow
    pygame.draw.line(screen, c, (x1 - pad, y1), (x1, y1), w)
    pygame.draw.line(screen, c, (x1, y1), (x1, y1 - pad), w)


def _draw_log_modal(
    screen: pygame.Surface,
    log_entries: list[str],
    scroll: int,
) -> int:
    """
    Draw a centered modal showing the full log history.
    Returns the possibly clamped scroll value.
    """
    global LOG_MODAL_CLOSE_RECT
    s = dcfg.UI_SCALE
    dim = pygame.Surface((dcfg.WINDOW_W, dcfg.WINDOW_H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 170))
    screen.blit(dim, (0, 0))

    box_w = int(min(dcfg.WINDOW_W * 0.75, 860))
    box_h = int(min(dcfg.WINDOW_H * 0.65, 560))
    bx = dcfg.WINDOW_W // 2 - box_w // 2
    by = dcfg.WINDOW_H // 2 - box_h // 2
    box = pygame.Rect(bx, by, box_w, box_h)
    pygame.draw.rect(screen, (22, 22, 34), box, border_radius=14)
    pygame.draw.rect(screen, (140, 140, 190), box, 2, border_radius=14)

    title_font = pygame.font.Font(None, max(20, int(28 * s)))
    title_font.set_bold(True)
    body_font = pygame.font.Font(None, max(16, int(20 * s)))
    hdr = title_font.render("Log History", True, (245, 245, 245))
    screen.blit(hdr, (box.x + int(16 * s), box.y + int(12 * s)))

    close_sz = max(22, int(26 * s))
    LOG_MODAL_CLOSE_RECT.update(
        box.right - close_sz - int(12 * s),
        box.y + int(10 * s),
        close_sz,
        close_sz,
    )
    pygame.draw.rect(screen, (55, 55, 80), LOG_MODAL_CLOSE_RECT, border_radius=6)
    pygame.draw.rect(screen, (140, 140, 190), LOG_MODAL_CLOSE_RECT, 1, border_radius=6)
    x = body_font.render("×", True, (245, 245, 245))
    screen.blit(x, (LOG_MODAL_CLOSE_RECT.centerx - x.get_width() // 2, LOG_MODAL_CLOSE_RECT.centery - x.get_height() // 2))

    # Content area leaves room for a scrollbar on the right.
    sb_w = max(10, int(12 * s))
    content = pygame.Rect(
        box.x + int(16 * s),
        box.y + int(50 * s),
        box.width - int(32 * s) - sb_w - int(8 * s),
        box.height - int(66 * s),
    )
    pygame.draw.rect(screen, (18, 18, 26), content, border_radius=10)

    # Prepare wrapped lines (newest first, same as panel).
    lines: list[str] = []
    for entry in log_entries:
        for ln in _wrap(entry, body_font, content.width - int(14 * s)):
            lines.append(ln)
        lines.append("")  # spacer

    line_h = body_font.get_height() + max(2, int(2 * s))
    max_lines_visible = max(1, content.height // line_h)
    max_scroll = max(0, len(lines) - max_lines_visible)
    scroll = max(0, min(int(scroll), max_scroll))

    # Expose scroll bounds for input handling (dragging / wheel).
    global LOG_MODAL_MAX_SCROLL, LOG_MODAL_VISIBLE_LINES, LOG_MODAL_TOTAL_LINES
    LOG_MODAL_MAX_SCROLL = int(max_scroll)
    LOG_MODAL_VISIBLE_LINES = int(max_lines_visible)
    LOG_MODAL_TOTAL_LINES = int(len(lines))

    y = content.y + int(8 * s)
    start = scroll
    end = min(len(lines), scroll + max_lines_visible)
    for i in range(start, end):
        ln = lines[i]
        if ln:
            surf = body_font.render(ln, True, (235, 235, 235))
            screen.blit(surf, (content.x + int(10 * s), y))
        y += line_h

    hint_font = pygame.font.Font(None, max(12, int(15 * s)))
    hint = hint_font.render("Wheel/trackpad to scroll • Drag bar • Click × to close", True, (170, 170, 190))
    screen.blit(hint, (box.x + int(16 * s), box.bottom - hint.get_height() - int(10 * s)))

    # Scrollbar
    global LOG_MODAL_SCROLLBAR_RECT, LOG_MODAL_THUMB_RECT
    LOG_MODAL_SCROLLBAR_RECT.update(content.right + int(8 * s), content.y, sb_w, content.height)
    pygame.draw.rect(screen, (28, 28, 44), LOG_MODAL_SCROLLBAR_RECT, border_radius=8)
    pygame.draw.rect(screen, (90, 90, 130), LOG_MODAL_SCROLLBAR_RECT, 1, border_radius=8)

    if max_scroll <= 0:
        LOG_MODAL_THUMB_RECT.update(LOG_MODAL_SCROLLBAR_RECT.x + 2, LOG_MODAL_SCROLLBAR_RECT.y + 2, sb_w - 4, LOG_MODAL_SCROLLBAR_RECT.height - 4)
    else:
        thumb_h = max(int(LOG_MODAL_SCROLLBAR_RECT.height * (max_lines_visible / max(1, len(lines)))), max(18, int(28 * s)))
        thumb_h = min(thumb_h, LOG_MODAL_SCROLLBAR_RECT.height - 4)
        track_h = LOG_MODAL_SCROLLBAR_RECT.height - 4 - thumb_h
        thumb_y = LOG_MODAL_SCROLLBAR_RECT.y + 2 + int(round(track_h * (scroll / max_scroll)))
        LOG_MODAL_THUMB_RECT.update(LOG_MODAL_SCROLLBAR_RECT.x + 2, thumb_y, sb_w - 4, thumb_h)
    pygame.draw.rect(screen, (70, 70, 110), LOG_MODAL_THUMB_RECT, border_radius=8)
    pygame.draw.rect(screen, (165, 165, 210), LOG_MODAL_THUMB_RECT, 1, border_radius=8)
    return scroll


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

    animation = piece_renderer._active_sprite_animation(piece.id, faction=piece.faction)
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
    setup_piece_status: dict | None = None,
) -> None:
    s = dcfg.UI_SCALE
    pad_x = max(6, int(8 * s))
    pad_y = max(5, int(6 * s))
    gap = max(2, int(3 * s))

    detected = True if setup_piece_status is None else bool(setup_piece_status.get("detected", False))
    correct = True if setup_piece_status is None else bool(setup_piece_status.get("correct", False))
    status_label = ""
    status_color = C_MUTED
    if setup_piece_status is not None:
        if not detected:
            status_label = "Not detected"
            status_color = C_MUTED
        elif not correct:
            status_label = "Wrong position"
            status_color = (255, 175, 70)
        else:
            status_label = "Detected"
            status_color = (100, 220, 130)

    inactive = setup_piece_status is not None and not detected
    card_bg = (30, 30, 44) if inactive else (34, 34, 55)
    card_border = (255, 220, 70) if is_selected else C_PANEL_BORDER
    text_color = (155, 155, 165) if inactive else (245, 245, 245)
    pygame.draw.rect(screen, card_bg, rect, border_radius=8)
    pygame.draw.rect(screen, card_border, rect, width=2 if is_selected else 1, border_radius=8)

    # --- Header (name) ---
    name_surf = f_card.render(piece.id, True, text_color)
    name_x = rect.x + pad_x
    name_y = rect.y + pad_y
    screen.blit(name_surf, (name_x, name_y))
    header_h = name_surf.get_height()
    status_h = 0
    if status_label:
        status_surf = f_small.render(status_label, True, status_color)
        screen.blit(status_surf, (name_x, name_y + header_h + 1))
        status_h = status_surf.get_height() + 1

    # --- Footer (single-line stats + hp bar with centered text) ---
    bar_h = max(7, int(10 * s))
    stats_h = f_small.get_height()
    footer_h = stats_h + gap + bar_h

    footer_top = rect.bottom - pad_y - footer_h
    if footer_top < name_y + header_h + gap:
        footer_top = name_y + header_h + gap

    base_atk = get_base_attack(piece)
    atk_bonus = get_permanent_attack_bonus(piece) + get_attack_bonus(piece, state)
    def_bonus = get_defence_bonus(piece)
    atk_val = f"{base_atk}" + (f"+{atk_bonus}" if atk_bonus > 0 else "")
    stats_text = f"ATK {atk_val}   DEF {def_bonus}"
    stats_surf = f_small.render(stats_text, True, text_color)
    screen.blit(stats_surf, (rect.x + pad_x, footer_top))

    # HP bar + centered HP text
    hp_ratio = 0.0 if piece.max_hp <= 0 else max(0.0, min(1.0, piece.hp / piece.max_hp))
    bar_rect = pygame.Rect(
        rect.x + pad_x,
        footer_top + stats_h + gap,
        rect.width - pad_x * 2,
        bar_h,
    )
    pygame.draw.rect(screen, C_HP_EMPTY, bar_rect, border_radius=max(3, int(5 * s)))
    if hp_ratio > 0:
        fill_w = int(bar_rect.width * hp_ratio)
        pygame.draw.rect(
            screen,
            C_HP_FULL,
            (bar_rect.x, bar_rect.y, fill_w, bar_rect.height),
            border_radius=max(3, int(5 * s)),
        )
    hp_text = f"{max(0, piece.hp)}/{piece.max_hp}"
    hp_surf = f_small.render(hp_text, True, (15, 15, 15))
    screen.blit(
        hp_surf,
        (bar_rect.centerx - hp_surf.get_width() // 2, bar_rect.centery - hp_surf.get_height() // 2),
    )

    # --- Sprite area (between header and footer) ---
    sprite_top = name_y + header_h + status_h + gap
    sprite_bottom = footer_top - gap
    sprite_h = max(10, sprite_bottom - sprite_top)
    sprite_box = pygame.Rect(rect.x + pad_x, sprite_top, rect.width - pad_x * 2, sprite_h)

    frame = _status_panel_frame(piece)
    if frame is not None and sprite_h >= 10:
        max_h = max(10, sprite_box.height)
        scale = min(1.0, max_h / max(1, frame.get_height()))
        draw_w = max(1, int(frame.get_width() * scale * 1.4))
        draw_h = max(1, int(frame.get_height() * scale * 1.4))
        draw_frame = pygame.transform.smoothscale(frame, (draw_w, draw_h))
        if piece.faction == Faction.HumanSide:
            draw_frame = pygame.transform.flip(draw_frame, True, False)
        if inactive:
            draw_frame.fill((150, 150, 150, 190), special_flags=pygame.BLEND_RGBA_MULT)
        # Place the portrait around the right third of the card.
        anchor_x = sprite_box.x + int(sprite_box.width * 0.68)
        draw_x = anchor_x - draw_w // 2
        # Keep it inside the sprite box horizontally.
        draw_x = max(sprite_box.x, min(draw_x, sprite_box.right - draw_w))
        draw_y = sprite_box.bottom - draw_h
        screen.blit(draw_frame, (draw_x, draw_y))

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
    setup_status: dict | None = None,
) -> None:
    is_active = faction == active_faction
    if is_active and faction == Faction.HumanSide:
        panel_bg = (95, 28, 28)
        panel_border = (255, 150, 210)
    elif is_active and faction == Faction.OrcSide:
        panel_bg = (22, 65, 35)
        panel_border = (120, 255, 160)
    else:
        panel_bg = C_PANEL_BG
        panel_border = C_PANEL_BORDER
    pygame.draw.rect(screen, panel_bg, panel_rect, border_radius=12)
    pygame.draw.rect(screen, panel_border, panel_rect, width=2, border_radius=12)
    title_surf = f_title.render(title, True, title_color)
    screen.blit(title_surf, (panel_rect.x + dcfg.PANEL_PAD, panel_rect.y + dcfg.PANEL_PAD))

    pieces = _piece_order_for(faction, state)
    if not pieces:
        return
    cards_y = panel_rect.y + dcfg.PANEL_PAD + title_surf.get_height() + max(6, int(8 * dcfg.UI_SCALE))
    cards_h = panel_rect.bottom - dcfg.PANEL_PAD - cards_y
    gap = max(3, int(6 * dcfg.UI_SCALE))
    # Keep cards fully inside the side panel even at low window heights.
    # Reduce minimum height now that stats take only one line and HP text is on the bar.
    min_card = max(44, int(56 * dcfg.UI_SCALE))
    max_card = max(min_card, int(110 * dcfg.UI_SCALE))
    card_h = max(1, min(max_card, (cards_h - gap * (len(pieces) - 1)) // max(1, len(pieces))))
    card_h = max(min_card, card_h)
    y = cards_y
    for piece in pieces:
        card_rect = pygame.Rect(panel_rect.x + dcfg.PANEL_PAD, y, panel_rect.width - dcfg.PANEL_PAD * 2, card_h)
        _draw_piece_card(
            screen, piece, state, card_rect, f_card, f_small, f_x,
            is_selected=(selected_pid == piece.id),
            setup_piece_status=(setup_status or {}).get("pieces", {}).get(piece.id),
        )
        y += card_h + gap
        if y > panel_rect.bottom - dcfg.PANEL_PAD:
            break


def _draw_setup_columns(
    screen: pygame.Surface,
    setup_status: dict,
    left_col: pygame.Rect,
    mid_col: pygame.Rect,
    right_col: pygame.Rect,
    f_body: pygame.font.Font,
    f_small: pygame.font.Font,
    f_section: pygame.font.Font,
    log: list[str] | None,
) -> None:
    pieces = setup_status.get("pieces", {})
    total = len(pieces)
    detected_count = sum(1 for info in pieces.values() if bool(info.get("detected", False)))
    ready = bool(setup_status.get("ready", False))
    camera_connected = bool(setup_status.get("camera_connected", False))
    board_detected = bool(setup_status.get("board_detected", False))

    def status_row(x: int, y: int, label: str, ok: bool, value: str | None = None) -> int:
        dot_c = (60, 220, 120) if ok else (220, 80, 80)
        pygame.draw.circle(screen, dot_c, (x + 8, y + f_body.get_height() // 2), 5)
        text = value if value is not None else ("Connected" if ok else "Waiting")
        surf = f_body.render(f"{label}: {text}", True, C_PANEL_TEXT)
        screen.blit(surf, (x + 20, y))
        return y + surf.get_height() + 4

    x = left_col.x + 4
    y = left_col.y
    hdr = f_section.render("Setup Progress", True, C_MSG_TEXT)
    screen.blit(hdr, (x, y))
    y += hdr.get_height() + 6
    y = status_row(x, y, "Camera", camera_connected)
    y = status_row(x, y, "Board", board_detected, "Detected" if board_detected else "Waiting")
    y = status_row(x, y, "Pieces", detected_count == total and total > 0, f"{detected_count} / {total}")
    y += 6
    hint = "Ready to start." if ready else "Waiting for every piece in its start position."
    for line in _wrap(hint, f_small, left_col.width - 10):
        surf = f_small.render(line, True, (100, 220, 130) if ready else C_MUTED)
        screen.blit(surf, (x + 4, y))
        y += surf.get_height() + 1

    x = mid_col.x + 4
    y = mid_col.y
    hdr = f_section.render("Missing Pieces", True, C_MSG_TEXT)
    screen.blit(hdr, (x, y))
    y += hdr.get_height() + 4
    missing = [pid for pid, info in pieces.items() if not bool(info.get("detected", False))]
    if not missing:
        surf = f_body.render("None", True, (100, 220, 130))
        screen.blit(surf, (x + 6, y))
    else:
        line_h = f_small.get_height() + 2
        max_rows = max(1, (mid_col.bottom - y - 2) // line_h)
        for pid in missing[:max_rows]:
            surf = f_small.render(pid, True, C_PANEL_TEXT)
            screen.blit(surf, (x + 6, y))
            y += line_h
        if len(missing) > max_rows:
            surf = f_small.render(f"+ {len(missing) - max_rows} more", True, C_MUTED)
            screen.blit(surf, (x + 6, y))

    x = right_col.x + 4
    y = right_col.y
    hdr = f_section.render("Setup Log", True, C_MSG_TEXT)
    screen.blit(hdr, (x, y))
    y += hdr.get_height() + 4
    entries = log or []
    if not entries:
        surf = f_body.render("Keep camera on the board.", True, C_MUTED)
        screen.blit(surf, (x + 6, y))
        return
    for entry in entries[:4]:
        for line in _wrap(entry, f_small, right_col.width - 10):
            surf = f_small.render(line, True, C_PANEL_TEXT)
            screen.blit(surf, (x + 6, y))
            y += surf.get_height() + 1
            if y > right_col.bottom - 4:
                return


def draw_panel(
    screen: pygame.Surface,
    state: GameState,
    log: list[str] | None = None,
    btn_label: str = "Skip / End Turn",
    btn_hover: bool = False,
    selected_pid: str | None = None,
    surrender_label: str = "Surrender [S]",
    surrender_hover: bool = False,
    surrender_enabled: bool = True,
    draw_label: str = "Request Draw [D]",
    draw_hover: bool = False,
    draw_enabled: bool = True,
    log_modal_open: bool = False,
    log_modal_scroll: int = 0,
    btn_enabled: bool = True,
    setup_status: dict | None = None,
) -> int:
    ft, fb, fs, fbtn, fcard, fx = _fonts()
    fsz = max(16, int(24 * dcfg.UI_SCALE))
    f_section = pygame.font.Font(None, fsz)
    f_section.set_bold(True)

    left_rect = pygame.Rect(
        dcfg.LEFT_PANEL_X, dcfg.SIDE_PANEL_Y, dcfg.SIDE_PANEL_W, dcfg.SIDE_PANEL_H
    )
    right_rect = pygame.Rect(
        dcfg.RIGHT_PANEL_X, dcfg.SIDE_PANEL_Y, dcfg.SIDE_PANEL_W, dcfg.SIDE_PANEL_H
    )
    bottom_rect = pygame.Rect(
        dcfg.BOTTOM_PANEL_X, dcfg.BOTTOM_PANEL_Y, dcfg.BOTTOM_PANEL_W, dcfg.BOTTOM_PANEL_H
    )

    _draw_roster_panel(
        screen, state, left_rect, Faction.OrcSide, state.active_faction, selected_pid,
        "OrcSide", C_ORCSIDE_LABEL, ft, fcard, fs, fx, setup_status=setup_status
    )
    _draw_roster_panel(
        screen, state, right_rect, Faction.HumanSide, state.active_faction, selected_pid,
        "HumanSide", C_HUMANSIDE_LABEL, ft, fcard, fs, fx, setup_status=setup_status
    )
    _draw_panel_box(screen, bottom_rect)

    inner_x = bottom_rect.x + dcfg.PANEL_PAD
    inner_y = bottom_rect.y + dcfg.PANEL_PAD
    inner_w = bottom_rect.width - dcfg.PANEL_PAD * 2
    inner_h = bottom_rect.height - dcfg.PANEL_PAD * 2

    # Reserve a full-width action row for buttons at the bottom of the panel.
    # This prevents the (Surrender / Draw / Skip) row from overlapping the
    # Events / Log columns when their combined width exceeds the middle column.
    action_gap_y = dcfg.ACTION_ROW_GAP_Y
    btn_h, btn_w = dcfg.SKIP_BTN_H, dcfg.SKIP_BTN_W
    content_h = max(0, inner_h - btn_h - action_gap_y)
    action_row = pygame.Rect(inner_x, inner_y + content_h + action_gap_y, inner_w, btn_h)

    col_gap = 10
    col_w = (inner_w - col_gap * 2) // 3
    left_col = pygame.Rect(inner_x, inner_y, col_w, content_h)
    mid_col = pygame.Rect(left_col.right + col_gap, inner_y, col_w, content_h)
    right_col = pygame.Rect(mid_col.right + col_gap, inner_y, col_w, content_h)

    div1_x = left_col.right + col_gap // 2
    div2_x = mid_col.right + col_gap // 2
    pygame.draw.line(screen, C_PANEL_BORDER, (div1_x, inner_y), (div1_x, inner_y + content_h), 1)
    pygame.draw.line(screen, C_PANEL_BORDER, (div2_x, inner_y), (div2_x, inner_y + content_h), 1)

    if setup_status is not None:
        _draw_setup_columns(screen, setup_status, left_col, mid_col, right_col, fb, fs, f_section, log)

        BUTTON_RECT.update(
            action_row.centerx - btn_w // 2,
            action_row.y,
            btn_w,
            btn_h,
        )
        g = dcfg.ACTION_BTN_GAP_X
        aw, ah = dcfg.ACTION_BTN_W, dcfg.ACTION_BTN_H
        SURRENDER_RECT.update(
            action_row.right - max(6, int(10 * dcfg.UI_SCALE)) - aw,
            BUTTON_RECT.y,
            aw,
            ah,
        )
        DRAW_RECT.update(
            SURRENDER_RECT.x - g - aw,
            BUTTON_RECT.y,
            aw,
            ah,
        )

        disabled_bg = (70, 70, 70)
        disabled_text = (150, 150, 150)

        pygame.draw.rect(screen, disabled_bg, SURRENDER_RECT, border_radius=8)
        pygame.draw.rect(screen, C_PANEL_BORDER, SURRENDER_RECT, 1, border_radius=8)
        s_surf = fbtn.render("Setup", True, disabled_text)
        screen.blit(s_surf, (SURRENDER_RECT.centerx - s_surf.get_width() // 2, SURRENDER_RECT.centery - s_surf.get_height() // 2))

        pygame.draw.rect(screen, disabled_bg, DRAW_RECT, border_radius=8)
        pygame.draw.rect(screen, C_PANEL_BORDER, DRAW_RECT, 1, border_radius=8)
        d_surf = fbtn.render("Camera Scan", True, disabled_text)
        screen.blit(d_surf, (DRAW_RECT.centerx - d_surf.get_width() // 2, DRAW_RECT.centery - d_surf.get_height() // 2))

        btn_colour = (C_BTN_HOVER if btn_hover else C_BTN_BG) if btn_enabled else disabled_bg
        btn_text = C_BTN_TEXT if btn_enabled else disabled_text
        pygame.draw.rect(screen, btn_colour, BUTTON_RECT, border_radius=8)
        pygame.draw.rect(screen, C_PANEL_BORDER, BUTTON_RECT, 1, border_radius=8)
        btn_surf = fbtn.render(btn_label, True, btn_text)
        screen.blit(btn_surf, (BUTTON_RECT.centerx - btn_surf.get_width() // 2, BUTTON_RECT.centery - btn_surf.get_height() // 2))
        return int(log_modal_scroll)

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
    mid_font = pygame.font.Font(None, max(16, int(20 * dcfg.UI_SCALE)))
    mid_font.set_bold(True)
    for line in _wrap(instr, mid_font, mid_col.width - 8):
        s = mid_font.render(line, True, C_MSG_TEXT)
        screen.blit(s, (mid_col.centerx - s.get_width() // 2, y_mid))
        y_mid += s.get_height() + 1

    enter_hint_font = pygame.font.Font(None, max(14, int(18 * dcfg.UI_SCALE)))
    enter_hint = enter_hint_font.render("Press Enter to skip", True, C_MUTED)
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
                pygame.font.Font(None, max(16, int(22 * dcfg.UI_SCALE))),
            )
    else:
        no_event_font = pygame.font.Font(None, max(16, int(22 * dcfg.UI_SCALE)))
        no_event = no_event_font.render("No active event points.", True, C_MUTED)
        screen.blit(no_event, (x_left, y_left))
        y_left += no_event.get_height() + 2

    # --- Triggered events (rule reminder placeholder) ---
    y_left += max(4, int(6 * dcfg.UI_SCALE))
    trig_hdr = f_section.render("Triggered_events:", True, C_MSG_TEXT)
    screen.blit(trig_hdr, (x_left, y_left))
    y_left += trig_hdr.get_height() + 2
    trig_font = pygame.font.Font(None, max(16, int(22 * dcfg.UI_SCALE)))
    trig_text = "Leader in palace (3×3): −1 incoming damage"
    for line in _wrap(trig_text, trig_font, left_col.width - 10):
        s = trig_font.render(line, True, (235, 235, 235))
        screen.blit(s, (x_left + 6, y_left))
        y_left += s.get_height() + 1

    # --- Right column: log (latest 5) ---
    y_right = right_col.y
    x_right = right_col.x + 4
    log_entries = log if log else []
    if log_entries:
        lbl_hdr = f_section.render("Log", True, C_MSG_TEXT)
        screen.blit(lbl_hdr, (x_right, y_right))
        exp_sz = max(18, int(22 * dcfg.UI_SCALE))
        LOG_EXPAND_RECT.update(right_col.right - exp_sz - 6, y_right + 2, exp_sz, exp_sz)
        _draw_expand_icon(screen, LOG_EXPAND_RECT)
        y_right += lbl_hdr.get_height() + 2
        flog = pygame.font.Font(None, max(16, int(22 * dcfg.UI_SCALE)))
        flog.set_bold(True)
        for entry in log_entries[:5]:
            ec = C_AMMO if ("✦" in entry or "triggered" in entry or "Spawned" in entry) else C_MSG_TEXT
            for line in _wrap(entry, flog, right_col.width - 10):
                s = flog.render(line, True, ec)
                screen.blit(s, (x_right + 6, y_right))
                y_right += s.get_height() + 1
            if y_right > right_col.bottom - 6:
                break
    else:
        s = fb.render("Log: (empty)", True, C_MUTED)
        screen.blit(s, (x_right, y_right))
        LOG_EXPAND_RECT.update(0, 0, 1, 1)

    # Place click-to-act buttons on the reserved full-width action row.
    BUTTON_RECT.update(
        action_row.centerx - btn_w // 2,
        action_row.y,
        btn_w,
        btn_h,
    )
    # Place Surrender/Draw at the bottom-right, keep Skip centered.
    g = dcfg.ACTION_BTN_GAP_X
    aw, ah = dcfg.ACTION_BTN_W, dcfg.ACTION_BTN_H
    SURRENDER_RECT.update(
        action_row.right - max(6, int(10 * dcfg.UI_SCALE)) - aw,
        BUTTON_RECT.y,
        aw,
        ah,
    )
    DRAW_RECT.update(
        SURRENDER_RECT.x - g - aw,
        BUTTON_RECT.y,
        aw,
        ah,
    )

    disabled_bg = (70, 70, 70)
    disabled_text = (150, 150, 150)

    # Surrender button
    s_bg = (C_BTN_HOVER if surrender_hover else C_BTN_BG) if surrender_enabled else disabled_bg
    s_tc = C_BTN_TEXT if surrender_enabled else disabled_text
    pygame.draw.rect(screen, s_bg, SURRENDER_RECT, border_radius=8)
    pygame.draw.rect(screen, C_PANEL_BORDER, SURRENDER_RECT, 1, border_radius=8)
    s_surf = fbtn.render(surrender_label, True, s_tc)
    screen.blit(
        s_surf,
        (
            SURRENDER_RECT.centerx - s_surf.get_width() // 2,
            SURRENDER_RECT.centery - s_surf.get_height() // 2,
        ),
    )

    # Draw button
    d_bg = (C_BTN_HOVER if draw_hover else C_BTN_BG) if draw_enabled else disabled_bg
    d_tc = C_BTN_TEXT if draw_enabled else disabled_text
    pygame.draw.rect(screen, d_bg, DRAW_RECT, border_radius=8)
    pygame.draw.rect(screen, C_PANEL_BORDER, DRAW_RECT, 1, border_radius=8)
    d_surf = fbtn.render(draw_label, True, d_tc)
    screen.blit(
        d_surf,
        (
            DRAW_RECT.centerx - d_surf.get_width() // 2,
            DRAW_RECT.centery - d_surf.get_height() // 2,
        ),
    )

    btn_colour = (C_BTN_HOVER if btn_hover else C_BTN_BG) if btn_enabled else disabled_bg
    btn_text = C_BTN_TEXT if btn_enabled else disabled_text
    pygame.draw.rect(screen, btn_colour, BUTTON_RECT, border_radius=8)
    pygame.draw.rect(screen, C_PANEL_BORDER, BUTTON_RECT, 1, border_radius=8)
    btn_surf = fbtn.render(btn_label, True, btn_text)
    screen.blit(
        btn_surf,
        (
            BUTTON_RECT.centerx - btn_surf.get_width() // 2,
            BUTTON_RECT.centery - btn_surf.get_height() // 2,
        ),
    )

    if log_modal_open and log_entries:
        log_modal_scroll = _draw_log_modal(screen, list(log_entries), log_modal_scroll)

    return int(log_modal_scroll)


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
        orc_surrendered = state.players[Faction.OrcSide].has_surrendered
        subtitle  = "OrcSide has surrendered." if orc_surrendered else "GeneralOrc has fallen."
        box_fill  = (90, 20, 20)
        box_border= C_VICTORY_HUMANSIDE
        title_c   = C_VICTORY_HUMANSIDE
    elif vs == VictoryState.OrcSide_WIN:
        title     = "ORCSIDE  WINS!"
        human_surrendered = state.players[Faction.HumanSide].has_surrendered
        subtitle  = "HumanSide has surrendered." if human_surrendered else "GeneralHuman has fallen."
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
    dim = pygame.Surface((dcfg.WINDOW_W, dcfg.WINDOW_H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 180))
    screen.blit(dim, (0, 0))

    # ── Dialog box ────────────────────────────────────────────────────────
    BOX_W, BOX_H = 480, 260
    bx = dcfg.WINDOW_W // 2 - BOX_W // 2
    by = dcfg.WINDOW_H // 2 - BOX_H // 2

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
        dcfg.WINDOW_W // 2 - t_surf.get_width() // 2,
        by + 42,
    ))

    # Divider line
    pygame.draw.line(screen, box_border,
                     (bx + 30, by + 110), (bx + BOX_W - 30, by + 110), 1)

    # ── Subtitle ──────────────────────────────────────────────────────────
    s_surf = font_sub.render(subtitle, True, (220, 220, 220))
    screen.blit(s_surf, (
        dcfg.WINDOW_W // 2 - s_surf.get_width() // 2,
        by + 130,
    ))

    # ── Hint ──────────────────────────────────────────────────────────────
    h_surf = font_hint.render("Press  Escape  to quit", True, (160, 160, 160))
    screen.blit(h_surf, (
        dcfg.WINDOW_W // 2 - h_surf.get_width() // 2,
        by + BOX_H - 36,
    ))


def draw_kill_dialog(screen: pygame.Surface, pending_kills: list[dict]) -> None:
    """
    Modal dialog that asks the opposing player to physically remove the
    just-killed piece(s) from the board.

    The dialog stays open until the main loop empties *pending_kills*
    (vision detects the piece markers off the board).
    """
    if not pending_kills:
        return

    # ---- copy / colours -----------------------------------------------------
    factions = {entry.get("faction") for entry in pending_kills}
    if len(factions) == 1 and Faction.HumanSide in factions:
        # HumanSide pieces just died -> HumanSide owner removes them.
        title_c = C_VICTORY_HUMANSIDE
        box_border = C_VICTORY_HUMANSIDE
        box_fill = (90, 20, 20)
        owner_label = "Red player"
    elif len(factions) == 1 and Faction.OrcSide in factions:
        title_c = C_VICTORY_ORCSIDE
        box_border = C_VICTORY_ORCSIDE
        box_fill = (20, 20, 70)
        owner_label = "Black player"
    else:
        title_c = (220, 200, 100)
        box_border = (220, 200, 100)
        box_fill = (60, 50, 20)
        owner_label = "Owners"

    title = "Remove fallen piece"
    subtitle = (
        f"{owner_label}, please take the piece(s) off the board."
    )
    hint = "Dialog closes once the marker is no longer detected."

    # Build piece-name lines (use PIECE_LABELS to avoid hard-coding piece IDs).
    name_lines: list[str] = []
    for entry in pending_kills:
        pid = str(entry.get("piece_id", ""))
        label = PIECE_LABELS.get(pid, pid)
        pos = entry.get("pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            name_lines.append(f"{label}  @  ({pos[0]}, {pos[1]})")
        else:
            name_lines.append(label)

    # ---- screen dim ---------------------------------------------------------
    dim = pygame.Surface((dcfg.WINDOW_W, dcfg.WINDOW_H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 180))
    screen.blit(dim, (0, 0))

    # ---- dialog box ---------------------------------------------------------
    s = max(0.7, min(1.6, dcfg.UI_SCALE))
    BOX_W = int(560 * s)
    line_h = max(20, int(28 * s))
    BOX_H = int(220 * s) + line_h * len(name_lines)
    bx = dcfg.WINDOW_W // 2 - BOX_W // 2
    by = dcfg.WINDOW_H // 2 - BOX_H // 2

    pygame.draw.rect(
        screen, (0, 0, 0),
        pygame.Rect(bx + 6, by + 6, BOX_W, BOX_H),
        border_radius=14,
    )
    box_rect = pygame.Rect(bx, by, BOX_W, BOX_H)
    pygame.draw.rect(screen, box_fill, box_rect, border_radius=14)
    pygame.draw.rect(screen, box_border, box_rect, 3, border_radius=14)

    font_title = pygame.font.Font(None, max(28, int(40 * s)))
    font_title.set_bold(True)
    font_sub = pygame.font.Font(None, max(16, int(22 * s)))
    font_name = pygame.font.Font(None, max(16, int(22 * s)))
    font_name.set_bold(True)
    font_hint = pygame.font.Font(None, max(12, int(16 * s)))

    t_surf = font_title.render(title, True, title_c)
    screen.blit(
        t_surf,
        (dcfg.WINDOW_W // 2 - t_surf.get_width() // 2, by + int(28 * s)),
    )

    pygame.draw.line(
        screen, box_border,
        (bx + int(30 * s), by + int(80 * s)),
        (bx + BOX_W - int(30 * s), by + int(80 * s)),
        1,
    )

    s_surf = font_sub.render(subtitle, True, (230, 230, 230))
    screen.blit(
        s_surf,
        (dcfg.WINDOW_W // 2 - s_surf.get_width() // 2, by + int(96 * s)),
    )

    list_y = by + int(140 * s)
    for line in name_lines:
        n_surf = font_name.render(line, True, (250, 240, 200))
        screen.blit(
            n_surf,
            (dcfg.WINDOW_W // 2 - n_surf.get_width() // 2, list_y),
        )
        list_y += line_h

    h_surf = font_hint.render(hint, True, (170, 170, 180))
    screen.blit(
        h_surf,
        (
            dcfg.WINDOW_W // 2 - h_surf.get_width() // 2,
            by + BOX_H - int(34 * s),
        ),
    )


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
