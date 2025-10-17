import time
from cfutils import hl_takeoff_compat

def takeoff(hl, height_m=1.6, ascent_vel=0.7):
    hl_takeoff_compat(hl, height_m, ascent_vel)
    time.sleep(max(1.0, height_m / max(0.1, ascent_vel)) + 0.3)