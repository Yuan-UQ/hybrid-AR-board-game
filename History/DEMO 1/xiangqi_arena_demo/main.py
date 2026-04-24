import sys
import pygame

from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    FPS,
    FONT_NAME,
    FONT_SIZE_SMALL,
    FONT_SIZE_MEDIUM,
    FONT_SIZE_LARGE,
)
from ui.colors import BG_COLOR
from ui.board_ui import draw_board, screen_to_board
from ui.piece_ui import (
    draw_all_pieces,
    draw_move_hints,
    draw_attack_hints,
    draw_cannon_centers,
    draw_events,
    draw_attack_ready_piece_hints,
)
from ui.panel_ui import draw_panel, get_skip_button_rect
from ui.screens import draw_game_over_overlay, get_game_over_buttons

from core.constants import PHASE_MOVE, PHASE_ATTACK, CANNON
from core.setup import create_initial_game_state

from engine.move_engine import (
    select_piece,
    move_selected_piece,
    clear_current_selection,
)
from engine.attack_engine import (
    attack_with_selected_piece,
    start_attack_phase,
    select_attack_piece,
)
from engine.turn_engine import advance_phase
from engine.event_engine import refresh_events


def init_pygame():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    font_small = pygame.font.Font(FONT_NAME, FONT_SIZE_SMALL)
    font_medium = pygame.font.Font(FONT_NAME, FONT_SIZE_MEDIUM)
    font_large = pygame.font.Font(FONT_NAME, FONT_SIZE_LARGE)

    return screen, clock, font_small, font_medium, font_large


def handle_mouse_click(game_state, mouse_pos):
    # game over popup buttons
    if game_state.game_over:
        surface = pygame.display.get_surface()
        play_again_rect, exit_rect = get_game_over_buttons(surface)

        if play_again_rect.collidepoint(mouse_pos):
            return "restart"

        if exit_rect.collidepoint(mouse_pos):
            return "exit"

        return None

    # skip button
    skip_button_rect = get_skip_button_rect()
    if skip_button_rect.collidepoint(mouse_pos):
        advance_phase(game_state)
        return None

    board_pos = screen_to_board(*mouse_pos)
    if board_pos is None:
        return None

    x, y = board_pos
    clicked_piece = game_state.board.get_piece_at(x, y)

    if game_state.phase == PHASE_MOVE:
        if game_state.selected_piece is None:
            if clicked_piece is not None and game_state.is_current_players_piece(clicked_piece):
                select_piece(game_state, x, y)
            return None

        if clicked_piece is not None and game_state.is_current_players_piece(clicked_piece):
            select_piece(game_state, x, y)
            return None

        moved = move_selected_piece(game_state, x, y)
        if moved:
            start_attack_phase(game_state)
        return None

    if game_state.phase == PHASE_ATTACK:
        if game_state.selected_piece is None:
            if clicked_piece is not None and clicked_piece.camp == game_state.current_player:
                select_attack_piece(game_state, clicked_piece)
            return None

        if game_state.selected_piece.piece_type == CANNON:
            attack_with_selected_piece(game_state, x, y)
            return None

        if clicked_piece is not None and clicked_piece.camp != game_state.current_player:
            attack_with_selected_piece(game_state, x, y)
            return None

    return None


def handle_keydown(game_state, key):
    if game_state.game_over:
        return

    if key == pygame.K_SPACE:
        advance_phase(game_state)
        return

    if key == pygame.K_c:
        clear_current_selection(game_state)
        game_state.message = "Selection cleared."
        return

    if key == pygame.K_r:
        refresh_events(game_state)
        return


def draw_everything(screen, game_state, font_small, font_medium, font_large):
    screen.fill(BG_COLOR)

    draw_board(screen, font_medium)
    draw_events(screen, game_state.events, font_small)

    draw_all_pieces(
        surface=screen,
        board=game_state.board,
        selected_piece=game_state.selected_piece,
        font_small=font_small,
        font_medium=font_medium,
    )

    if game_state.game_over:
        draw_game_over_overlay(
            screen,
            game_state.winner,
            game_state.round_number,
            font_small,
            font_medium,
            font_large,
        )
        pygame.display.flip()
        return


    if game_state.phase == PHASE_ATTACK and getattr(game_state, "attack_ready_pieces", []):
        draw_attack_ready_piece_hints(screen, game_state.attack_ready_pieces)

    if game_state.phase == PHASE_MOVE:
        draw_move_hints(screen, game_state.available_moves)

    if game_state.phase == PHASE_ATTACK:
        if game_state.selected_piece is not None and game_state.selected_piece.piece_type == CANNON:
            draw_cannon_centers(screen, game_state.available_cannon_centers)
        else:
            draw_attack_hints(screen, game_state.available_attacks)

    draw_panel(screen, game_state, font_small, font_medium, font_large)

    pygame.display.flip()


def main():
    screen, clock, font_small, font_medium, font_large = init_pygame()
    game_state = create_initial_game_state()

    running = True
    while running:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                else:
                    handle_keydown(game_state, event.key)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                result = handle_mouse_click(game_state, event.pos)

                if result == "restart":
                    game_state = create_initial_game_state()

                elif result == "exit":
                    running = False

        mouse_pos = pygame.mouse.get_pos()

        if game_state.game_over:
            play_again_rect, exit_rect = get_game_over_buttons(screen)
            if play_again_rect.collidepoint(mouse_pos) or exit_rect.collidepoint(mouse_pos):
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
            else:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
        else:
            skip_button_rect = get_skip_button_rect()
            if skip_button_rect.collidepoint(mouse_pos):
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
            else:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

        draw_everything(screen, game_state, font_small, font_medium, font_large)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()