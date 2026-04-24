from core.constants import DEFAULT_EVENT_ROTATION
from core.enums import EventType
from models.event_point import EventPoint
from state.game_state import GameState


def should_spawn_event(state: GameState) -> bool:
    return state.round_number % 2 == 1 and state.last_event_spawn_round != state.round_number


def random_event_type(state: GameState) -> EventType:
    return state.rng.choice(DEFAULT_EVENT_ROTATION)


def spawn_event(state: GameState) -> EventPoint | None:
    candidates = []
    for x in range(state.board.width):
        for y in range(state.board.height):
            position = (x, y)
            if not state.board.is_occupied(position):
                candidates.append(position)
    if not candidates:
        return None
    position = state.rng.choice(candidates)
    event_point = EventPoint(event_type=random_event_type(state), position=position, spawned_round=state.round_number)
    state.event_points = [event_point]
    state.last_event_spawn_round = state.round_number
    state.history.append(f"Event spawned: {event_point.event_type.name} at {event_point.position}")
    return event_point


def active_event(state: GameState) -> EventPoint | None:
    for event_point in state.event_points:
        if event_point.active and not event_point.triggered:
            return event_point
    return None
