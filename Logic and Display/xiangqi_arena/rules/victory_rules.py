"""
Victory, defeat, and draw condition rules.

Pure read-only checks.  Writing the result into state.victory_state is done
by modification/attack.py (after combat) or by flow/turn.py (for surrender /
draw confirmations).

Rulebook V3 §15:
  §15.1 Victory: if either Leader/Marshal reaches HP ≤ 0, the opposing
        player wins IMMEDIATELY.  This check must happen after every damage
        application, not just at turn end.
  §15.2 Draw / Surrender: mutually agreed draw or voluntary surrender are
        both supported in MVP.
"""

from __future__ import annotations

from xiangqi_arena.core.enums import Faction, PieceType, VictoryState
from xiangqi_arena.state.game_state import GameState


def check_victory(state: GameState) -> VictoryState:
    """
    Evaluate all win / loss / draw conditions and return the current result.

    Priority order:
    1. Leader/Marshal HP ≤ 0   →  immediate win for the opponent.
    2. Surrender flag set        →  immediate win for the non-surrendering side.
    3. Both draw_requested       →  draw.
    4. Otherwise                 →  ONGOING.

    This function is idempotent and does NOT modify state.
    """
    # 1. Leader/Marshal death (Rulebook V3 §15.1)
    for faction in (Faction.HumanSide, Faction.OrcSide):
        leader = state.leader_of(faction)
        if leader.hp <= 0:
            return (
                VictoryState.OrcSide_WIN
                if faction is Faction.HumanSide
                else VictoryState.HumanSide_WIN
            )

    # 2. Surrender (Rulebook V3 §15.2)
    for faction, player in state.players.items():
        if player.has_surrendered:
            return (
                VictoryState.OrcSide_WIN
                if faction is Faction.HumanSide
                else VictoryState.HumanSide_WIN
            )

    # 3. Mutual draw agreement
    if all(p.draw_requested for p in state.players.values()):
        return VictoryState.DRAW

    return VictoryState.ONGOING


def is_game_over(state: GameState) -> bool:
    """Return True if the game has already ended."""
    return state.victory_state is not VictoryState.ONGOING
