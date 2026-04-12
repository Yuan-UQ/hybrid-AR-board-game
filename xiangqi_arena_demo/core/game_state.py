"""
Stores board, turn info, selected piece, events, messages, and winner state.
"""

from core.constants import RED, BLACK, PHASE_MOVE


class GameState:
    def __init__(self, board):
        self.board = board

        self.current_player = RED
        self.round_number = 1
        self.phase = PHASE_MOVE

        self.selected_piece = None
        self.available_moves = []
        self.available_attacks = []
        self.attack_ready_pieces = []

        self.available_cannon_centers = []
        self.selected_cannon_center = None

        self.events = []

        self.game_over = False
        self.winner = None

        self.message = "Select a piece and move it to a highlighted position."
        self.last_action = None

    def switch_player(self) -> None:
        self.current_player = BLACK if self.current_player == RED else RED

    def next_round_if_needed(self, previous_player: str) -> None:
        if previous_player == BLACK and self.current_player == RED:
            self.round_number += 1

    def set_phase(self, phase: str) -> None:
        self.phase = phase

    def set_selected_piece(self, piece) -> None:
        self.selected_piece = piece

    def clear_selection(self) -> None:
        self.selected_piece = None
        self.available_moves = []
        self.available_attacks = []
        self.available_cannon_centers = []
        self.selected_cannon_center = None

    def set_available_moves(self, positions: list[tuple[int, int]]) -> None:
        self.available_moves = positions

    def set_available_attacks(self, positions: list[tuple[int, int]]) -> None:
        self.available_attacks = positions

    def set_available_cannon_centers(self, positions: list[tuple[int, int]]) -> None:
        self.available_cannon_centers = positions
    
    def set_attack_ready_pieces(self, pieces: list) -> None:
        self.attack_ready_pieces = pieces

    def clear_attack_ready_pieces(self) -> None:
        self.attack_ready_pieces = []

    def add_event(self, event_type: str, x: int, y: int) -> None:
        self.events.append({
            "type": event_type,
            "x": x,
            "y": y,
        })

    def remove_event_at(self, x: int, y: int) -> None:
        self.events = [
            event for event in self.events
            if not (event["x"] == x and event["y"] == y)
        ]

    def get_event_at(self, x: int, y: int):
        for event in self.events:
            if event["x"] == x and event["y"] == y:
                return event
        return None

    def clear_events(self) -> None:
        self.events = []

    def set_game_over(self, winner: str) -> None:
        self.game_over = True
        self.winner = winner
        self.message = f"Game over. Winner: {winner}"

    def is_current_players_piece(self, piece) -> bool:
        return piece is not None and piece.camp == self.current_player and piece.alive

    def __repr__(self) -> str:
        return (
            f"GameState(player={self.current_player}, round={self.round_number}, "
            f"phase={self.phase}, game_over={self.game_over}, winner={self.winner})"
        )