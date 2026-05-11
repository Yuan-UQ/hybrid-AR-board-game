"""
Highlight rendering.

Draws semi-transparent overlays for:
  - Selected piece    → floating pixel arrow
  - Valid move nodes  → semi-transparent green circle
  - Valid attack nodes → semi-transparent HumanSide circle + floating pixel arrow
"""

from __future__ import annotations

import math
from pathlib import Path

import pygame

from xiangqi_arena.core.utils import Pos
from xiangqi_arena.ui.board_renderer import node_to_pixel
import xiangqi_arena.ui.display_config as dcfg
from xiangqi_arena.ui.display_config import (
    C_ATTACK_DOT, C_MOVE_DOT,
)
_ALPHA_MOVE     = 160
_ALPHA_ATTACK   = 170
_SELECT_ARROW_OUTLINE = (170, 115, 0)
_SELECT_ARROW_FILL    = (255, 220, 35)
_ATTACK_ARROW_OUTLINE = (120, 0, 0)
_ATTACK_ARROW_FILL    = (235, 35, 35)
_ARROW_FLOAT_PX = 4
_ARROW_FLOAT_MS = 700
_ATTACK_ARROW_Y_OFFSET = 2
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ATTACK_EFFECT_PATH = _PROJECT_ROOT / "ArtResource" / "Effect" / "Attack_effect.png"
_ATTACK_EFFECT_FRAMES: list[pygame.Surface] | None = None


def draw_highlights(
    screen: pygame.Surface,
    selected_pos: Pos | None,
    valid_moves: list[Pos],
    valid_attacks: list[Pos],
    show_attack_effect: bool = False,
    attack_arrow_nodes: list[Pos] | None = None,
    show_selected_arrow: bool = True,
) -> None:
    """Draw all selection and legality highlights."""
    _draw_valid_moves(screen, selected_pos, valid_moves)
    _draw_valid_attacks(
        screen,
        valid_attacks,
        show_attack_effect=show_attack_effect,
        show_arrows=True,
        attack_arrow_nodes=attack_arrow_nodes,
    )
    if show_selected_arrow and selected_pos is not None:
        _draw_selected(screen, selected_pos)


def draw_attack_target_arrows(
    screen: pygame.Surface,
    nodes: list[Pos],
) -> None:
    """Draw attack target arrows only (for top-layer rendering)."""
    _draw_valid_attacks(
        screen,
        nodes,
        show_attack_effect=False,
        show_arrows=True,
        attack_arrow_nodes=nodes,
        draw_dots=False,
    )


def draw_attack_effect_overlays(
    screen: pygame.Surface,
    nodes: list[Pos],
) -> None:
    """Draw attack-range effect sprites only (for top-layer rendering)."""
    _draw_valid_attacks(
        screen,
        nodes,
        show_attack_effect=True,
        show_arrows=False,
        attack_arrow_nodes=None,
        draw_dots=False,
    )


def draw_selected_arrow(
    screen: pygame.Surface,
    selected_pos: Pos | None,
) -> None:
    """Draw selected-piece arrow only (for top-layer rendering)."""
    if selected_pos is not None:
        _draw_selected(screen, selected_pos)


def _draw_valid_moves(
    screen: pygame.Surface,
    selected_pos: Pos | None,
    nodes: list[Pos],
) -> None:
    if not nodes:
        return
    _draw_move_path_guides(screen, selected_pos, nodes)
    for pos in nodes:
        _draw_valid_move_target(screen, pos)


def _pulse_alpha(
    *,
    base: int,
    amplitude: int,
    period_ms: int,
    phase_shift: float = 0.0,
) -> int:
    """Smooth alpha pulse helper for move indicators."""
    t = pygame.time.get_ticks()
    pulse = (math.sin((t / max(1, period_ms)) * math.tau + phase_shift) + 1.0) * 0.5
    return max(0, min(255, int(base + amplitude * pulse)))


