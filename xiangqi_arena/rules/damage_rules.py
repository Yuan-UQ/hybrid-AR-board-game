"""
Combat numerical calculations.

This module only calculates numbers and clamps (no state mutation), e.g.:
- compute damage from effective ATK
- apply palace-based damage reduction for General/Marshal (min 0)
- compute healing (cannot exceed MaxHP)
- enforce HP bounds after changes
"""

