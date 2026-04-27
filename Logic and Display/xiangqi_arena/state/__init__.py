"""
Runtime state.

`GameState` is the single authoritative source of truth at runtime.
Other layers should read from it and write back only via the modification layer.
"""

