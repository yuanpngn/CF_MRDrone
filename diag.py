# diag.py
import time
from cfutils import hl_move_distance_compat

def diag(hl, dx=0.4, dy=0.4, dz=0.0, duration_s=2.0):
    """Relative step: move by (dx, dy, dz) safely using move_distance."""
    hl_move_distance_compat(hl, dx, dy, dz, duration_s=duration_s)
    time.sleep(duration_s + 0.05)