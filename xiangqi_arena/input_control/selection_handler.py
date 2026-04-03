"""
Selection-based input handling.

This module converts player selections into structured intents, e.g.:
- selecting a piece to operate this turn
- selecting a destination node for movement
- selecting a target (piece or node) for attack

It should not decide legality; it only captures intent for rules/flow to process.
"""

