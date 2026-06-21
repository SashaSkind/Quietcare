"""Quietcare BAND @mention mesh — two long-running agents that coordinate over
BAND chat rooms via the official band-sdk.

- ``elder``     — the safety companion; on an unresolved incident it recruits and
                  @mentions the caretaker agent in a room.
- ``caretaker`` — triages the escalation and decides how to alert the human; never
                  authorizes 911 autonomously.

Run each in its own terminal (see app/band_mesh/elder.py and caretaker.py).
"""
