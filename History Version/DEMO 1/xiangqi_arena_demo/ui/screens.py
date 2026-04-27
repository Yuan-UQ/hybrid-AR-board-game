"""
Screen overlays for Xiangqi Arena.
"""

import pygame

from ui.colors import WHITE


def get_game_over_popup_rect(surface):
    popup_width = 560
    popup_height = 640
    x = (surface.get_width() - popup_width) // 2
    y = (surface.get_height() - popup_height) // 2
    return pygame.Rect(x, y, popup_width, popup_height)


def get_game_over_buttons(surface):
    popup_rect = get_game_over_popup_rect(surface)

    button_width = popup_rect.width - 80
    button_height = 58
    button_x = popup_rect.x + 40

    play_again_rect = pygame.Rect(
        button_x,
        popup_rect.bottom - 145,
        button_width,
        button_height,
    )

    exit_rect = pygame.Rect(
        button_x,
        popup_rect.bottom - 75,
        button_width,
        button_height,
    )

    return play_again_rect, exit_rect


def draw_game_over_overlay(surface, winner, round_number, font_small, font_medium, font_large):
    # background dark overlay
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    surface.blit(overlay, (0, 0))

    popup_rect = get_game_over_popup_rect(surface)

    # popup box
    pygame.draw.rect(surface, (45, 45, 50), popup_rect, border_radius=18)
    pygame.draw.rect(surface, (95, 95, 102), popup_rect, width=2, border_radius=18)

    center_x = popup_rect.centerx

    # title
    title = font_large.render("GAME OVER", True, (210, 210, 215))
    title_rect = title.get_rect(center=(center_x, popup_rect.y + 55))
    surface.blit(title, title_rect)

    # winner headline
    winner_text = "Red Wins" if winner == "red" else "Black Wins"
    winner_color = (255, 55, 55) if winner == "red" else (240, 240, 240)
    winner_render = font_large.render(winner_text, True, winner_color)
    winner_rect = winner_render.get_rect(center=(center_x, popup_rect.y + 145))
    surface.blit(winner_render, winner_rect)

    # divider 1
    pygame.draw.line(
        surface,
        (90, 90, 96),
        (popup_rect.x + 40, popup_rect.y + 205),
        (popup_rect.right - 40, popup_rect.y + 205),
        1,
    )

    # subtitle
    subtitle = font_medium.render(
        f"{'Black' if winner == 'red' else 'Red'} King has been captured",
        True,
        (230, 230, 235),
    )
    subtitle_rect = subtitle.get_rect(center=(center_x, popup_rect.y + 240))
    surface.blit(subtitle, subtitle_rect)

    # card settings
    card_x = popup_rect.x + 40
    card_w = popup_rect.width - 80
    card_h = 68

    # Total rounds card
    card1 = pygame.Rect(card_x, popup_rect.y + 290, card_w, card_h)
    pygame.draw.rect(surface, (22, 22, 26), card1, border_radius=12)

    rounds_label = font_medium.render("Total Rounds", True, (185, 185, 190))
    rounds_value = font_large.render(str(round_number), True, WHITE)

    surface.blit(rounds_label, (card1.x + 24, card1.y + 18))
    surface.blit(rounds_value, (card1.right - 42, card1.y + 12))

    # Winner card
    card2 = pygame.Rect(card_x, popup_rect.y + 385, card_w, card_h)
    pygame.draw.rect(surface, (22, 22, 26), card2, border_radius=12)
    pygame.draw.rect(surface, winner_color, card2, width=2, border_radius=12)

    winner_label = font_medium.render("Winner", True, (185, 185, 190))
    winner_value = font_large.render("Red" if winner == "red" else "Black", True, winner_color)

    surface.blit(winner_label, (card2.x + 24, card2.y + 18))
    surface.blit(winner_value, (card2.right - 95, card2.y + 12))

    # divider 2
    pygame.draw.line(
        surface,
        (90, 90, 96),
        (popup_rect.x + 40, popup_rect.y + 490),
        (popup_rect.right - 40, popup_rect.y + 490),
        1,
    )

    # buttons
    play_again_rect, exit_rect = get_game_over_buttons(surface)

    pygame.draw.rect(surface, (0, 190, 70), play_again_rect, border_radius=12)
    play_text = font_large.render("Play Again", True, WHITE)
    play_text_rect = play_text.get_rect(center=play_again_rect.center)
    surface.blit(play_text, play_text_rect)

    pygame.draw.rect(surface, (88, 88, 94), exit_rect, border_radius=12)
    exit_text = font_large.render("Exit Game", True, WHITE)
    exit_text_rect = exit_text.get_rect(center=exit_rect.center)
    surface.blit(exit_text, exit_text_rect)