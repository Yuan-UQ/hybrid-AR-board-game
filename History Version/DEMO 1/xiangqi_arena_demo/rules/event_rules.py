"""
This file focuses on rule-level helpers for event generation and event removal.
"""

import random

from core.constants import AMMO, HEAL, TRAP, EVENT_TYPES, BOARD_COLS, BOARD_ROWS


def is_valid_event_type(event_type: str) -> bool:
    return event_type in EVENT_TYPES


def create_event(event_type: str, x: int, y: int) -> dict:
    """
    Create a simple event dictionary.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Invalid event type: {event_type}")

    return {
        "type": event_type,
        "x": x,
        "y": y,
    }


def is_event_on_position(event: dict, x: int, y: int) -> bool:
    return event["x"] == x and event["y"] == y


def get_random_event_type() -> str:
    return random.choice([AMMO, HEAL, TRAP])


def get_empty_positions_for_events(board, existing_events=None) -> list[tuple[int, int]]:
    """
    Return all empty positions that are also not occupied by current events.
    """
    occupied_by_event = set()
    if existing_events:
        occupied_by_event = {(event["x"], event["y"]) for event in existing_events}

    result = []
    for x in range(BOARD_COLS):
        for y in range(BOARD_ROWS):
            if board.is_empty(x, y) and (x, y) not in occupied_by_event:
                result.append((x, y))

    return result


def generate_random_events(board, count: int = 3, existing_events=None) -> list[dict]:
    """
    Generate random events on empty positions.
    """
    candidates = get_empty_positions_for_events(board, existing_events=existing_events)
    if not candidates:
        return []

    actual_count = min(count, len(candidates))
    chosen_positions = random.sample(candidates, actual_count)

    events = []
    for x, y in chosen_positions:
        events.append(create_event(get_random_event_type(), x, y))

    return events


def remove_triggered_event(events: list[dict], x: int, y: int) -> list[dict]:
    """
    Return a new event list after removing the event at (x, y).
    """
    return [event for event in events if not is_event_on_position(event, x, y)]