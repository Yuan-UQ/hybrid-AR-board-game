"""
Apply confirmed attack changes to GameState.

Responsibilities:
- apply damage results to target pieces (including Cannon AOE)
- trigger death checks and update dead/inactive flags
- refresh board occupancy after deaths (dead pieces no longer occupy nodes)
- record outcomes into history (optional)
"""

