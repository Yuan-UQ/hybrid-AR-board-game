"""
Board rendering for Xiangqi-style board.
"""

import pygame

from config import BOARD_ORIGIN_X, BOARD_ORIGIN_Y, GRID_SIZE
from core.constants import BOARD_COLS, BOARD_ROWS
from ui.colors import BOARD_BG_COLOR, LINE_COLOR


BOARD_PIXEL_WIDTH = (BOARD_COLS - 1) * GRID_SIZE
BOARD_PIXEL_HEIGHT = (BOARD_ROWS - 1) * GRID_SIZE


def board_to_screen(x: int, y: int) -> tuple[int, int]:
    px = BOARD_ORIGIN_X + x * GRID_SIZE
    py = BOARD_ORIGIN_Y + y * GRID_SIZE
    return px, py


def screen_to_board(mouse_x: int, mouse_y: int):
    half = GRID_SIZE // 2

    min_x = BOARD_ORIGIN_X - half
    max_x = BOARD_ORIGIN_X + (BOARD_COLS - 1) * GRID_SIZE + half
    min_y = BOARD_ORIGIN_Y - half
    max_y = BOARD_ORIGIN_Y + (BOARD_ROWS - 1) * GRID_SIZE + half

    if not (min_x <= mouse_x <= max_x and min_y <= mouse_y <= max_y):
        return None

    bx = round((mouse_x - BOARD_ORIGIN_X) / GRID_SIZE)
    by = round((mouse_y - BOARD_ORIGIN_Y) / GRID_SIZE)

    if 0 <= bx < BOARD_COLS and 0 <= by < BOARD_ROWS:
        return bx, by
    return None


def draw_board(surface, font_medium) -> None:
    board_rect = pygame.Rect(
        BOARD_ORIGIN_X - 45,
        BOARD_ORIGIN_Y - 45,
        BOARD_PIXEL_WIDTH + 90,
        BOARD_PIXEL_HEIGHT + 90,
    )

    # shadow
    shadow = pygame.Surface((board_rect.width, board_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 70), shadow.get_rect(), border_radius=14)
    surface.blit(shadow, (board_rect.x + 8, board_rect.y + 10))

    # main board block
    pygame.draw.rect(surface, BOARD_BG_COLOR, board_rect, border_radius=14)

    # horizontal lines
    for y in range(BOARD_ROWS):
        start = board_to_screen(0, y)
        end = board_to_screen(BOARD_COLS - 1, y)
        pygame.draw.line(surface, LINE_COLOR, start, end, 2)

    # vertical lines with river gap
    for x in range(BOARD_COLS):
        start_top = board_to_screen(x, 0)
        end_top = board_to_screen(x, 4)
        pygame.draw.line(surface, LINE_COLOR, start_top, end_top, 2)

        start_bottom = board_to_screen(x, 5)
        end_bottom = board_to_screen(x, 9)
        pygame.draw.line(surface, LINE_COLOR, start_bottom, end_bottom, 2)

    # palace diagonals
    pygame.draw.line(surface, LINE_COLOR, board_to_screen(3, 0), board_to_screen(5, 2), 2)
    pygame.draw.line(surface, LINE_COLOR, board_to_screen(5, 0), board_to_screen(3, 2), 2)

    pygame.draw.line(surface, LINE_COLOR, board_to_screen(3, 7), board_to_screen(5, 9), 2)
    pygame.draw.line(surface, LINE_COLOR, board_to_screen(5, 7), board_to_screen(3, 9), 2)