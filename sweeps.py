# sweeps.py
import time
from cfutils import hl_go_to_compat

def diagonal_sweeps(hl, *, cx=0.0, cy=0.0, z=1.2,
                    cycles=2, fwd=1.0, fwd_t=3.5,
                    back=1.0, back_t=4.0, pause_s=0.5):
    """
    Absolute sweeps around (cx, cy) at height z.
    Each cycle:
      1) forward glide to (cx+fwd, cy)
      2) hold
      3) diagonal retreat to (cx - back, cy - back)
      4) hold
      5) return to center
    """
    for _ in range(cycles):
        # forward
        hl_go_to_compat(hl, x=cx + fwd, y=cy + 0.0, z=z, duration_s=fwd_t, relative=False)
        time.sleep(fwd_t + 0.05)
        time.sleep(pause_s)

        # retreat diagonally back-right
        hl_go_to_compat(hl, x=cx - back, y=cy - back, z=z, duration_s=back_t, relative=False)
        time.sleep(back_t + 0.05)
        time.sleep(pause_s)

        # return to center
        hl_go_to_compat(hl, x=cx, y=cy, z=z, duration_s=1.0, relative=False)
        time.sleep(1.0 + 0.05)