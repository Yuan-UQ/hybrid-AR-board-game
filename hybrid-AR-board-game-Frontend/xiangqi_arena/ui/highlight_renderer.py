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
from xiangqi_arena.ui.display_config import (
    C_ATTACK_DOT, C_MOVE_DOT, PIECE_RADIUS,
)

_MOVE_RADIUS    = 10
_ATTACK_RADIUS  = 12
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
    _draw_valid_moves(screen, valid_moves)
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


def _draw_valid_moves(screen: pygame.Surface, nodes: list[Pos]) -> None:
    if not nodes:
        return
    for pos in nodes:
        px, py = node_to_pixel(*pos)
        surf = pygame.Surface((_MOVE_RADIUS * 2, _MOVE_RADIUS * 2),
                              pygame.SRCALPHA)
        r, g, b = C_MOVE_DOT
        pygame.draw.circle(surf, (r, g, b, _ALPHA_MOVE),
                           (_MOVE_RADIUS, _MOVE_RADIUS), _MOVE_RADIUS)
        screen.blit(surf, (px - _MOVE_RADIUS, py - _MOVE_RADIUS))


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
            surf = pygame.Surface((_ATTACK_RADIUS * 2, _ATTACK_RADIUS * 2),
                                  pygame.SRCALPHA)
            r, g, b = C_ATTACK_DOT
            pygame.draw.circle(surf, (r, g, b, _ALPHA_ATTACK),
                               (_ATTACK_RADIUS, _ATTACK_RADIUS), _ATTACK_RADIUS)
            screen.blit(surf, (px - _ATTACK_RADIUS, py - _ATTACK_RADIUS))
        if show_attack_effect:
            _draw_attack_effect(screen, px, py)
        if show_arrows and pos in arrow_nodes:
            _draw_attack_target_arrow(screen, px, py)


def _draw_selected(screen: pygame.Surface, pos: Pos) -> None:
    px, py = node_to_pixel(*pos)
    float_offset = int(
        math.sin(pygame.time.get_ticks() / _ARROW_FLOAT_MS * math.tau)
        * _ARROW_FLOAT_PX
    )
    tip_y = py - PIECE_RADIUS - 15 + float_offset
    _draw_pixel_arrow(screen, px, tip_y, _SELECT_ARROW_OUTLINE, _SELECT_ARROW_FILL)


def _draw_attack_target_arrow(screen: pygame.Surface, px: int, py: int) -> None:
    float_offset = int(
        math.sin(pygame.time.get_ticks() / _ARROW_FLOAT_MS * math.tau)
        * _ARROW_FLOAT_PX
    )
    tip_y = py - PIECE_RADIUS - _ATTACK_ARROW_Y_OFFSET + float_offset
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
