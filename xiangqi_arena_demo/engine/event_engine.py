"""
Handles spawning / refreshing special event points.
"""

import random

from core.constants import (
    AMMO,
    HEAL,
    TRAP,
    EVENT_TYPES,
    EVENT_REFRESH_ON_ODD_ROUNDS,
    BOARD_COLS,
    BOARD_ROWS,
)


def should_refresh_events(round_number: int) -> bool:
    """
    By current rule:
    - refresh on odd rounds only
    """
    if EVENT_REFRESH_ON_ODD_ROUNDS:
        return round_number % 2 == 1
    return True


def get_all_empty_positions(board, existing_events=None) -> list[tuple[int, int]]:
    """
    Return all empty board cells that also do not already contain an event.
    """
    event_positions = set()
    if existing_events:
        event_positions = {(event["x"], event["y"]) for event in existing_events}

    empty_positions = []
    for x in range(BOARD_COLS):
        for y in range(BOARD_ROWS):
            if board.is_empty(x, y) and (x, y) not in event_positions:
                empty_positions.append((x, y))

    return empty_positions


def refresh_events(game_state, num_events: int = 3) -> list[dict]:
    """
    Refresh event points:
    - old untriggered points disappear
    - new points are placed randomly on empty cells
    - can appear in palace as long as cell is empty
    """
    if not should_refresh_events(game_state.round_number):
        game_state.message = f"Round {game_state.round_number}: no event refresh."
        return game_state.events

    game_state.clear_events()

    available_positions = get_all_empty_positions(game_state.board)
    if not available_positions:
        game_state.message = "No empty cells available for event refresh."
        return []

    num_to_spawn = min(num_events, len(available_positions))
    chosen_positions = random.sample(available_positions, num_to_spawn)

    for x, y in chosen_positions:
        event_type = random.choice([AMMO, HEAL, TRAP])
        game_state.add_event(event_type, x, y)

    game_state.message = (
        f"Round {game_state.round_number}: refreshed {len(game_state.events)} event points."
    )
    return game_state.events


def add_single_event(game_state, event_type: str, x: int, y: int) -> bool:
    """
    Manual helper for testing.
    """
    if event_type not in EVENT_TYPES:
        return False

    if not game_state.board.is_within_bounds(x, y):
        return False

    if not game_state.board.is_empty(x, y):
        return False

    if game_state.get_event_at(x, y) is not None:
        return False

    game_state.add_event(event_type, x, y)
    return True