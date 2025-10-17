# figure8.py
import time
from cfutils import hl_go_to_compat

def figure8(hl, *, cx=0.0, cy=0.0, z=1.2, loops=3, step_d=0.45, step_t=1.75):
    """
    Absolute figure-8 strokes around (cx, cy) at height z.
    Creates a diamond-like 8 with four points per loop.
    """
    pts = [
        ( cx + step_d, cy + step_d ),
        ( cx + step_d, cy - step_d ),
        ( cx - step_d, cy - step_d ),
        ( cx - step_d, cy + step_d ),
    ]
    for _ in range(loops):
        for (px, py) in pts:
            hl_go_to_compat(hl, x=px, y=py, z=z, duration_s=step_t, relative=False)
            time.sleep(step_t + 0.05)
    # return to center
    hl_go_to_compat(hl, x=cx, y=cy, z=z, duration_s=1.2, relative=False)
    time.sleep(1.2 + 0.05)