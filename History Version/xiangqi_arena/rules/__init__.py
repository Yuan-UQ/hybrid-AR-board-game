"""
Rules: validation and calculation only.

This layer determines what is legal and computes outcomes (damage/heal/buffs),
but MUST NOT mutate the official `GameState` directly.
"""

