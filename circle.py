import time, math
from cfutils import hl_go_to_compat, face_center_yaw_deg

def circle(hl, *, cx=0.0, cy=0.0, z=1.6, radius=0.6, total_time=20.0,
           segments=60, face_center=True, world_yaw_offset_deg=0.0):
    """
    Absolute orbit CCW around (cx,cy) at height z. Ends where it started.
    """
    dt = total_time / float(segments)
    for k in range(segments + 1):
        theta = 2.0 * math.pi * (k / float(segments))
        px = cx + radius * math.cos(theta)
        py = cy + radius * math.sin(theta)
        yaw_deg = (face_center_yaw_deg(px, py, cx, cy, world_yaw_offset_deg)
                   if face_center else None)
        hl_go_to_compat(hl, px, py, z, yaw_deg=yaw_deg, duration_s=dt, relative=False)
        time.sleep(dt)