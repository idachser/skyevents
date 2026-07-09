"""Point the ephemeris loader at the committed excerpt.

tests/data/de440s.bsp is a jplephem excerpt of DE440s covering
2025-2030 (~0.7 MB); generator tests must work from it alone so the
suite runs offline, in CI included. Set before any skyevents import
triggers a load.
"""

import os

os.environ["SKYEVENTS_DATA"] = os.path.join(
    os.path.dirname(__file__), "data")
