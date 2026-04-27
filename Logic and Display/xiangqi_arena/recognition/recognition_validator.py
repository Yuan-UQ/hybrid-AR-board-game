"""
Validate recognition results before entering game flow.

Typical checks:
- missing pieces, duplicates, overlaps
- illegal coordinates/out-of-bounds
- dead pieces must not re-enter the game

This module should NOT judge gameplay legality (that belongs to rules/).
"""

