from cfutils import hl_go_to_compat
from safe_sleep import safe_sleep
import time

def takeoff(hl, height_m=1.5, ascent_vel=0.6):
    """
    Performs a TIMED ascent (takeoff) from the ground.
    Uses hl_go_to_compat to control the duration and
    safe_sleep to make the wait interruptible.
    """
    
    # Calculate the desired duration based on height and velocity
    # e.g., (1.3m / 0.26 m/s = 5.0 seconds)
    duration = max(1.0, height_m / max(0.1, ascent_vel))
    
    print(f"[TAKING OFF] Ascending to {height_m}m over {duration:.1f} seconds...")
    
    # Use hl_go_to_compat to perform a timed, relative "goto"
    # This moves straight up from the drone's current ground position.
    hl_go_to_compat(hl, 
                    x=0.0, y=0.0, z=height_m,  # Target height
                    yaw_deg=None,             # Keep current yaw
                    duration_s=duration,      # <--- This forces the 5-sec duration
                    relative=True)            # Move RELATIVE (straight up)
    
    # Use safe_sleep to wait for the move to complete.
    # We wait for the *exact* duration of the move.
    safe_sleep(duration)