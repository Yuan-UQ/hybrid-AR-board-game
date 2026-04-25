"""
Event point rendering.

Draws all active event points on the board using a distinctive icon per type:
  Ammunition → orange diamond  (ATK +2)
  Medical    → green cross     (HP +1)
  Trap       → purple X        (HP -1)
"""

from __future__ import annotations

import pygame

from xiangqi_arena.core.enums import EventPointType
from xiangqi_arena.state.game_state import GameState
from xiangqi_arena.ui.board_renderer import node_to_pixel
from xiangqi_arena.ui.display_config import C_AMMO, C_MED, C_TRAP

_ICON_SIZE = 14   # half-size for drawing shapes


def draw_event_points(screen: pygame.Surface, state: GameState) -> None:
    """Draw all currently active (valid, un-triggered) event point icons."""
    for ep in state.event_points:
        if ep.is_valid and not ep.is_triggered:
            px, py = node_to_pixel(*ep.pos)
            if ep.event_type == EventPointType.AMMUNITION:
                _draw_diamond(screen, px, py, C_AMMO)
            elif ep.event_type == EventPointType.MEDICAL:
                _draw_cross(screen, px, py, C_MED)
            elif ep.event_type == EventPointType.TRAP:
                _draw_x(screen, px, py, C_TRAP)


# ---------------------------------------------------------------------------
# Shape helpers
# ---------------------------------------------------------------------------

def _draw_diamond(surf: pygame.Surface, cx: int, cy: int,
                  colour: tuple) -> None:
    """Filled diamond (rotated square)."""
    s = _ICON_SIZE
    points = [(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)]
    pygame.draw.polygon(surf, colour, points)
    pygame.draw.polygon(surf, (255, 255, 255), points, 2)


def _draw_cross(surf: pygame.Surface, cx: int, cy: int,
                colour: tuple) -> None:
    """Filled plus-sign cross."""
    s = _ICON_SIZE
    t = s // 3
    pygame.draw.rect(surf, colour, pygame.Rect(cx - t, cy - s, t * 2, s * 2))
    pygame.draw.rect(surf, colour, pygame.Rect(cx - s, cy - t, s * 2, t * 2))
    pygame.draw.rect(surf, (255, 255, 255),
                     pygame.Rect(cx - t, cy - s, t * 2, s * 2), 1)
    pygame.draw.rect(surf, (255, 255, 255),
                     pygame.Rect(cx - s, cy - t, s * 2, t * 2), 1)


def _draw_x(surf: pygame.Surface, cx: int, cy: int,
            colour: tuple) -> None:
    """Thick X shape."""
    s = _ICON_SIZE
    pygame.draw.line(surf, colour, (cx - s, cy - s), (cx + s, cy + s), 5)
    pygame.draw.line(surf, colour, (cx + s, cy - s), (cx - s, cy + s), 5)
    pygame.draw.line(surf, (255, 255, 255), (cx - s, cy - s), (cx + s, cy + s), 1)
    pygame.draw.line(surf, (255, 255, 255), (cx + s, cy - s), (cx - s, cy + s), 1)
