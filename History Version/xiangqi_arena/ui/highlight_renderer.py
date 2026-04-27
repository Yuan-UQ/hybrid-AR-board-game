"""
Highlight rendering.

Draws semi-transparent overlays for:
  - Selected piece    → thick gold ring
  - Valid move nodes  → semi-transparent green circle
  - Valid attack nodes → semi-transparent red circle
"""

from __future__ import annotations

import pygame

from xiangqi_arena.core.utils import Pos
from xiangqi_arena.ui.board_renderer import node_to_pixel
from xiangqi_arena.ui.display_config import (
    C_ATTACK_DOT, C_MOVE_DOT, C_SELECTED, PIECE_RADIUS,
)

_MOVE_RADIUS    = 10
_ATTACK_RADIUS  = 12
_ALPHA_MOVE     = 160
_ALPHA_ATTACK   = 170
_SELECT_WIDTH   = 4


def draw_highlights(
    screen: pygame.Surface,
    selected_pos: Pos | None,
    valid_moves: list[Pos],
    valid_attacks: list[Pos],
) -> None:
    """Draw all selection and legality highlights."""
    _draw_valid_moves(screen, valid_moves)
    _draw_valid_attacks(screen, valid_attacks)
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


def _draw_valid_attacks(screen: pygame.Surface, nodes: list[Pos]) -> None:
    if not nodes:
        return
    for pos in nodes:
        px, py = node_to_pixel(*pos)
        surf = pygame.Surface((_ATTACK_RADIUS * 2, _ATTACK_RADIUS * 2),
                              pygame.SRCALPHA)
        r, g, b = C_ATTACK_DOT
        pygame.draw.circle(surf, (r, g, b, _ALPHA_ATTACK),
                           (_ATTACK_RADIUS, _ATTACK_RADIUS), _ATTACK_RADIUS)
        screen.blit(surf, (px - _ATTACK_RADIUS, py - _ATTACK_RADIUS))


def _draw_selected(screen: pygame.Surface, pos: Pos) -> None:
    px, py = node_to_pixel(*pos)
    pygame.draw.circle(screen, C_SELECTED,
                       (px, py), PIECE_RADIUS + 4, _SELECT_WIDTH)
