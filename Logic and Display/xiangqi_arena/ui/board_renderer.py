"""
Board rendering.

Draws the 9×10 intersection grid, river, palace diagonals, and coordinate
labels.  Pure presentation — reads no GameState; only uses geometry constants.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from xiangqi_arena.core.constants import BOARD_COLS, BOARD_ROWS
import xiangqi_arena.ui.display_config as dcfg
from xiangqi_arena.ui.display_config import (
    C_BG, C_BOARD_LINE, C_PALACE_LINE, C_RIVER_FILL,
)


_IMAGE_NATIVE_W = 819
_IMAGE_NATIVE_H = 546

BOARD_POINTS: dict[tuple[int, int], list[int]] = {
    (0, 0): [165, 465],
    (1, 0): [219, 465],
    (2, 0): [274, 465],
    (3, 0): [329, 465],
    (4, 0): [382, 465],
    (5, 0): [437, 465],
    (6, 0): [491, 465],
    (7, 0): [545, 465],
    (8, 0): [600, 465],
    (9, 0): [654, 465],
    (0, 1): [171, 411],
    (1, 1): [224, 411],
    (2, 1): [277, 411],
    (3, 1): [331, 411],
    (4, 1): [383, 411],
    (5, 1): [436, 411],
    (6, 1): [490, 411],
    (7, 1): [542, 411],
    (8, 1): [596, 411],
    (9, 1): [650, 411],
    (0, 2): [176, 360],
    (1, 2): [228, 360],
    (2, 2): [280, 360],
    (3, 2): [332, 360],
    (4, 2): [384, 360],
    (5, 2): [436, 360],
    (6, 2): [488, 360],
    (7, 2): [540, 360],
    (8, 2): [591, 360],
    (9, 2): [644, 360],
    (0, 3): [181, 310],
    (1, 3): [232, 310],
    (2, 3): [283, 310],
    (3, 3): [334, 310],
    (4, 3): [385, 310],
    (5, 3): [436, 310],
    (6, 3): [487, 310],
    (7, 3): [537, 310],
    (8, 3): [589, 310],
    (9, 3): [640, 310],
    (0, 4): [186, 263],
    (1, 4): [236, 263],
    (2, 4): [286, 263],
    (3, 4): [336, 263],
    (4, 4): [385, 263],
    (5, 4): [435, 263],
    (6, 4): [485, 263],
    (7, 4): [535, 263],
    (8, 4): [585, 263],
    (9, 4): [635, 263],
    (0, 5): [190, 217],
    (1, 5): [239, 217],
    (2, 5): [289, 217],
    (3, 5): [338, 217],
    (4, 5): [385, 217],
    (5, 5): [434, 217],
    (6, 5): [483, 217],
    (7, 5): [532, 217],
    (8, 5): [581, 217],
    (9, 5): [631, 217],
    (0, 6): [195, 174],
    (1, 6): [243, 173],
    (2, 6): [291, 173],
    (3, 6): [338, 174],
    (4, 6): [386, 173],
    (5, 6): [434, 173],
    (6, 6): [481, 174],
    (7, 6): [530, 173],
    (8, 6): [577, 173],
    (9, 6): [626, 173],
    (0, 7): [199, 132],
    (1, 7): [246, 132],
    (2, 7): [292, 132],
    (3, 7): [340, 132],
    (4, 7): [386, 132],
    (5, 7): [434, 132],
    (6, 7): [481, 132],
    (7, 7): [527, 131],
    (8, 7): [574, 132],
    (9, 7): [622, 132],
    (0, 8): [202, 90],
    (1, 8): [249, 90],
    (2, 8): [295, 90],
    (3, 8): [341, 90],
    (4, 8): [387, 90],
    (5, 8): [433, 90],
    (6, 8): [479, 90],
    (7, 8): [525, 90],
    (8, 8): [571, 90],
    (9, 8): [618, 90],
}

_BOARD_IMAGE: pygame.Surface | None = None
_BOARD_BACKDROP: pygame.Surface | None = None


def invalidate_board_image_cache() -> None:
    """Call after window resize / layout change so the board image rescales."""
    global _BOARD_IMAGE, _BOARD_BACKDROP
    _BOARD_IMAGE = None
    _BOARD_BACKDROP = None


def node_to_pixel(x: int, y: int) -> tuple[int, int]:
    """Convert a board node (x=0..9, y=0..8) to screen pixel (px, py)."""
    native_x, native_y = BOARD_POINTS[(x, y)]
    px = dcfg.BOARD_IMAGE_LEFT + round(native_x / _IMAGE_NATIVE_W * dcfg.BOARD_IMAGE_W)
    py = dcfg.BOARD_IMAGE_TOP + round(native_y / _IMAGE_NATIVE_H * dcfg.BOARD_IMAGE_H)
    return px, py


def _draw_board_image(screen: pygame.Surface) -> None:
    global _BOARD_IMAGE, _BOARD_BACKDROP

    if _BOARD_IMAGE is None:
        image_path = (
            Path(__file__).resolve().parents[2]
            / "ArtResource"
            / "Chess Board"
            / "ChessBoardWithBackground.png"
        )
        image = pygame.image.load(str(image_path)).convert()
        # Backdrop: scale to the *available* board area to visually reduce letterboxing.
        # This can stretch, but it's drawn subtly under the true aspect-ratio board.
        _BOARD_BACKDROP = pygame.transform.smoothscale(
            image,
            (max(1, dcfg.BOARD_AVAIL_W), max(1, dcfg.BOARD_AVAIL_H)),
        )
        _BOARD_BACKDROP.set_alpha(90)
        _BOARD_IMAGE = pygame.transform.smoothscale(
            image,
            (dcfg.BOARD_IMAGE_W, dcfg.BOARD_IMAGE_H),
        )

    if _BOARD_BACKDROP is not None:
        screen.blit(_BOARD_BACKDROP, (dcfg.BOARD_AVAIL_LEFT, dcfg.BOARD_AVAIL_TOP))
        # Slight dark overlay to keep focus on the main board.
        shade = pygame.Surface((dcfg.BOARD_AVAIL_W, dcfg.BOARD_AVAIL_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 55))
        screen.blit(shade, (dcfg.BOARD_AVAIL_LEFT, dcfg.BOARD_AVAIL_TOP))

    screen.blit(_BOARD_IMAGE, (dcfg.BOARD_IMAGE_LEFT, dcfg.BOARD_IMAGE_TOP))


def draw_board(screen: pygame.Surface) -> None:
    """Draw the full board background, grid, river, and palace markings."""
    _draw_board_image(screen)
    _draw_nodes(screen)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _draw_background(screen: pygame.Surface) -> None:
    board_rect = pygame.Rect(
        dcfg.BOARD_LEFT - 15, dcfg.BOARD_TOP - 15,
        9 * dcfg.CELL + 30, 8 * dcfg.CELL + 30,
    )
    pygame.draw.rect(screen, C_BG, board_rect, border_radius=6)
    pygame.draw.rect(screen, C_BOARD_LINE, board_rect, width=2, border_radius=6)


def _draw_river(screen: pygame.Surface) -> None:
    """Tint the river strip (between x=4 and x=5) with a translucent blue."""
    x4, _ = node_to_pixel(4, 0)
    x5, _ = node_to_pixel(5, 0)
    _, y_top = node_to_pixel(0, BOARD_ROWS - 1)
    _, y_bottom = node_to_pixel(0, 0)
    river_rect = pygame.Rect(x4, y_top, x5 - x4, y_bottom - y_top)
    surf = pygame.Surface((river_rect.width, river_rect.height), pygame.SRCALPHA)
    surf.fill(C_RIVER_FILL)
    screen.blit(surf, (river_rect.x, river_rect.y))


def _draw_grid(screen: pygame.Surface) -> None:
    """Draw all horizontal and vertical grid lines."""
    # Horizontal lines are broken by the vertical river gap.
    for y in range(BOARD_ROWS):
        pygame.draw.line(screen, C_BOARD_LINE,
                         node_to_pixel(0, y), node_to_pixel(4, y), 1)
        pygame.draw.line(screen, C_BOARD_LINE,
                         node_to_pixel(5, y), node_to_pixel(BOARD_COLS - 1, y), 1)

    # Vertical lines span each side from bottom to top.
    for x in range(BOARD_COLS):
        pygame.draw.line(screen, C_BOARD_LINE,
                         node_to_pixel(x, 0), node_to_pixel(x, BOARD_ROWS - 1), 1)


def _draw_palaces(screen: pygame.Surface) -> None:
    """Draw diagonal cross lines inside both palaces."""
    for (x_lo, x_hi) in [(0, 2), (7, 9)]:
        y_lo, y_hi = 3, 5
        x0_px, y0_px = node_to_pixel(x_lo, y_lo)
        x1_px, y1_px = node_to_pixel(x_hi, y_hi)
        x2_px, y2_px = node_to_pixel(x_hi, y_lo)
        x3_px, y3_px = node_to_pixel(x_lo, y_hi)
        pygame.draw.line(screen, C_PALACE_LINE,
                         (x0_px, y0_px), (x1_px, y1_px), 1)
        pygame.draw.line(screen, C_PALACE_LINE,
                         (x2_px, y2_px), (x3_px, y3_px), 1)


def _draw_nodes(screen: pygame.Surface) -> None:
    """Draw green dots at every legal board node."""
    r_out = max(2, int(4 * dcfg.UI_SCALE + 0.5))
    r_in = max(1, r_out - 2)
    for x in range(BOARD_COLS):
        for y in range(BOARD_ROWS):
            px, py = node_to_pixel(x, y)
            pygame.draw.circle(screen, (10, 70, 20), (px, py), r_out)
            pygame.draw.circle(screen, (0, 255, 80), (px, py), r_in)


def _draw_labels(screen: pygame.Surface) -> None:
    """Draw coordinate numbers along the edges (small, muted)."""
    font = pygame.font.Font(None, 11)
    # Board x coordinates along the bottom edge
    for x in range(BOARD_COLS):
        px, py = node_to_pixel(x, 0)
        lbl = font.render(str(x), True, (120, 80, 40))
        screen.blit(lbl, (px - 4, py + 8))
    # Board y coordinates along the left edge
    for y in range(BOARD_ROWS):
        px, py = node_to_pixel(0, y)
        lbl = font.render(str(y), True, (120, 80, 40))
        screen.blit(lbl, (px - 20, py - 4))
