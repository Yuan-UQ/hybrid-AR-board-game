"""
HUD rendering.

Layout:
  - Left panel  : OrcSide roster cards
  - Right panel : HumanSide roster cards
  - Bottom panel: game status, events, log, skip button
"""

from __future__ import annotations

import math
import os
import pygame

try:
    from PIL import Image, ImageSequence
except Exception:  # pragma: no cover - optional runtime dependency fallback
    Image = None
    ImageSequence = None

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
TUTORIAL_RECT: pygame.Rect = pygame.Rect(0, 0, 1, 1)
GUIDE_RECT: pygame.Rect = pygame.Rect(0, 0, 1, 1)
# IMPORTANT: never reassign these Rect objects after import; main.py imports the
# objects directly and relies on .update() to mutate them across frames/resizes.
LOG_EXPAND_RECT: pygame.Rect = pygame.Rect(0, 0, 1, 1)
LOG_MODAL_CLOSE_RECT: pygame.Rect = pygame.Rect(0, 0, 1, 1)
LOG_MODAL_SCROLLBAR_RECT: pygame.Rect = pygame.Rect(0, 0, 1, 1)
LOG_MODAL_THUMB_RECT: pygame.Rect = pygame.Rect(0, 0, 1, 1)
LOG_MODAL_MAX_SCROLL: int = 0
LOG_MODAL_VISIBLE_LINES: int = 0
LOG_MODAL_TOTAL_LINES: int = 0
_HINT_GIF_CACHE: dict[tuple[str, int, int], list[pygame.Surface]] = {}
_HINT_ANIMATION_FILES: dict[str, str | tuple[str, ...]] = {
    "flip_marker": ("PhysicalPieceSelection.gif", "DigitalPieceSelection.gif"),
    "flip_marker_warning": ("PhysicalPieceSelection.gif", "DigitalPieceSelection.gif"),
    "leader_palace_move": "LeaderMove.gif",
    "leader_attack": "LeaderAttack.gif",
    "archer_straight_range": "ArcherMove.gif",
    "archer_attack": "ArcherAttack.gif",
    "lancer_l_shape": "LancerMove.gif",
    "lancer_attack": "LancerAttack.gif",
    "wizard_cross_aoe": "WizardMove.gif",
    "wizard_attack": "WizardAttack.gif",
    "soldier_before_river": "SoldierMove.gif",
    "soldier_after_river": "SoldierMove.gif",
    "soldier_attack": "SoldierAttack.gif",
}


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
    TUTORIAL_RECT.update(0, 0, 1, 1)
    GUIDE_RECT.update(0, 0, 1, 1)
    LOG_EXPAND_RECT.update(0, 0, 1, 1)
    LOG_MODAL_CLOSE_RECT.update(0, 0, 1, 1)
    LOG_MODAL_SCROLLBAR_RECT.update(0, 0, 1, 1)
    LOG_MODAL_THUMB_RECT.update(0, 0, 1, 1)


sync_button_rects_from_config()


def sync_top_bar_button_rects(*, show_tutorial: bool = False) -> None:
    """Update clickable top-bar Guide/Tutorial rects for the current layout."""
    s = dcfg.UI_SCALE
    top_bar = pygame.Rect(
        dcfg.HUD_MARGIN,
        dcfg.HUD_MARGIN,
        dcfg.WINDOW_W - dcfg.HUD_MARGIN * 2,
        dcfg.TOP_BAR_H,
    )
    pad = max(10, int(16 * s))
    gap = max(8, int(10 * s))
    guide_size = max(30, int(36 * s))
    guide_x = top_bar.right - pad - guide_size
    guide_y = top_bar.centery - guide_size // 2
    GUIDE_RECT.update(guide_x, guide_y, guide_size, guide_size)

    if show_tutorial:
        tutorial_w = max(104, int(126 * s))
        tutorial_h = guide_size
        TUTORIAL_RECT.update(guide_x - gap - tutorial_w, guide_y, tutorial_w, tutorial_h)
    else:
        TUTORIAL_RECT.update(0, 0, 1, 1)

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
_NOTIF_ERR_TITLE_FONT: pygame.font.Font | None = None
_NOTIF_ERR_BODY_FONT: pygame.font.Font | None = None


