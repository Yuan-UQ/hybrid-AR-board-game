"""
Single source of truth for runtime game state.

Guide v2 requirement: `GameState` is the only authoritative runtime state.
All layers read from it; confirmed changes are written back via modification/.

Minimum recommended contents (Guide v2):
- current round number / current active side / current phase
- board state
- all piece states
- player states
- active event points
- current per-turn action context
- game end state, history records
- recognition cache (optional)
"""

