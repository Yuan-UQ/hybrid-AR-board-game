"""
Side panel rendering.
"""

import pygame

from config import PANEL_X, PANEL_Y, PANEL_WIDTH, PANEL_HEIGHT
from ui.colors import (
    PANEL_BG_COLOR,
    PANEL_CARD_COLOR,
    PANEL_BORDER_COLOR,
    SUBTEXT_COLOR,
    MUTED_TEXT_COLOR,
    RED_PIECE_COLOR,
    WHITE,
)


def get_skip_button_rect():
    """
    Make the button bottom align visually with the board bottom.
    """
    button_width = PANEL_WIDTH - 52
    button_height = 60
    x = PANEL_X + 26
    y = PANEL_Y + PANEL_HEIGHT - button_height - 20
    return pygame.Rect(x, y, button_width, button_height)


def draw_card(surface, x, y, w, h, title, value, font_small, font_medium):
    rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surface, PANEL_CARD_COLOR, rect, border_radius=10)
    pygame.draw.rect(surface, PANEL_BORDER_COLOR, rect, width=1, border_radius=10)

    title_text = font_small.render(title, True, MUTED_TEXT_COLOR)
    value_text = font_medium.render(str(value), True, WHITE)

    surface.blit(title_text, (x + 18, y + 14))
    surface.blit(value_text, (x + 18, y + 44))


def draw_panel(surface, game_state, font_small, font_medium, font_large) -> None:
    panel_rect = pygame.Rect(PANEL_X, PANEL_Y, PANEL_WIDTH, PANEL_HEIGHT)
    pygame.draw.rect(surface, PANEL_BG_COLOR, panel_rect)

    x = PANEL_X + 26
    y = PANEL_Y + 20

    title = font_large.render(
        f"{'Red' if game_state.current_player == 'red' else 'Black'}'s Turn",
        True,
        RED_PIECE_COLOR if game_state.current_player == "red" else WHITE,
    )
    surface.blit(title, (x, y))
    y += 70

    draw_card(surface, x, y, PANEL_WIDTH - 52, 90, "Round", game_state.round_number, font_small, font_medium)
    y += 110

    draw_card(surface, x, y, PANEL_WIDTH - 52, 90, "Phase", game_state.phase.capitalize(), font_small, font_medium)
    y += 110

    draw_card(
        surface,
        x,
        y,
        PANEL_WIDTH - 52,
        90,
        "Current Player",
        "Red" if game_state.current_player == "red" else "Black",
        font_small,
        font_medium,
    )
    y += 120

    if game_state.selected_piece is not None:
        selected_text = f"Selected: {game_state.selected_piece.id}"
        selected_render = font_small.render(selected_text, True, SUBTEXT_COLOR)
        surface.blit(selected_render, (x, y))
        y += 40

    msg_lines = wrap_text(game_state.message, font_medium, PANEL_WIDTH - 60)
    for line in msg_lines[:4]:
        text = font_medium.render(line, True, (235, 235, 235))
        surface.blit(text, (x, y))
        y += 32

    button_rect = get_skip_button_rect()
    draw_button(surface, button_rect, "Skip [Space]", (0, 190, 70), font_medium)


def draw_button(surface, rect, text, color, font):
    pygame.draw.rect(surface, color, rect, border_radius=12)
    label = font.render(text, True, WHITE)
    label_rect = label.get_rect(center=rect.center)
    surface.blit(label, label_rect)


def wrap_text(text, font, max_width):
    words = text.split()
    if not words:
        return []

    lines = []
    current = words[0]

    for word in words[1:]:
        test = current + " " + word
        if font.size(test)[0] <= max_width:
            current = test
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines