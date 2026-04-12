"""
Dead piece marker rendering.

Dead pieces are drawn as grey circles with a red X, placed at their last
known position.  They don't block interaction — the board treats those
nodes as empty — but they remain visible until explicitly cleaned up.
"""

from __future__ import annotations

import pygame

from xiangqi_arena.core.enums import Faction
from xiangqi_arena.state.game_state import GameState
from xiangqi_arena.ui.board_renderer import node_to_pixel
from xiangqi_arena.ui.display_config import (
    C_BLACK_FILL, C_DEAD_FILL, C_DEAD_X, C_PIECE_BORDER, C_PIECE_TEXT,
    C_RED_FILL, PIECE_LABELS, PIECE_RADIUS,
)

_ALPHA = 130   # transparency for dead pieces


def draw_dead_pieces(screen: pygame.Surface, state: GameState) -> None:
    """Draw all dead pieces as muted markers at their last position."""
    font = pygame.font.SysFont("Arial", 15, bold=True)

    for piece in state.pieces.values():
        if not piece.is_dead:
            continue

        px, py = node_to_pixel(*piece.pos)

        # Faded circle
        surf = pygame.Surface((PIECE_RADIUS * 2 + 4, PIECE_RADIUS * 2 + 4),
                              pygame.SRCALPHA)
        cx = cy = PIECE_RADIUS + 2
        base = C_RED_FILL if piece.faction == Faction.RED else C_BLACK_FILL
        r, g, b = C_DEAD_FILL
        pygame.draw.circle(surf, (r, g, b, _ALPHA), (cx, cy), PIECE_RADIUS)
        pygame.draw.circle(surf, (*C_PIECE_BORDER, _ALPHA), (cx, cy),
                           PIECE_RADIUS, 2)

        # X overlay
        s = PIECE_RADIUS - 5
        pygame.draw.line(surf, (*C_DEAD_X, 200),
                         (cx - s, cy - s), (cx + s, cy + s), 3)
        pygame.draw.line(surf, (*C_DEAD_X, 200),
                         (cx + s, cy - s), (cx - s, cy + s), 3)

        screen.blit(surf, (px - PIECE_RADIUS - 2, py - PIECE_RADIUS - 2))
