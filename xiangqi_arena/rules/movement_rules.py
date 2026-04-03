"""
Movement legality rules.

Responsibilities (Guide v2 / Rulebook V3):
- verify boundaries and reachability
- verify path blocking (where applicable)
- verify piece-specific movement patterns
- enforce palace restriction for the General/Marshal
- enforce pre-river/post-river pawn restrictions

This module MUST NOT directly mutate GameState.
"""