def reset_panel_fonts() -> None:
    """Clear cached fonts after a layout / UI_SCALE change (e.g. window resize)."""
    global _FONT_TITLE, _FONT_BODY, _FONT_SMALL, _FONT_BTN, _FONT_CARD, _FONT_X
    global _NOTIF_ERR_TITLE_FONT, _NOTIF_ERR_BODY_FONT
    _FONT_TITLE = None
    _FONT_BODY = None
    _FONT_SMALL = None
    _FONT_BTN = None
    _FONT_CARD = None
    _FONT_X = None
    _NOTIF_ERR_TITLE_FONT = None
    _NOTIF_ERR_BODY_FONT = None


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


def _notification_error_fonts() -> tuple[pygame.font.Font, pygame.font.Font]:
    """System fonts for notification errors (CJK + Latin; avoids tofu from Font(None))."""
    global _NOTIF_ERR_TITLE_FONT, _NOTIF_ERR_BODY_FONT
    if _NOTIF_ERR_TITLE_FONT is None:
        s = dcfg.UI_SCALE
        panel_h = max(120, int(getattr(dcfg, "BOTTOM_PANEL_H", 190) or 190))
        # Keep title/body within the bottom-left panel (narrow + ~148–280px tall).
        title_sz = max(14, min(18, int(panel_h * 0.078 * s + 5)))
        body_sz = max(12, min(14, int(panel_h * 0.064 * s + 4)))
        names = (
            "Microsoft YaHei UI",
            "Microsoft YaHei",
            "Segoe UI",
            "Arial Unicode MS",
            "Arial",
        )

        def _try_sys(sz: int, bold: bool) -> pygame.font.Font | None:
            for n in names:
                try:
                    f = pygame.font.SysFont(n, sz, bold=bold)
                    probe = f.render("Vision 视觉 0123", True, (255, 255, 255))
                    if probe.get_width() > 0:
                        return f
                except Exception:
                    continue
            return None

        _NOTIF_ERR_TITLE_FONT = _try_sys(title_sz, True) or pygame.font.Font(None, title_sz)
        _NOTIF_ERR_TITLE_FONT.set_bold(True)
        _NOTIF_ERR_BODY_FONT = _try_sys(body_sz, True) or pygame.font.Font(None, body_sz)
        _NOTIF_ERR_BODY_FONT.set_bold(True)
    return _NOTIF_ERR_TITLE_FONT, _NOTIF_ERR_BODY_FONT


def _draw_panel_box(screen: pygame.Surface, rect: pygame.Rect) -> None:
    pygame.draw.rect(screen, C_PANEL_BG, rect, border_radius=12)
    pygame.draw.rect(screen, C_PANEL_BORDER, rect, width=2, border_radius=12)


