"""
Piece domain model.

All pieces are represented through a unified model (not one class per piece type).
Typical fields:
- unique id (marker-based), faction, piece type
- current position (x, y) on the 9x10 node grid
- combat attributes: HP, MaxHP, ATK
- death state / operability state
- buffs/status (e.g. permanent ATK+1 from ammunition points)
"""

