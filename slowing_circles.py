# slowing_circles.py
from circle import circle

def slowing_circles(hl, *, cx=0.0, cy=0.0, z=1.2,
                    radius=0.7, times=(12.0, 10.0, 8.0),
                    segments=60, face_center=True, world_yaw_offset_deg=0.0):
    """
    Plays consecutive circles with decreasing durations (tempo slows).
    """
    for T in times:
        if T <= 0:
            continue
        circle(hl, cx=cx, cy=cy, z=z, radius=radius, total_time=T,
               segments=segments, face_center=face_center,
               world_yaw_offset_deg=world_yaw_offset_deg)