def _draw_move_path_guides(
    screen: pygame.Surface,
    selected_pos: Pos | None,
    move_nodes: list[Pos],
) -> None:
    if selected_pos is None or not move_nodes:
        return
    sx, sy = node_to_pixel(*selected_pos)
    line_alpha = _pulse_alpha(base=48, amplitude=34, period_ms=1150, phase_shift=0.6)
    line_color = (85, 255, 170, line_alpha)
    seg_len = max(8, int(11 * dcfg.UI_SCALE))
    gap_len = max(6, int(7 * dcfg.UI_SCALE))

    for pos in move_nodes:
        tx, ty = node_to_pixel(*pos)
        dx = tx - sx
        dy = ty - sy
        dist = math.hypot(dx, dy)
        if dist < 1:
            continue
        ux = dx / dist
        uy = dy / dist
        progress = 0.0
        while progress < dist:
            start = progress
            end = min(progress + seg_len, dist)
            x1 = int(round(sx + ux * start))
            y1 = int(round(sy + uy * start))
            x2 = int(round(sx + ux * end))
            y2 = int(round(sy + uy * end))
            pygame.draw.line(screen, line_color, (x1, y1), (x2, y2), 2)
            progress += seg_len + gap_len


def _draw_valid_move_target(screen: pygame.Surface, pos: Pos) -> None:
    px, py = node_to_pixel(*pos)
    base_rad = dcfg.HIGHLIGHT_MOVE_R
    outer_rad = max(base_rad + 8, int(base_rad * 1.9))
    core_rad = max(3, int(base_rad * 0.36))
    ring_w = max(2, int(3 * dcfg.UI_SCALE))

    fill_alpha = _pulse_alpha(base=72, amplitude=40, period_ms=1050)
    ring_alpha = _pulse_alpha(base=175, amplitude=60, period_ms=1050, phase_shift=1.1)
    center_alpha = _pulse_alpha(base=210, amplitude=45, period_ms=780, phase_shift=0.35)

    # Semi-transparent drop-area fill.
    fill_surf = pygame.Surface((outer_rad * 2, outer_rad * 2), pygame.SRCALPHA)
    cr, cg, cb = C_MOVE_DOT
    pygame.draw.circle(fill_surf, (cr, cg, cb, fill_alpha), (outer_rad, outer_rad), outer_rad)
    screen.blit(fill_surf, (px - outer_rad, py - outer_rad))

    # Bright target ring.
    ring_surf = pygame.Surface((outer_rad * 2, outer_rad * 2), pygame.SRCALPHA)
    pygame.draw.circle(
        ring_surf,
        (95, 255, 170, ring_alpha),
        (outer_rad, outer_rad),
        outer_rad - 1,
        ring_w,
    )
    screen.blit(ring_surf, (px - outer_rad, py - outer_rad))

    # Small bright center dot.
    center_surf = pygame.Surface((core_rad * 2, core_rad * 2), pygame.SRCALPHA)
    pygame.draw.circle(
        center_surf,
        (205, 255, 220, center_alpha),
        (core_rad, core_rad),
        core_rad,
    )
    screen.blit(center_surf, (px - core_rad, py - core_rad))


def _draw_valid_attacks(
    screen: pygame.Surface,
    nodes: list[Pos],
    show_attack_effect: bool,
    show_arrows: bool,
    attack_arrow_nodes: list[Pos] | None,
    draw_dots: bool = True,
) -> None:
    if not nodes:
        return
    arrow_nodes = set(nodes if attack_arrow_nodes is None else attack_arrow_nodes)
    for pos in nodes:
        px, py = node_to_pixel(*pos)
        if draw_dots:
            _draw_attack_target(screen, pos)
        if show_attack_effect:
            _draw_attack_effect(screen, px, py)
        if show_arrows and pos in arrow_nodes:
            _draw_attack_target_arrow(screen, px, py)


