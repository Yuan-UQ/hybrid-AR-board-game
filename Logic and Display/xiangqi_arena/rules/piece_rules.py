"""
Unified access point for piece-specific rules.

Guide v2 §4.5 design intent:
  The main system (flow/, main.py) should query legality and attack options
  through THIS module rather than importing movement_rules or attack_rules
  directly.  This keeps the call sites clean and makes piece-type dispatch
  a single responsibility.

All functions here are thin wrappers that delegate to the appropriate
sub-modules; no new logic is introduced.
"""

from __future__ import annotations

from xiangqi_arena.models.piece import Piece
from xiangqi_arena.rules.attack_rules import (
    get_wizard_aoe,
    get_legal_attack_targets,
)
from xiangqi_arena.rules.movement_rules import get_legal_moves
from xiangqi_arena.state.game_state import GameState

Pos = tuple[int, int]


# ---------------------------------------------------------------------------
# Movement
# ---------------------------------------------------------------------------

def legal_moves(piece: Piece, state: GameState) -> list[Pos]:
    """Return all positions *piece* may legally move to this turn."""
    return get_legal_moves(piece, state)


# ---------------------------------------------------------------------------
# Attack
# ---------------------------------------------------------------------------

def legal_attack_targets(piece: Piece, state: GameState) -> list[Pos]:
    """
    Return the legal attack targets for *piece*.

    For non-Wizard pieces: a list of enemy-occupied positions within reach.
    For the Wizard: a list of valid *center* positions (one per valid attack
    direction — the player then picks one via arrow keys).
    """
    return get_legal_attack_targets(piece, state)


def wizard_aoe_nodes(
    piece: Piece,
    center_pos: Pos,
    state: GameState,
) -> list[Pos]:
    """
    Return the nodes affected by a Wizard attack aimed at *center_pos*.

    Filters to enemy-occupied, in-bounds nodes (no friendly fire).
    Only call this after confirming *center_pos* is a legal attack target.
    """
    return get_wizard_aoe(center_pos, state, piece.faction)


# ---------------------------------------------------------------------------
# Combined query (used by UI highlight layer)
# ---------------------------------------------------------------------------

def legal_moves_and_attacks(
    piece: Piece,
    state: GameState,
) -> tuple[list[Pos], list[Pos]]:
    """
    Return (legal_moves, legal_attack_targets) for *piece* in one call.
    Useful for highlight_renderer which needs both sets at once.
    """
    return legal_moves(piece, state), legal_attack_targets(piece, state)


# ---------------------------------------------------------------------------
# Operability check
# ---------------------------------------------------------------------------

def has_any_action(piece: Piece, state: GameState) -> bool:
    """
    Return True if *piece* has at least one legal move OR one legal attack.
    Can be used to grey-out pieces that have no available actions.
    """
    return bool(legal_moves(piece, state)) or bool(legal_attack_targets(piece, state))
