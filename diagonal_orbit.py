import time, math
from cfutils import hl_go_to_compat, face_center_yaw_deg
from safe_sleep import safe_sleep

def diagonal_orbit(hl, *,
                   cx=0.0, cy=0.0,
                   z_low=1.2, z_high=2.0,
                   radius=1.2,
                   passes=10,
                   total_time=24.0,
                   face_center=True,
                   world_yaw_offset_deg=0.0):
    """
    Orbits the performer (cx, cy) in a series of 'passes',
    alternating between z_low and z_high at each step.
    
    The drone moves from one point on the circle to the next,
    changing its height at the same time.

    Args:
        hl: High-level commander
        cx, cy: Center of the orbit (performer position)
        z_low: The lower height boundary
        z_high: The upper height boundary
        radius: The radius of the orbit around the performer
        passes: The total number of diagonal movements to make
        total_time: The total time for the entire sequence
        face_center: If True, always face the performer (cx, cy)
        world_yaw_offset_deg: Yaw offset from facing center
    """
    
    if passes <= 0:
        return
    
    # Calculate time for each movement segment
    # Note: This follows the pattern of circle.py, using time.sleep()
    # The 'safe_sleep' from main.py is not used here to keep the module simple.
    dt = max(0.02, total_time / float(passes))
    duration_s = dt * 0.95  # Use most of the time for movement
    sleep_s = dt * 0.05     # Small sleep buffer
             
    angle_step = (2.0 * math.pi) / float(passes)

    for i in range(passes):
        # Determine target height for this pass
        # Pass 0 (i=0) is "up" to z_high
        # Pass 1 (i=1) is "down" to z_low
        mode_is_up = (i % 2 == 0)
        z_end = z_high if mode_is_up else z_low
        
        # Calculate target (x, y) position
        # We are moving TO the (i+1)th point on the circle
        angle_end = (i + 1) * angle_step
        
        x_end = cx + radius * math.cos(angle_end)
        y_end = cy + radius * math.sin(angle_end)
        
        # Calculate yaw to face the performer
        yaw_deg = (face_center_yaw_deg(x_end, y_end, cx, cy, world_yaw_offset_deg)
                   if face_center else None)
        
        # Execute movement
        hl_go_to_compat(hl, x=x_end, y=y_end, z=z_end,
                        yaw_deg=yaw_deg,
                        duration_s=duration_s,
                        relative=False)
        
        # Sleep for the remaining duration
        safe_sleep(duration_s + sleep_s)
        