def _attack_pulse_alpha(
    *,
    base: int,
    amplitude: int,
    period_ms: int,
    phase_shift: float = 0.0,
) -> int:
    """Smooth pulse helper dedicated to attack lock-on markers."""
    t = pygame.time.get_ticks()
    pulse = (math.sin((t / max(1, period_ms)) * math.tau + phase_shift) + 1.0) * 0.5
    return max(0, min(255, int(base + amplitude * pulse)))


def _draw_attack_target(screen: pygame.Surface, pos: Pos) -> None:
    """Render a layered red lock-on marker for valid attack nodes."""
    px, py = node_to_pixel(*pos)
    base_rad = dcfg.HIGHLIGHT_ATTACK_R
    glow_rad = max(base_rad + 10, int(base_rad * 2.2))
    ring_rad = max(base_rad + 4, int(base_rad * 1.35))
    center_rad = max(3, int(base_rad * 0.42))
    ring_w = max(2, int(3 * dcfg.UI_SCALE))
    cross_len = max(8, int(base_rad * 1.35))
    cross_gap = max(2, int(base_rad * 0.35))
    cross_w = max(2, int(2 * dcfg.UI_SCALE))

    glow_alpha = _attack_pulse_alpha(base=72, amplitude=42, period_ms=940)
    ring_alpha = _attack_pulse_alpha(base=180, amplitude=60, period_ms=940, phase_shift=0.9)
    center_alpha = _attack_pulse_alpha(base=205, amplitude=50, period_ms=730, phase_shift=0.35)
    cross_alpha = _attack_pulse_alpha(base=195, amplitude=55, period_ms=850, phase_shift=1.2)

    # 1) Glow first.
    glow = pygame.Surface((glow_rad * 2, glow_rad * 2), pygame.SRCALPHA)
    pygame.draw.circle(glow, (255, 45, 45, glow_alpha), (glow_rad, glow_rad), glow_rad)
    screen.blit(glow, (px - glow_rad, py - glow_rad))

    # 2) Bright ring + center.
    ring = pygame.Surface((ring_rad * 2, ring_rad * 2), pygame.SRCALPHA)
    pygame.draw.circle(ring, (255, 85, 85, ring_alpha), (ring_rad, ring_rad), ring_rad, ring_w)
    screen.blit(ring, (px - ring_rad, py - ring_rad))

    center = pygame.Surface((center_rad * 2, center_rad * 2), pygame.SRCALPHA)
    pygame.draw.circle(center, (255, 225, 225, center_alpha), (center_rad, center_rad), center_rad)
    screen.blit(center, (px - center_rad, py - center_rad))

    # 3) Crosshair last.
    cross_color = (255, 120, 120, cross_alpha)
    pygame.draw.line(screen, cross_color, (px - cross_len, py), (px - cross_gap, py), cross_w)
    pygame.draw.line(screen, cross_color, (px + cross_gap, py), (px + cross_len, py), cross_w)
    pygame.draw.line(screen, cross_color, (px, py - cross_len), (px, py - cross_gap), cross_w)
    pygame.draw.line(screen, cross_color, (px, py + cross_gap), (px, py + cross_len), cross_w)


def _draw_selected(screen: pygame.Surface, pos: Pos) -> None:
    px, py = node_to_pixel(*pos)
    float_offset = int(
        math.sin(pygame.time.get_ticks() / _ARROW_FLOAT_MS * math.tau)
        * _ARROW_FLOAT_PX
    )
    tip_y = py - dcfg.PIECE_RADIUS - 15 + float_offset
    _draw_pixel_arrow(screen, px, tip_y, _SELECT_ARROW_OUTLINE, _SELECT_ARROW_FILL)


