"""
Separated highlight rendering helpers.
Currently reuses highlight drawing functions from piece_ui.
"""

from ui.piece_ui import draw_move_hints, draw_attack_hints, draw_cannon_centers

__all__ = [
    "draw_move_hints",
    "draw_attack_hints",
    "draw_cannon_centers",
]