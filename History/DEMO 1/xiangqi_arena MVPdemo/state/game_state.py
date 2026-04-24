from dataclasses import dataclass, field
from random import Random

from core.config import GameConfig
from core.enums import PhaseType, Side, VictoryStatus
from models.board import Board
from models.event_point import EventPoint
from models.piece import Piece
from models.player import Player


@dataclass(slots=True)
class ActionContext:
    piece_id: str | None = None
    has_moved: bool = False
    skipped_move: bool = False
    cannon_direction: tuple[int, int] | None = None
    selected_target: tuple[int, int] | None = None

    def reset(self) -> None:
        self.piece_id = None
        self.has_moved = False
        self.skipped_move = False
        self.cannon_direction = None
        self.selected_target = None


@dataclass(slots=True)
class GameState:
    board: Board
    players: dict[Side, Player]
    pieces: dict[str, Piece]
    config: GameConfig
    rng: Random
    round_number: int = 1
    current_side: Side = Side.RED
    current_phase: PhaseType = PhaseType.START
    event_points: list[EventPoint] = field(default_factory=list)
    action: ActionContext = field(default_factory=ActionContext)
    victory_status: VictoryStatus = VictoryStatus.ONGOING
    history: list[str] = field(default_factory=list)
    last_event_spawn_round: int = 0

    def selected_piece(self) -> Piece | None:
        if self.action.piece_id is None:
            return None
        return self.pieces.get(self.action.piece_id)