def _draw_top_bar_legacy(screen: pygame.Surface) -> None:
    """
    Top header bar.

    Left:  XIANGQI_ARENA (project title / logo placeholder)
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
    # Left: title
    title = title_font.render("XIANGQI_ARENA", True, (245, 245, 245))
    screen.blit(title, (rect.x + int(16 * s), rect.centery - title.get_height() // 2))

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


def draw_top_bar(
    screen: pygame.Surface,
    *,
    show_tutorial: bool = False,
    tutorial_hover: bool = False,
    guide_hover: bool = False,
    setup_stage_label: str = "Setup Stage",
    state: GameState | None = None,
    selected_pid: str | None = None,
    minor_warning: str | None = None,
    status_is_error: bool = False,
) -> None:
    """Top header bar with Setup Tutorial and Game Guide controls."""
    s = dcfg.UI_SCALE
    h = dcfg.TOP_BAR_H
    rect = pygame.Rect(dcfg.HUD_MARGIN, dcfg.HUD_MARGIN, dcfg.WINDOW_W - dcfg.HUD_MARGIN * 2, h)
    bar_bg = (18, 18, 26)
    bar_border = (80, 80, 120)
    accent_main = (255, 236, 130)
    accent_border = (130, 130, 170)
    if state is not None:
        if state.active_faction == Faction.HumanSide:
            bar_bg = (40, 16, 20)
            bar_border = (200, 70, 85)
            accent_main = (255, 190, 190)
            accent_border = (245, 120, 135)
        else:
            bar_bg = (16, 35, 22)
            bar_border = (80, 190, 100)
            accent_main = (195, 255, 195)
            accent_border = (120, 235, 145)
    pygame.draw.rect(screen, bar_bg, rect, border_radius=14)
    pygame.draw.rect(screen, bar_border, rect, 2, border_radius=14)

    title_font = pygame.font.Font(None, max(18, int(24 * s)))
    title_font.set_bold(True)
    title = title_font.render("XIANGQI_ARENA", True, (245, 245, 245))
    title_y = rect.y + max(6, int(8 * s))
    screen.blit(title, (rect.x + int(16 * s), title_y))

    if state is not None:
        phase_name = _PHASE_NAMES.get(state.current_phase, str(state.current_phase))
        faction_name = "HumanSide" if state.active_faction == Faction.HumanSide else "OrcSide"
        status_text = f"Round {state.round_number} | {faction_name} Turn | {phase_name}"
    else:
        status_text = setup_stage_label

    status_font = pygame.font.Font(None, max(24, int(34 * s)))
    status_font.set_bold(True)
    status_color = accent_main
    status_surf = status_font.render(status_text, True, status_color)
    status_x = rect.centerx - status_surf.get_width() // 2
    status_y = title_y + title.get_height() + max(2, int(4 * s))
    screen.blit(status_surf, (status_x, status_y))

    sync_top_bar_button_rects(show_tutorial=show_tutorial)

    if show_tutorial:
        radius = max(8, int(10 * s))
        tut_bg = C_BTN_HOVER if tutorial_hover else (45, 45, 65)
        pygame.draw.rect(screen, tut_bg, TUTORIAL_RECT, border_radius=radius)
        pygame.draw.rect(screen, (120, 120, 160), TUTORIAL_RECT, 2, border_radius=radius)
        tut_font = pygame.font.Font(None, max(17, int(23 * s)))
        tut_font.set_bold(True)
        tut = tut_font.render("Tutorial", True, (240, 240, 240))
        screen.blit(
            tut,
            (
                TUTORIAL_RECT.centerx - tut.get_width() // 2,
                TUTORIAL_RECT.centery - tut.get_height() // 2,
            ),
        )

    guide_bg = C_BTN_HOVER if guide_hover else (45, 45, 65)
    pygame.draw.ellipse(screen, guide_bg, GUIDE_RECT)
    pygame.draw.ellipse(screen, (120, 120, 160), GUIDE_RECT, 2)
    icon_font = pygame.font.Font(None, max(18, int(26 * s)))
    icon_font.set_bold(True)
    guide = icon_font.render("?", True, (240, 240, 240))
    screen.blit(
        guide,
        (
            GUIDE_RECT.centerx - guide.get_width() // 2,
            GUIDE_RECT.centery - guide.get_height() // 2,
        ),
    )


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


def _hint_animation_paths(animation_key: str) -> list[str]:
    files = _HINT_ANIMATION_FILES.get(animation_key)
    if not files:
        return []
    filenames = list(files) if isinstance(files, tuple) else [files]
    guide_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "ArtResource",
        "Home",
        "Guide",
    )
    return [os.path.join(guide_dir, filename) for filename in filenames]


def _hint_animation_path(animation_key: str) -> str | None:
    paths = _hint_animation_paths(animation_key)
    return paths[0] if paths else None


def _load_hint_gif_frames_from_path(path: str | None, max_w: int, max_h: int) -> list[pygame.Surface]:
    if not path or Image is None or ImageSequence is None or not os.path.exists(path):
        return []

    key = (path, max_w, max_h)
    cached = _HINT_GIF_CACHE.get(key)
    if cached is not None:
        return cached

    frames: list[pygame.Surface] = []
    try:
        with Image.open(path) as gif:
            for frame in ImageSequence.Iterator(gif):
                rgba = frame.convert("RGBA")
                w, h = rgba.size
                scale = min(max_w / max(1, w), max_h / max(1, h))
                target_size = (max(1, int(w * scale)), max(1, int(h * scale)))
                if target_size != rgba.size:
                    rgba = rgba.resize(target_size, Image.Resampling.LANCZOS)
                surf = pygame.image.fromstring(rgba.tobytes(), rgba.size, "RGBA").convert_alpha()
                frames.append(surf)
    except Exception:
        frames = []

    _HINT_GIF_CACHE[key] = frames
    return frames


def _load_hint_gif_frames(animation_key: str, max_w: int, max_h: int) -> list[pygame.Surface]:
    return _load_hint_gif_frames_from_path(_hint_animation_path(animation_key), max_w, max_h)


def _draw_hint_animation(screen: pygame.Surface, rect: pygame.Rect, animation_key: str) -> None:
    """MVP animation slot: static, safe fallback when no frame assets exist."""
    s = dcfg.UI_SCALE
    pygame.draw.rect(screen, (28, 28, 42), rect, border_radius=8)
    pygame.draw.rect(screen, (105, 105, 145), rect, 1, border_radius=8)

    paths = _hint_animation_paths(str(animation_key or ""))
    if len(paths) >= 2:
        arrow_w = max(12, int(16 * s))
        gap = max(3, int(4 * s))
        max_h = max(1, rect.height - int(10 * s))
        max_w = max(1, (rect.width - arrow_w - gap * 4) // 2)
        flow_frames: list[pygame.Surface] = []
        for path in paths[:2]:
            frames_for_step = _load_hint_gif_frames_from_path(path, max_w, max_h)
            if not frames_for_step:
                flow_frames = []
                break
            frame_index = (pygame.time.get_ticks() // 90) % len(frames_for_step)
            flow_frames.append(frames_for_step[frame_index])

        if len(flow_frames) == 2:
            total_w = flow_frames[0].get_width() + arrow_w + flow_frames[1].get_width() + gap * 2
            x = rect.centerx - total_w // 2
            for i, frame in enumerate(flow_frames):
                screen.blit(frame, (x, rect.centery - frame.get_height() // 2))
                x += frame.get_width()
                if i == 0:
                    x += gap
                    arrow_font = pygame.font.Font(None, max(18, int(25 * s)))
                    arrow_font.set_bold(True)
                    arrow = arrow_font.render(">", True, (235, 218, 160))
                    screen.blit(arrow, (x + arrow_w // 2 - arrow.get_width() // 2, rect.centery - arrow.get_height() // 2))
                    x += arrow_w + gap
            return

    frames = _load_hint_gif_frames(
        str(animation_key or ""),
        max(1, rect.width - int(10 * s)),
        max(1, rect.height - int(10 * s)),
    )
    if frames:
        frame_index = (pygame.time.get_ticks() // 90) % len(frames)
        frame = frames[frame_index]
        screen.blit(
            frame,
            (
                rect.centerx - frame.get_width() // 2,
                rect.centery - frame.get_height() // 2,
            ),
        )
        return

    label_font = pygame.font.Font(None, max(12, int(15 * s)))
    label_font.set_bold(True)
    key = str(animation_key or "hint")
    lines = _wrap(key.replace("_", " "), label_font, max(20, rect.width - int(10 * s)))
    line_h = label_font.get_height() + 1
    total_h = line_h * min(3, len(lines))
    y = rect.centery - total_h // 2
    for line in lines[:3]:
        surf = label_font.render(line, True, (190, 190, 215))
        screen.blit(surf, (rect.centerx - surf.get_width() // 2, y))
        y += line_h


def _draw_hint_panel(
    screen: pygame.Surface,
    rect: pygame.Rect,
    hint_context: dict | None,
    f_section: pygame.font.Font,
) -> None:
    """Draw playing-stage Hint content from precomputed context only."""
    if hint_context is None:
        hint_context = {
            "title": "Choose a piece",
            "action_line": "Flip one active piece to reveal its marker.",
            "rule_line": "Only one piece can be selected at a time.",
            "detail_line": "Do not click the computer. The selected piece will glow yellow.",
            "next_step_line": "Next: follow the green move points or red attack targets.",
            "severity": "normal",
            "animation_key": "flip_marker",
        }

    # Keep the Hint Bar visually stable even when recovery/error guidance is active.
    accent = C_MSG_TEXT
    fill = (28, 32, 43)

    inner = rect.inflate(-dcfg.PANEL_PAD * 2, -dcfg.PANEL_PAD * 2)
    header = f_section.render("Hint", True, C_MSG_TEXT)
    screen.blit(header, (inner.x, inner.y))

    content = pygame.Rect(
        inner.x,
        inner.y + header.get_height() + max(5, int(6 * dcfg.UI_SCALE)),
        inner.width,
        max(0, inner.height - header.get_height() - max(5, int(6 * dcfg.UI_SCALE))),
    )
    pygame.draw.rect(screen, fill, content, border_radius=8)
    pygame.draw.rect(screen, accent, content, 2, border_radius=8)

    anim_w = max(210, min(int(content.width * 0.42), 340))
    anim_rect = pygame.Rect(
        content.right - anim_w - max(8, int(10 * dcfg.UI_SCALE)),
        content.y + max(8, int(10 * dcfg.UI_SCALE)),
        anim_w,
        max(52, content.height - max(16, int(20 * dcfg.UI_SCALE))),
    )
    text_rect = pygame.Rect(
        content.x + max(10, int(12 * dcfg.UI_SCALE)),
        content.y + max(8, int(10 * dcfg.UI_SCALE)),
        max(30, anim_rect.x - content.x - max(22, int(26 * dcfg.UI_SCALE))),
        content.height - max(16, int(20 * dcfg.UI_SCALE)),
    )

    title_font = pygame.font.Font(None, max(22, int(31 * dcfg.UI_SCALE)))
    title_font.set_bold(True)
    line_font = pygame.font.Font(None, max(18, int(25 * dcfg.UI_SCALE)))

    y = text_rect.y
    title = str(hint_context.get("title", "Choose a piece"))
    for line in _wrap(title, title_font, text_rect.width)[:2]:
        surf = title_font.render(line, True, (250, 250, 245))
        screen.blit(surf, (text_rect.x, y))
        y += surf.get_height() + 1

    lines = [
        (str(hint_context.get("action_line", "")), line_font, (245, 245, 245)),
    ]
    y += max(2, int(3 * dcfg.UI_SCALE))
    bottom = text_rect.bottom
    for text, font, colour in lines:
        if not text or y >= bottom:
            continue
        for line in _wrap(text, font, text_rect.width):
            if y + font.get_height() > bottom:
                break
            surf = font.render(line, True, colour)
            screen.blit(surf, (text_rect.x, y))
            y += surf.get_height() + 1
        y += max(1, int(2 * dcfg.UI_SCALE))

    _draw_hint_animation(screen, anim_rect, str(hint_context.get("animation_key", "flip_marker")))


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
    hdr = title_font.render("Game Log History", True, (245, 245, 245))
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
    wrong_pos = setup_piece_status is not None and detected and not correct
    status_label = ""
    status_color = C_MUTED
    if setup_piece_status is not None:
        if not detected:
            status_label = "Not detected"
            status_color = C_MUTED
        elif not correct:
            status_label = "Wrong position"
            status_color = (255, 235, 120)
        else:
            status_label = "Detected"
            status_color = (100, 220, 130)

    inactive = setup_piece_status is not None and not detected
    if inactive:
        card_bg = (30, 30, 44)
    elif wrong_pos:
        card_bg = (46, 42, 28)
    else:
        card_bg = (34, 34, 55)

    if wrong_pos:
        card_border = (255, 210, 65)
        border_w = 3
    elif is_selected:
        card_border = (255, 220, 70)
        border_w = 2
    else:
        card_border = C_PANEL_BORDER
        border_w = 1

    text_color = (155, 155, 165) if inactive else (245, 245, 245)
    if is_selected:
        pulse = (math.sin(pygame.time.get_ticks() / 650 * math.tau) + 1.0) * 0.5
        glow_alpha = int(58 + 52 * pulse)
        glow_rect = rect.inflate(max(8, int(10 * s)), max(8, int(10 * s)))
        glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(
            glow,
            (255, 225, 85, glow_alpha),
            glow.get_rect(),
            border_radius=max(9, int(11 * s)),
        )
        screen.blit(glow, glow_rect.topleft)
    pygame.draw.rect(screen, card_bg, rect, border_radius=8)
    pygame.draw.rect(screen, card_border, rect, width=border_w, border_radius=8)

    # --- Header (name) ---
    name_surf = f_card.render(piece.id, True, text_color)
    name_x = rect.x + pad_x
    name_y = rect.y + pad_y
    screen.blit(name_surf, (name_x, name_y))
    header_h = name_surf.get_height()
    status_h = 0
    if status_label:
        status_surf = f_small.render(status_label, True, status_color)
        if wrong_pos:
            pill = pygame.Rect(
                name_x - 4,
                name_y + header_h - 1,
                rect.width - pad_x * 2 + 8,
                status_surf.get_height() + 6,
            )
            glow = pygame.Surface(pill.size, pygame.SRCALPHA)
            pygame.draw.rect(
                glow,
                (255, 210, 70, 88),
                glow.get_rect(),
                border_radius=6,
            )
            screen.blit(glow, pill.topleft)
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
        hp_fill_color = (255, 0, 0) if piece.faction == Faction.HumanSide else C_HP_FULL  # #FF0000
        pygame.draw.rect(
            screen,
            hp_fill_color,
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

    # Playing only: soft halo + bright rim for the roster whose faction owns the selected piece.
    if setup_status is None and selected_pid:
        sel_piece = state.pieces.get(selected_pid)
        if sel_piece is not None and sel_piece.faction == faction:
            s = dcfg.UI_SCALE
            pulse = (math.sin(pygame.time.get_ticks() / 650 * math.tau) + 1.0) * 0.5
            base_pad = max(6, int(8 * s))
            if faction == Faction.HumanSide:
                soft = (255, 110, 140, int(38 + 28 * pulse))
                mid = (255, 150, 175, int(95 + 55 * pulse))
                rim = (255, 210, 225, int(175 + 70 * pulse))
            else:
                soft = (100, 255, 150, int(38 + 28 * pulse))
                mid = (130, 255, 175, int(95 + 55 * pulse))
                rim = (200, 255, 215, int(175 + 70 * pulse))
            for extra, color, lw_scale in (
                (base_pad + 14, soft, 10),
                (base_pad + 7, mid, 5),
                (base_pad + 2, rim, 3),
            ):
                outer = panel_rect.inflate(extra * 2, extra * 2)
                glow = pygame.Surface(outer.size, pygame.SRCALPHA)
                br = max(14, int(12 + extra * 0.45))
                pygame.draw.rect(
                    glow,
                    color,
                    glow.get_rect(),
                    width=max(2, int(lw_scale * s)),
                    border_radius=br,
                )
                screen.blit(glow, outer.topleft)


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

    setup_hdr_color = (245, 245, 245)

    x = left_col.x + 4
    y = left_col.y
    hdr = f_section.render("Setup Progress", True, setup_hdr_color)
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
    hdr = f_section.render("Missing Pieces", True, setup_hdr_color)
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
    hdr = f_section.render("Setup Log", True, setup_hdr_color)
    screen.blit(hdr, (x, y))
    y += hdr.get_height() + 4
    setup_log_font_size = max(18, int(f_small.get_height() * 1.18))
    setup_log_font = pygame.font.Font(None, setup_log_font_size)

    def _setup_log_color(entry: str) -> tuple[int, int, int]:
        low = entry.lower()
        if "warning" in low or "wrong position" in low:
            return (255, 225, 110)  # yellow for wrong-position warnings
        if (
            "setup complete" in low
            or "detected piece" in low
            or "board detected" in low
        ):
            return (105, 225, 125)  # green for successful recognition milestones
        return C_PANEL_TEXT

    entries = log or []
    if not entries:
        surf = f_body.render("Keep camera on the board.", True, C_MUTED)
        screen.blit(surf, (x + 6, y))
        return
    for entry in entries[:4]:
        color = _setup_log_color(entry)
        for line in _wrap(entry, setup_log_font, right_col.width - 10):
            surf = setup_log_font.render(line, True, color)
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
    tutorial_hover: bool = False,
    log_modal_open: bool = False,
    log_modal_scroll: int = 0,
    btn_enabled: bool = True,
    setup_status: dict | None = None,
    notification_errors: list[str] | None = None,
    hint_context: dict | None = None,
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
        _draw_panel_box(screen, bottom_rect)
        _draw_setup_columns(screen, setup_status, left_col, mid_col, right_col, fb, fs, f_section, log)

        setup_btn_w = max(btn_w + 54, int(290 * dcfg.UI_SCALE))
        setup_btn_h = max(btn_h + 8, int(46 * dcfg.UI_SCALE))
        BUTTON_RECT.update(
            action_row.centerx - setup_btn_w // 2,
            action_row.centery - setup_btn_h // 2,
            setup_btn_w,
            setup_btn_h,
        )
        # Setup stage uses automatic camera detection; the extra placeholder
        # buttons (Camera Scan / Setup) are intentionally not shown.
        # Also clear their click rects to avoid hover/click confusion.
        SURRENDER_RECT.update(0, 0, 1, 1)
        DRAW_RECT.update(0, 0, 1, 1)

        disabled_bg = (70, 70, 70)
        disabled_text = (150, 150, 150)

        if btn_enabled:
            pulse = (pygame.time.get_ticks() % 1200) / 1200.0
            pulse_alpha = int(45 + 40 * (1.0 + math.sin(pulse * math.tau)) / 2.0)
            glow_rect = BUTTON_RECT.inflate(max(12, int(18 * dcfg.UI_SCALE)), max(8, int(12 * dcfg.UI_SCALE)))
            glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(
                glow,
                (90, 230, 130, pulse_alpha),
                glow.get_rect(),
                border_radius=max(10, int(12 * dcfg.UI_SCALE)),
            )
            screen.blit(glow, glow_rect.topleft)

        btn_colour = (C_BTN_HOVER if btn_hover else C_BTN_BG) if btn_enabled else disabled_bg
        btn_text = C_BTN_TEXT if btn_enabled else disabled_text
        pygame.draw.rect(screen, btn_colour, BUTTON_RECT, border_radius=8)
        btn_border = (105, 235, 135) if btn_enabled else C_PANEL_BORDER
        pygame.draw.rect(screen, btn_border, BUTTON_RECT, 2 if btn_enabled else 1, border_radius=8)
        btn_surf = fbtn.render(btn_label, True, btn_text)
        screen.blit(btn_surf, (BUTTON_RECT.centerx - btn_surf.get_width() // 2, BUTTON_RECT.centery - btn_surf.get_height() // 2))
        return int(log_modal_scroll)

    # Playing stage layout: Notification | Hint | Game Log
    # Hide legacy action buttons and keep their rects inactive.
    BUTTON_RECT.update(0, 0, 1, 1)
    SURRENDER_RECT.update(0, 0, 1, 1)
    DRAW_RECT.update(0, 0, 1, 1)

    battle_status_rect = pygame.Rect(
        dcfg.LEFT_PANEL_X,
        dcfg.BOTTOM_PANEL_Y,
        dcfg.SIDE_PANEL_W,
        dcfg.BOTTOM_PANEL_H,
    )
    tutorial_rect = pygame.Rect(
        dcfg.BOARD_IMAGE_LEFT,
        dcfg.BOTTOM_PANEL_Y,
        dcfg.BOARD_IMAGE_W,
        dcfg.BOTTOM_PANEL_H,
    )
    battle_log_rect = pygame.Rect(
        dcfg.RIGHT_PANEL_X,
        dcfg.BOTTOM_PANEL_Y,
        dcfg.SIDE_PANEL_W,
        dcfg.BOTTOM_PANEL_H,
    )
    _draw_panel_box(screen, battle_status_rect)
    _draw_panel_box(screen, tutorial_rect)
    _draw_panel_box(screen, battle_log_rect)

    # --- Left panel: Notification (playing stage only; setup uses early return) ---
    sx = battle_status_rect.x + dcfg.PANEL_PAD
    sy = battle_status_rect.y + dcfg.PANEL_PAD
    max_notif_w = max(40, battle_status_rect.width - dcfg.PANEL_PAD * 2 - 8)
    notif_body_font = pygame.font.Font(None, max(17, int(22 * dcfg.UI_SCALE)))
    errs: list[str] = list(notification_errors or []) if setup_status is None else []
    if setup_status is None and errs:
        err_title_font, err_detail_font = _notification_error_fonts()
        inner_flash = battle_status_rect.inflate(-6, -6)
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * (2 * math.pi / 900))
        flash_alpha = int(55 + 85 * pulse)
        flash_surf = pygame.Surface((inner_flash.width, inner_flash.height), pygame.SRCALPHA)
        flash_surf.fill((220, 25, 35, min(155, flash_alpha)))
        screen.blit(flash_surf, inner_flash.topleft)
        warn_hdr = err_title_font.render("[!] Problem Detected", True, (255, 235, 120))
        screen.blit(warn_hdr, (sx, sy))
        cy = sy + warn_hdr.get_height() + max(4, int(6 * dcfg.UI_SCALE))
        for msg in errs[:4]:
            for line in _wrap(msg, err_detail_font, max_notif_w):
                line_surf = err_detail_font.render(line, True, (255, 255, 255))
                shadow = err_detail_font.render(line, True, (40, 0, 0))
                screen.blit(shadow, (sx + 1, cy + 1))
                screen.blit(line_surf, (sx, cy))
                cy += line_surf.get_height() + 1
                if cy > battle_status_rect.bottom - dcfg.PANEL_PAD - 4:
                    break
            if cy > battle_status_rect.bottom - dcfg.PANEL_PAD - 4:
                break
    elif setup_status is None:
        status_hdr = f_section.render("Notification", True, C_MSG_TEXT)
        screen.blit(status_hdr, (sx, sy))
        cy = sy + status_hdr.get_height() + max(4, int(6 * dcfg.UI_SCALE))
        ok_surf = notif_body_font.render("No current issues.", True, C_MUTED)
        screen.blit(ok_surf, (sx, cy))

    # --- Middle panel: Hint (playing stage only) ---
    _draw_hint_panel(screen, tutorial_rect, hint_context, f_section)

    # --- Right panel: Game Log (action-focused display) ---
    log_entries = log if log else []
    action_tokens = (
        " move", " moved", " attack", "attacked", "damage", " hit", "kill", "death",
        "died", "heal", "buff", "trigger", "spawned", "reached",
    )
    display_entries = [
        entry for entry in log_entries
        if any(token in f" {entry.lower()} " for token in action_tokens)
    ]
    lx = battle_log_rect.x + dcfg.PANEL_PAD
    ly = battle_log_rect.y + dcfg.PANEL_PAD
    log_hdr = f_section.render("Game Log", True, C_MSG_TEXT)
    screen.blit(log_hdr, (lx, ly))
    if log_entries:
        exp_sz = max(18, int(22 * dcfg.UI_SCALE))
        LOG_EXPAND_RECT.update(battle_log_rect.right - exp_sz - 6, ly + 2, exp_sz, exp_sz)
        _draw_expand_icon(screen, LOG_EXPAND_RECT)
    else:
        LOG_EXPAND_RECT.update(0, 0, 1, 1)
    ly += log_hdr.get_height() + 2
    if display_entries:
        flog = pygame.font.Font(None, max(17, int(22 * dcfg.UI_SCALE)))
        flog.set_bold(True)
        for entry in display_entries[:6]:
            ec = C_AMMO if ("✦" in entry or "trigger" in entry.lower()) else C_PANEL_TEXT
            for line in _wrap(entry, flog, battle_log_rect.width - dcfg.PANEL_PAD * 2 - 8):
                s = flog.render(line, True, ec)
                screen.blit(s, (lx + 2, ly))
                ly += s.get_height() + 1
            if ly > battle_log_rect.bottom - 6:
                break
    else:
        empty = fb.render("No recent piece actions.", True, C_MUTED)
        screen.blit(empty, (lx + 2, ly))

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
    """Word-wrap text and split long tokens so narrow panels never overflow."""
    def split_long_word(word: str) -> list[str]:
        if font.size(word)[0] <= max_w:
            return [word]
        chunks: list[str] = []
        current = ""
        for ch in word:
            test = current + ch
            if current and font.size(test)[0] > max_w:
                chunks.append(current)
                current = ch
            else:
                current = test
        if current:
            chunks.append(current)
        return chunks or [word]

    words: list[str] = []
    for word in text.split():
        words.extend(split_long_word(word))
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
