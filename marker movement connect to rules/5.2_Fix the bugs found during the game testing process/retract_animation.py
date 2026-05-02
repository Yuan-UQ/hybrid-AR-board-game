"""
Illegal-move retract animation.

Renders a translucent "ghost" piece that slides from the (illegal) destination
cell back to the original cell, telling the player "put your physical piece
back to its starting square and try again".

This module is purely a UI overlay — it does NOT mutate game state. The main
loop owns the active retract entries (so it can also gate selection logic on
whether a retract is currently animating).
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from xiangqi_arena.core.enums import Faction
from xiangqi_arena.ui.board_renderer import node_to_pixel
from xiangqi_arena.ui.piece_renderer import draw_piece_sprite_at
import xiangqi_arena.ui.display_config as dcfg
from xiangqi_arena.ui.display_config import (
    C_HUMANSIDE_FILL, C_ORCSIDE_FILL, C_PIECE_BORDER, PIECE_RADIUS,
)

Pos = tuple[int, int]
DEFAULT_DURATION_MS = 550
_GHOST_ALPHA = 170
_TINT_ILLEGAL = (255, 80, 80)


@dataclass
class RetractAnim:
    """One active retract animation."""
    piece_id: str
    faction: Faction
    illegal_pos: Pos
    target_pos: Pos
    started_ms: int
    duration_ms: int = DEFAULT_DURATION_MS

    def progress(self, now_ms: int) -> float:
        elapsed = now_ms - self.started_ms
        return max(0.0, min(1.0, elapsed / max(1, self.duration_ms)))

    def is_finished(self, now_ms: int) -> bool:
        return self.progress(now_ms) >= 1.0


def _ease_out_cubic(t: float) -> float:
    inv = 1.0 - t
    return 1.0 - inv * inv * inv


def make_retract(
    piece_id: str,
    faction: Faction,
    illegal_pos: Pos,
    target_pos: Pos,
    now_ms: int,
    *,
    duration_ms: int = DEFAULT_DURATION_MS,
) -> RetractAnim:
    return RetractAnim(
        piece_id=piece_id,
        faction=faction,
        illegal_pos=tuple(illegal_pos),
        target_pos=tuple(target_pos),
        started_ms=int(now_ms),
        duration_ms=int(duration_ms),
    )


def is_finished(anim: RetractAnim | None, now_ms: int) -> bool:
    if anim is None:
        return True
    return anim.is_finished(now_ms)


def draw_retracts(
    screen: pygame.Surface,
    anims: list[RetractAnim],
) -> None:
    if not anims:
        return
    now_ms = pygame.time.get_ticks()
    for anim in anims:
        t = _ease_out_cubic(anim.progress(now_ms))
        from_px, from_py = node_to_pixel(*anim.illegal_pos)
        to_px, to_py = node_to_pixel(*anim.target_pos)
        px = int(from_px + (to_px - from_px) * t)
        py = int(from_py + (to_py - from_py) * t)
        _draw_one_ghost(screen, anim, px, py)


def _draw_one_ghost(
    screen: pygame.Surface,
    anim: RetractAnim,
    px: int,
    py: int,
) -> None:
    drew_sprite = draw_piece_sprite_at(
        screen,
        anim.piece_id,
        anim.faction,
        px,
        py,
        alpha=_GHOST_ALPHA,
        tint=_TINT_ILLEGAL,
    )
    if drew_sprite:
        return

    # Fallback for pieces without configured sprites: translucent disc.
    fill = C_HUMANSIDE_FILL if anim.faction is Faction.HumanSide else C_ORCSIDE_FILL
    surf = pygame.Surface((PIECE_RADIUS * 2 + 4, PIECE_RADIUS * 2 + 4), pygame.SRCALPHA)
    pygame.draw.circle(
        surf,
        (*_TINT_ILLEGAL, 120),
        (PIECE_RADIUS + 2, PIECE_RADIUS + 2),
        PIECE_RADIUS + 2,
    )
    pygame.draw.circle(
        surf,
        (*fill, _GHOST_ALPHA),
        (PIECE_RADIUS + 2, PIECE_RADIUS + 2),
        PIECE_RADIUS,
    )
    pygame.draw.circle(
        surf,
        C_PIECE_BORDER,
        (PIECE_RADIUS + 2, PIECE_RADIUS + 2),
        PIECE_RADIUS,
        2,
    )
    screen.blit(surf, (px - (PIECE_RADIUS + 2), py - (PIECE_RADIUS + 2)))