def _draw_attack_target_arrow(screen: pygame.Surface, px: int, py: int) -> None:
    float_offset = int(
        math.sin(pygame.time.get_ticks() / _ARROW_FLOAT_MS * math.tau)
        * _ARROW_FLOAT_PX
    )
    # Extra red pulse behind the directional arrow to reinforce attack intent.
    pulse_alpha = _attack_pulse_alpha(base=95, amplitude=55, period_ms=780, phase_shift=0.8)
    pulse_rad = max(7, int(9 * dcfg.UI_SCALE))
    pulse = pygame.Surface((pulse_rad * 2, pulse_rad * 2), pygame.SRCALPHA)
    pygame.draw.circle(pulse, (255, 70, 70, pulse_alpha), (pulse_rad, pulse_rad), pulse_rad)
    screen.blit(pulse, (px - pulse_rad, py - dcfg.PIECE_RADIUS - pulse_rad))
    tip_y = py - dcfg.PIECE_RADIUS - _ATTACK_ARROW_Y_OFFSET + float_offset
    _draw_pixel_arrow(screen, px, tip_y, _ATTACK_ARROW_OUTLINE, _ATTACK_ARROW_FILL)


def _draw_pixel_arrow(
    screen: pygame.Surface,
    cx: int,
    tip_y: int,
    outline_colour: tuple[int, int, int],
    fill_colour: tuple[int, int, int],
) -> None:
    unit = 4

    # Draw an outlined, blocky down arrow. The tip points at the selected piece.
    outer_blocks = [
        (-1, -7), (0, -7), (1, -7),
        (-1, -6), (0, -6), (1, -6),
        (-1, -5), (0, -5), (1, -5),
        (-3, -4), (-2, -4), (-1, -4), (0, -4), (1, -4), (2, -4), (3, -4),
        (-2, -3), (-1, -3), (0, -3), (1, -3), (2, -3),
        (-1, -2), (0, -2), (1, -2),
        (0, -1),
    ]
    inner_blocks = [
        (0, -6),
        (0, -5),
        (-2, -4), (-1, -4), (0, -4), (1, -4), (2, -4),
        (-1, -3), (0, -3), (1, -3),
        (0, -2),
    ]

    for bx, by in outer_blocks:
        rect = pygame.Rect(cx + bx * unit, tip_y + by * unit, unit, unit)
        pygame.draw.rect(screen, outline_colour, rect)
    for bx, by in inner_blocks:
        rect = pygame.Rect(cx + bx * unit, tip_y + by * unit, unit, unit)
        pygame.draw.rect(screen, fill_colour, rect)


def _draw_attack_effect(screen: pygame.Surface, px: int, py: int) -> None:
    frames = _get_attack_effect_frames()
    if not frames:
        return
    frame_idx = int((pygame.time.get_ticks() // 80) % len(frames))
    frame = frames[frame_idx]
    screen.blit(frame, (px - frame.get_width() // 2, py - frame.get_height()))


def _get_attack_effect_frames() -> list[pygame.Surface]:
    global _ATTACK_EFFECT_FRAMES
    if _ATTACK_EFFECT_FRAMES is None:
        _ATTACK_EFFECT_FRAMES = _load_attack_effect_frames()
    return _ATTACK_EFFECT_FRAMES


def _load_attack_effect_frames() -> list[pygame.Surface]:
    sheet = pygame.image.load(str(_ATTACK_EFFECT_PATH)).convert_alpha()
    frames: list[pygame.Surface] = []
    frame_w = 100
    frame_h = 100
    target_h = 30
    for x in range(0, sheet.get_width(), frame_w):
        frame = sheet.subsurface(pygame.Rect(x, 0, frame_w, frame_h)).copy()
        bounds = frame.get_bounding_rect(min_alpha=1)
        if bounds.width == 0 or bounds.height == 0:
            continue
        cropped = frame.subsurface(bounds).copy()
        target_w = max(1, int(cropped.get_width() * target_h / cropped.get_height()))
        frames.append(pygame.transform.scale(cropped, (target_w, target_h)))
    return frames
