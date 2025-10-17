# cfutils.py
import time, math, logging, inspect
logging.basicConfig(level=logging.INFO)

# ---------- generic helpers ----------
def reset_estimator(cf):
    cf.param.set_value('kalman.resetEstimation','1'); time.sleep(0.1)
    cf.param.set_value('kalman.resetEstimation','0'); time.sleep(1.0)

def call_with_keywords(func, kwargs_ordered):
    sig = inspect.signature(func)
    names = [p for p in sig.parameters.keys()]
    call_kwargs = {k:v for (k,v) in kwargs_ordered if k in names}
    missing = [n for n,p in sig.parameters.items()
               if p.default is inspect._empty and n not in call_kwargs]
    if missing:
        raise TypeError(f"{func.__name__} requires {missing} (keys: {names})")
    return func(**call_kwargs)

# ---------- HL compat: takeoff / land ----------
def hl_takeoff_compat(hl, height_m, ascent_vel=0.6):
    try:
        return call_with_keywords(hl.takeoff, [
            ('height', height_m),
            ('velocity', ascent_vel),
            ('duration_s', max(1.0, height_m / max(0.1, ascent_vel))),
        ])
    except Exception:
        try: return hl.takeoff(height_m, ascent_vel)
        except Exception:
            try: return hl.takeoff(height_m, max(1.0, height_m / max(0.1, ascent_vel)))
            except Exception: return hl.takeoff(height_m)

def hl_land_compat(hl, from_height_m, descent_vel=0.4):
    duration = max(1.5, from_height_m / max(0.1, descent_vel))
    try:
        return call_with_keywords(hl.land, [
            ('velocity', descent_vel),
            ('height', 0.0),
            ('duration_s', duration),
        ])
    except Exception:
        for attempt in [
            lambda: hl.land(descent_vel, duration),
            lambda: hl.land(0.0,       duration),
            lambda: hl.land(duration),
        ]:
            try: return attempt()
            except Exception: pass
        # as last resort try height-only
        return call_with_keywords(hl.land, [('height', 0.0)])

# ---------- HL compat: absolute go_to ----------
def hl_go_to_compat(hl, x, y, z, *, yaw_deg=None, duration_s=None, relative=False):
    """
    Use for ABSOLUTE setpoints. Avoid using `relative=True` here;
    use hl_move_distance_compat for relative steps.
    """
    try:
        return call_with_keywords(hl.go_to, [
            ('x', x), ('y', y), ('z', z),
            ('yaw', math.radians((yaw_deg or 0.0))),
            ('yaw_deg', yaw_deg),
            ('duration_s', duration_s),
            ('relative', relative),
        ])
    except Exception:
        try:
            yaw_rad = math.radians(yaw_deg) if yaw_deg is not None else 0.0
            if duration_s is not None:
                return hl.go_to(x, y, z, yaw_rad, duration_s)
            else:
                return hl.go_to(x, y, z, yaw_rad)
        except Exception:
            if duration_s is not None:
                return call_with_keywords(hl.go_to, [
                    ('x', x), ('y', y), ('z', z),
                    ('duration_s', duration_s),
                ])
            return call_with_keywords(hl.go_to, [('x', x), ('y', y), ('z', z)])

# ---------- HL compat: RELATIVE safe steps ----------
def hl_move_distance_compat(hl, dx, dy, dz, *, duration_s=None, velocity=None):
    """
    SAFE relative motion. Preferred for diag/forward/left/backward/upward/downward.
    """
    # preferred: explicit keywords
    try:
        return call_with_keywords(hl.move_distance, [
            ('x', dx), ('y', dy), ('z', dz),
            ('duration_s', duration_s), ('velocity', velocity),
        ])
    except Exception:
        # positional duration if available
        try:
            if duration_s is not None:
                return hl.move_distance(dx, dy, dz, duration_s)
            else:
                return hl.move_distance(dx, dy, dz)
        except Exception:
            # velocity-only variant
            if velocity is not None:
                return call_with_keywords(hl.move_distance, [
                    ('x', dx), ('y', y), ('z', dz),  # NOTE: keep api robust
                    ('velocity', velocity),
                ])
            raise RuntimeError("move_distance not supported; aborting relative move.")

def face_center_yaw_deg(px, py, cx, cy, world_yaw_offset_deg=0.0):
    ang = math.degrees(math.atan2(cy - py, cx - px))
    return ang + world_yaw_offset_deg