"""
Dead piece marker rendering.

Dead pieces are drawn as grey circles with a HumanSide X, placed at their last
known position.  They don't block interaction — the board treats those
nodes as empty — but they remain visible until explicitly cleaned up.
"""

from __future__ import annotations

import pygame

from xiangqi_arena.core.enums import Faction
from xiangqi_arena.state.game_state import GameState
from xiangqi_arena.ui.board_renderer import node_to_pixel
from xiangqi_arena.ui.display_config import (
    C_ORCSIDE_FILL, C_DEAD_FILL, C_DEAD_X, C_PIECE_BORDER, C_PIECE_TEXT,
    C_HUMANSIDE_FILL, PIECE_LABELS, PIECE_RADIUS,
)

_ALPHA = 130   # transparency for dead pieces
_SPRITE_DEATH_ANIMATION_IDS = {
    "GeneralHuman",
    "ArcherHuman",
    "LancerHuman",
    "WizardHuman",
    "Soldier1Human",
    "Soldier2Human",
    "Soldier3Human",
    "GeneralOrc",
    "ArcherSkeleton",
    "RiderOrc",
    "Slime Orc",
    "Soldier1Orc",
    "Soldier2Skeleton",
    "Soldier3Skeleton",
}


def draw_dead_pieces(screen: pygame.Surface, state: GameState) -> None:
    """Draw all dead pieces as muted markers at their last position."""
    font = pygame.font.Font(None, 15)
    font.set_bold(True)

    for piece in state.pieces.values():
        if not piece.is_dead:
            continue
        if piece.id in _SPRITE_DEATH_ANIMATION_IDS:
            continue

        px, py = node_to_pixel(*piece.pos)

        # Faded circle
        surf = pygame.Surface((PIECE_RADIUS * 2 + 4, PIECE_RADIUS * 2 + 4),
                              pygame.SRCALPHA)
        cx = cy = PIECE_RADIUS + 2
        base = C_HUMANSIDE_FILL if piece.faction == Faction.HumanSide else C_ORCSIDE_FILL
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
