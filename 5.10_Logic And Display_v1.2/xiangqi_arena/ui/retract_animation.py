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
import math

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
_GHOST_ALPHA = 230
_TINT_ILLEGAL = (255, 35, 35)


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


def _draw_retract_target_beacon(screen: pygame.Surface, tx: int, ty: int, now_ms: int) -> None:
    """Single pulsing yellow ring at the legal cell the physical piece should return to."""
    pulse = (math.sin(now_ms / 300 * math.tau) + 1.0) * 0.5
    r = int(PIECE_RADIUS + 11 + 5 * pulse)
    sz = r * 2 + 6
    surf = pygame.Surface((sz, sz), pygame.SRCALPHA)
    cx, cy = sz // 2, sz // 2
    lw = max(3, int(4 * dcfg.UI_SCALE))
    pygame.draw.circle(
        surf,
        (255, 255, 200, int(130 + 110 * pulse)),
        (cx, cy),
        r,
        max(2, lw - 1),
    )
    screen.blit(surf, (tx - cx, ty - cy))


def _draw_retract_return_guide(
    screen: pygame.Surface,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> None:
    """Dashed guide from ghost toward the home intersection."""
    dx, dy = x1 - x0, y1 - y0
    dist = math.hypot(dx, dy)
    if dist < 10:
        return
    ux, uy = dx / dist, dy / dist
    dash = max(7, int(10 * dcfg.UI_SCALE))
    gap = max(5, int(6 * dcfg.UI_SCALE))
    pos = dash * 0.25
    col = (255, 240, 120)
    w = max(2, int(4 * dcfg.UI_SCALE))
    while pos < dist - 6:
        p0 = (int(x0 + ux * pos), int(y0 + uy * pos))
        p1 = (int(x0 + ux * min(pos + dash, dist)), int(y0 + uy * min(pos + dash, dist)))
        pygame.draw.line(screen, col, p0, p1, w)
        pos += dash + gap


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
        _draw_retract_target_beacon(screen, to_px, to_py, now_ms)
        px = int(from_px + (to_px - from_px) * t)
        py = int(from_py + (to_py - from_py) * t)
        _draw_retract_return_guide(screen, px, py, to_px, to_py)
        _draw_one_ghost(screen, anim, px, py, now_ms)


def _draw_one_ghost(
    screen: pygame.Surface,
    anim: RetractAnim,
    px: int,
    py: int,
    now_ms: int,
) -> None:
    pulse = (math.sin(now_ms / 260 * math.tau) + 1.0) * 0.5
    ring_r = dcfg.PIECE_RADIUS + 7
    ring_surf = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA)
    cx, cy = ring_r + 2, ring_r + 2
    ring_w = max(2, int(2 * dcfg.UI_SCALE))
    pygame.draw.circle(
        ring_surf,
        (255, 60, 60, int(90 + 85 * pulse)),
        (cx, cy),
        ring_r,
        ring_w,
    )
    screen.blit(ring_surf, (px - cx, py - cy))

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

    # Fallback for pieces without configured sprites: translucent disc + same ring as sprite path.
    fill = C_HUMANSIDE_FILL if anim.faction is Faction.HumanSide else C_ORCSIDE_FILL
    rr = dcfg.PIECE_RADIUS + 7
    sz = rr * 2 + 6
    surf = pygame.Surface((sz, sz), pygame.SRCALPHA)
    c = sz // 2
    ring_w = max(2, int(2 * dcfg.UI_SCALE))
    pr = dcfg.PIECE_RADIUS
    pygame.draw.circle(surf, (*fill, _GHOST_ALPHA), (c, c), pr)
    pygame.draw.circle(surf, (*_TINT_ILLEGAL, 185), (c, c), rr, ring_w)
    pygame.draw.circle(surf, C_PIECE_BORDER, (c, c), pr, 2)
    screen.blit(surf, (px - c, py - c))
