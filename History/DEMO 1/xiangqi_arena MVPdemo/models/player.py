from dataclasses import dataclass, field

from core.enums import Side


@dataclass(slots=True)
class Player:
    side: Side
    piece_ids: list[str] = field(default_factory=list)
    has_surrendered: bool = False
    agreed_to_draw: bool = False
