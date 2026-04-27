"""
Piece / highlight / event rendering.
"""

import pygame

from config import (
    PIECE_RADIUS,
    MOVE_MARK_RADIUS,
    ATTACK_MARK_RADIUS,
    EVENT_MARK_RADIUS,
)
from core.constants import RED, KING, ROOK, KNIGHT, CANNON, PAWN, HEAL, AMMO, TRAP
from ui.colors import (
    RED_PIECE_COLOR,
    BLACK_PIECE_COLOR,
    PIECE_TEXT_LIGHT,
    TEXT_COLOR,
    WHITE,
    SELECTED_GLOW_COLOR,
    MOVE_HINT_COLOR,
    ATTACK_HINT_COLOR,
    CANNON_CENTER_COLOR,
    HEAL_COLOR,
    AMMO_COLOR,
    TRAP_COLOR,
    DEAD_CROSS_COLOR,
    HP_BAR_BG,
    HP_BAR_FILL,
)
from ui.board_ui import board_to_screen


def get_piece_label(piece_type: str) -> str:
    mapping = {
        KING: "K",
        ROOK: "R",
        KNIGHT: "H",
        CANNON: "C",
        PAWN: "P",
    }
    return mapping.get(piece_type, "?")


def get_piece_color(camp: str):
    return RED_PIECE_COLOR if camp == RED else BLACK_PIECE_COLOR


def draw_glow_circle(surface, center, radius, color):
    glow_surface = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
    pygame.draw.circle(glow_surface, color, (radius * 2, radius * 2), radius)
    surface.blit(glow_surface, (center[0] - radius * 2, center[1] - radius * 2))


def draw_single_piece(surface, piece, font_small, font_medium, is_selected: bool = False) -> None:
    if piece is None:
        return

    px, py = board_to_screen(piece.x, piece.y)
    piece_color = get_piece_color(piece.camp)

    if is_selected:
        draw_glow_circle(surface, (px, py), PIECE_RADIUS + 10, SELECTED_GLOW_COLOR)

    pygame.draw.circle(surface, piece_color, (px, py), PIECE_RADIUS + 3)
    pygame.draw.circle(surface, (22, 22, 24), (px, py), PIECE_RADIUS + 3, 2)

    label = font_medium.render(get_piece_label(piece.piece_type), True, PIECE_TEXT_LIGHT)
    label_rect = label.get_rect(center=(px, py - 2))
    surface.blit(label, label_rect)

    # HP bar
    bar_width = 56
    bar_height = 6
    bar_x = px - bar_width // 2
    bar_y = py + PIECE_RADIUS + 10

    pygame.draw.rect(surface, HP_BAR_BG, (bar_x, bar_y, bar_width, bar_height), border_radius=3)

    ratio = 0 if piece.max_hp == 0 else piece.hp / piece.max_hp
    fill_width = int(bar_width * ratio)
    pygame.draw.rect(surface, HP_BAR_FILL, (bar_x, bar_y, fill_width, bar_height), border_radius=3)

    if not piece.alive or piece.pending_removal:
        pygame.draw.line(
            surface, DEAD_CROSS_COLOR,
            (px - PIECE_RADIUS, py - PIECE_RADIUS),
            (px + PIECE_RADIUS, py + PIECE_RADIUS),
            4
        )
        pygame.draw.line(
            surface, DEAD_CROSS_COLOR,
            (px - PIECE_RADIUS, py + PIECE_RADIUS),
            (px + PIECE_RADIUS, py - PIECE_RADIUS),
            4
        )


def draw_all_pieces(surface, board, selected_piece, font_small, font_medium) -> None:
    for piece in board.get_all_pieces():
        is_selected = selected_piece is not None and piece.id == selected_piece.id
        draw_single_piece(surface, piece, font_small, font_medium, is_selected=is_selected)


def draw_move_hints(surface, positions: list[tuple[int, int]]) -> None:
    for x, y in positions:
        px, py = board_to_screen(x, y)
        draw_glow_circle(surface, (px, py), 34, MOVE_HINT_COLOR)


def draw_attack_hints(surface, positions: list[tuple[int, int]]) -> None:
    for x, y in positions:
        px, py = board_to_screen(x, y)
        draw_glow_circle(surface, (px, py), 34, ATTACK_HINT_COLOR)


def draw_cannon_centers(surface, positions: list[tuple[int, int]]) -> None:
    for x, y in positions:
        px, py = board_to_screen(x, y)
        draw_glow_circle(surface, (px, py), 36, CANNON_CENTER_COLOR)


def get_event_color(event_type: str):
    if event_type == HEAL:
        return HEAL_COLOR
    if event_type == AMMO:
        return AMMO_COLOR
    if event_type == TRAP:
        return TRAP_COLOR
    return WHITE


def get_event_label(event_type: str) -> str:
    if event_type == HEAL:
        return "H"
    if event_type == AMMO:
        return "A"
    if event_type == TRAP:
        return "T"
    return "?"


def draw_events(surface, events, font_small) -> None:
    for event in events:
        px, py = board_to_screen(event["x"], event["y"])
        color = get_event_color(event["type"])

        pygame.draw.circle(surface, color, (px, py), EVENT_MARK_RADIUS)
        text = font_small.render(get_event_label(event["type"]), True, TEXT_COLOR)
        rect = text.get_rect(center=(px, py))
        surface.blit(text, rect)


def draw_attack_ready_piece_hints(surface, pieces: list) -> None:
    """
    Highlight pieces that can attack in current attack phase.
    """
    for piece in pieces:
        px, py = board_to_screen(piece.x, piece.y)
        draw_glow_circle(surface, (px, py), PIECE_RADIUS + 14, (90, 200, 255, 100))