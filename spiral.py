# spiral.py
import time, math
from cfutils import hl_go_to_compat, face_center_yaw_deg

def spiral_arc(hl, *, cx=0.0, cy=0.0,
               z_start=1.2, z_end=1.8,
               radius=0.6, segments=24, seg_t=1.1,
               face_center=False, world_yaw_offset_deg=0.0):
    """
    Absolute spiral around (cx, cy) from z_start to z_end.
    - segments * seg_t ~= total duration
    - face_center=True will yaw toward center each segment
    """
    z = z_start
    dz = (z_end - z_start) / max(1, segments)

    for k in range(segments):
        theta = 2.0 * math.pi * (k / float(segments))
        px = cx + radius * math.cos(theta)
        py = cy + radius * math.sin(theta)
        yaw_deg = (face_center_yaw_deg(px, py, cx, cy, world_yaw_offset_deg)
                   if face_center else None)

        hl_go_to_compat(hl, px, py, z, yaw_deg=yaw_deg,
                        duration_s=seg_t, relative=False)
        time.sleep(seg_t)
        z += dz