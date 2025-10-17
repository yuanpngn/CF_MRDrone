# curves.py
from circle import circle

def expressive_curves(hl, *, cx=0.0, cy=0.0, z=1.2,
                      total_s=30.0, radii=(0.8, 0.6),
                      segments=60, face_center=True, world_yaw_offset_deg=0.0):
    """
    Runs two arcs back-to-back, splitting total_s across radii.
    """
    if total_s <= 0:
        return
    half = total_s / 2.0
    r1, r2 = radii if len(radii) == 2 else (radii[0], radii[0])

    circle(hl, cx=cx, cy=cy, z=z, radius=r1, total_time=half,
           segments=segments, face_center=face_center,
           world_yaw_offset_deg=world_yaw_offset_deg)

    circle(hl, cx=cx, cy=cy, z=z, radius=r2, total_time=half,
           segments=segments, face_center=face_center,
           world_yaw_offset_deg=world_yaw_offset_deg)