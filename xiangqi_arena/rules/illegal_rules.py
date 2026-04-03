"""
Illegal operation filtering and interception.

MVP intent (Rulebook V3):
- if an illegal movement or inconsistent recognition result is detected,
  prompt the player to correct the physical position and rescan/retry

This layer should prevent invalid states from entering the formal gameplay pipeline.
"""

