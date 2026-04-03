"""
Attack legality rules.

Responsibilities:
- determine whether a target is an enemy
- determine whether a target is in attack range / direction
- enforce piece-specific attack patterns
- handle special Cannon rules (directional selection, center target requirements)

This module computes legality/options only; it does not apply damage to state.
"""

