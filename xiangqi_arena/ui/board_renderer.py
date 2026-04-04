"""
Board rendering.

Draws the 9×10 intersection grid, river, palace diagonals, and coordinate
labels.  Pure presentation — reads no GameState; only uses geometry constants.
"""

from __future__ import annotations

import pygame

from xiangqi_arena.ui.display_config import (
    BOARD_BOTTOM, BOARD_LEFT, BOARD_RIGHT, BOARD_TOP, CELL,
    C_BG, C_BOARD_LINE, C_NODE_DOT, C_PALACE_LINE, C_RIVER_FILL,
)


def node_to_pixel(x: int, y: int) -> tuple[int, int]:
    """Convert a board node (x=0..8, y=0..9) to screen pixel (px, py)."""
    px = BOARD_LEFT + x * CELL
    py = BOARD_TOP  + (9 - y) * CELL
    return px, py


def draw_board(screen: pygame.Surface) -> None:
    """Draw the full board background, grid, river, and palace markings."""
    _draw_background(screen)
    _draw_river(screen)
    _draw_grid(screen)
    _draw_palaces(screen)
    _draw_nodes(screen)
    _draw_labels(screen)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _draw_background(screen: pygame.Surface) -> None:
    board_rect = pygame.Rect(
        BOARD_LEFT - 15, BOARD_TOP - 15,
        8 * CELL + 30, 9 * CELL + 30,
    )
    pygame.draw.rect(screen, C_BG, board_rect, border_radius=6)
    pygame.draw.rect(screen, C_BOARD_LINE, board_rect, width=2, border_radius=6)


def _draw_river(screen: pygame.Surface) -> None:
    """Tint the river strip (between y=4 and y=5) with a translucent blue."""
    _, y5 = node_to_pixel(0, 5)
    _, y4 = node_to_pixel(0, 4)
    river_rect = pygame.Rect(BOARD_LEFT, y5, 8 * CELL, y4 - y5)
    surf = pygame.Surface((river_rect.width, river_rect.height), pygame.SRCALPHA)
    surf.fill(C_RIVER_FILL)
    screen.blit(surf, (river_rect.x, river_rect.y))


def _draw_grid(screen: pygame.Surface) -> None:
    """Draw all horizontal and vertical grid lines."""
    # Horizontal lines (one per row y=0..9)
    for y in range(10):
        px0, py = node_to_pixel(0, y)
        px1, _  = node_to_pixel(8, y)
        pygame.draw.line(screen, C_BOARD_LINE, (px0, py), (px1, py), 1)

    # Vertical lines
    # Left and right boundary lines span the full height
    for x in (0, 8):
        px, py0 = node_to_pixel(x, 0)
        _,  py9 = node_to_pixel(x, 9)
        pygame.draw.line(screen, C_BOARD_LINE, (px, py9), (px, py0), 1)

    # Inner vertical lines are broken at the river (y=4 to y=5 gap is skipped)
    for x in range(1, 8):
        px, _  = node_to_pixel(x, 0)
        # Bottom half: y=0 to y=4
        _, py0 = node_to_pixel(x, 0)
        _, py4 = node_to_pixel(x, 4)
        pygame.draw.line(screen, C_BOARD_LINE, (px, py0), (px, py4), 1)
        # Top half: y=5 to y=9
        _, py5 = node_to_pixel(x, 5)
        _, py9 = node_to_pixel(x, 9)
        pygame.draw.line(screen, C_BOARD_LINE, (px, py5), (px, py9), 1)


def _draw_palaces(screen: pygame.Surface) -> None:
    """Draw diagonal cross lines inside both palaces (x=3..5, y=0..2 / y=7..9)."""
    for (y_lo, y_hi) in [(0, 2), (7, 9)]:
        x0_px, y0_px = node_to_pixel(3, y_lo)
        x1_px, y1_px = node_to_pixel(5, y_hi)
        x2_px, y2_px = node_to_pixel(5, y_lo)
        x3_px, y3_px = node_to_pixel(3, y_hi)
        pygame.draw.line(screen, C_PALACE_LINE,
                         (x0_px, y0_px), (x1_px, y1_px), 1)
        pygame.draw.line(screen, C_PALACE_LINE,
                         (x2_px, y2_px), (x3_px, y3_px), 1)


def _draw_nodes(screen: pygame.Surface) -> None:
    """Draw small dots at every intersection."""
    for x in range(9):
        for y in range(10):
            px, py = node_to_pixel(x, y)
            pygame.draw.circle(screen, C_NODE_DOT, (px, py), 3)


def _draw_labels(screen: pygame.Surface) -> None:
    """Draw coordinate numbers along the edges (small, muted)."""
    font = pygame.font.SysFont("monospace", 11)
    # Column letters along the bottom
    for x in range(9):
        px, py = node_to_pixel(x, 0)
        lbl = font.render(str(x), True, (120, 80, 40))
        screen.blit(lbl, (px - 4, py + 8))
    # Row numbers along the left
    for y in range(10):
        px, py = node_to_pixel(0, y)
        lbl = font.render(str(y), True, (120, 80, 40))
        screen.blit(lbl, (px - 20, py - 6))
