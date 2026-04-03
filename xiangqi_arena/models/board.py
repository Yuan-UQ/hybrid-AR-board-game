"""
Board domain model.

Rulebook V3 uses intersections (nodes), not square cells.
The board model typically tracks occupancy of live pieces and supports position
queries and updates. Dead pieces should not occupy nodes in the rules system.
"""

