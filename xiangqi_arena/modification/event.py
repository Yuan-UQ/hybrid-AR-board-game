"""
Apply confirmed event point effects to GameState.

Responsibilities (Rulebook V3):
- apply ATK +1 (ammunition, permanent)
- apply HP +1 (medical, clamped to MaxHP)
- apply HP -1 (trap)
- remove/invalidate triggered event points
- write outcomes back to GameState and history
"""

