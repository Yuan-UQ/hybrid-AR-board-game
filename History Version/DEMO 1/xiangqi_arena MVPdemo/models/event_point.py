from dataclasses import dataclass

from core.enums import EventType
from core.utils import Position


@dataclass(slots=True)
class EventPoint:
    event_type: EventType
    position: Position
    triggered: bool = False
    spawned_round: int = 0
    active: bool = True
