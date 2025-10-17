import time
import math
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from cfutils import reset_estimator, hl_go_to_compat
from takeoff import takeoff
from hover import hover  # alias as hold below
from circle import circle
from spiral import spiral_arc
from curves import expressive_curves
from slowing_circles import slowing_circles
from land import land

URI = "radio://0/80/2M"

# -----------------------------
# Show parameters
# -----------------------------
# Heights (meters)
CHEST_Z = 1.2
HIGH_Z  = 1.8

# Speeds
ASCENT_VEL  = 0.7
DESCENT_VEL = 0.25  # gentler landing

# Forbidden box: |x| < 0.5, |y| < 0.5 (1×1). We will stay strictly outside.
BOX_HALF   = 0.5
OUT_MARGIN = 0.10
OUT        = BOX_HALF + OUT_MARGIN  # 0.6 m

# Circle defaults (use radius outside the 1×1 box)
CIRCLE_R      = 0.70         # >= OUT to stay outside
CIRCLE_SEG    = 72
FACE_CENTER   = True
WORLD_YAW_OFF = 0.0

# Convenience
hold = hover

# -----------------------------
# Helpers
# -----------------------------
def goto(hl, x, y, z, dur):
    """Absolute go_to with duration and a short slack sleep."""
    hl_go_to_compat(hl, x=x, y=y, z=z, duration_s=dur, relative=False)
    time.sleep(dur + 0.05)

def nod(hl, amp=0.12, t_each=0.35):
    """Readiness cue at absolute height (no relative)."""
    goto(hl, 0.0, 0.0, max(0.15, CHEST_Z - amp), t_each)
    goto(hl, 0.0, 0.0, CHEST_Z, t_each)

# Perimeter points (8-point ring around the forbidden square)
P = {
    "E":  (+OUT, 0.0),
    "NE": (+OUT, +OUT),
    "N":  (0.0,  +OUT),
    "NW": (-OUT, +OUT),
    "W":  (-OUT, 0.0),
    "SW": (-OUT, -OUT),
    "S":  (0.0,  -OUT),
    "SE": (+OUT, -OUT),
}

def route_along_perimeter(hl, names, z, seg_t):
    """
    Move along the outer square only through adjacent perimeter points,
    so we never cut through the inside box.
    """
    for name in names:
        x, y = P[name]
        goto(hl, x, y, z, seg_t)

def move_edge_safe(hl, start_name, end_name, z, seg_t):
    """
    Move between two perimeter points WITHOUT crossing the inside.
    If they are opposite sides (e.g., E -> W), we go via the top edge by default.
    """
    order = ["E","NE","N","NW","W","SW","S","SE"]  # clockwise
    idx = {n:i for i,n in enumerate(order)}
    si, ei = idx[start_name], idx[end_name]

    # Compute clockwise and counter-clockwise paths and choose the shorter
    def path(cw=True):
        path = []
        i = si
        while i != ei:
            i = (i + (1 if cw else -1)) % len(order)
            path.append(order[i])
        return path

    cw_path  = path(True)
    ccw_path = path(False)
    chosen = cw_path if len(cw_path) <= len(ccw_path) else ccw_path
    route_along_perimeter(hl, chosen, z, seg_t)

if __name__ == "__main__":
    cflib.crtp.init_drivers()
    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
        cf = scf.cf

        # Enable High-Level commander & ensure motor override off
        cf.param.set_value('commander.enHighLevel', '1')
        try:
            cf.param.set_value('motorPowerSet.enable', '0')
        except Exception:
            pass

        # Brushless: arm
        cf.platform.send_arming_request(True)
        time.sleep(0.3)
        print("[ARM] Armed.")

        try:
            reset_estimator(cf)
            hl = cf.high_level_commander

            # ==============================
            # Pre-Dance (~5 s)
            # ==============================
            takeoff(hl, height_m=CHEST_Z, ascent_vel=ASCENT_VEL)
            hold(hl, 0.6)
            nod(hl, amp=0.12, t_each=0.35)  # readiness cue

            # ==================================
            # During Dance (0:00–3:27)
            # ==================================

            # 0:00–0:42 Flow Intro — outer circle (always outside the 1×1)
            circle(
                hl, cx=0.0, cy=0.0, z=CHEST_Z,
                radius=CIRCLE_R, total_time=18.0,
                segments=CIRCLE_SEG, face_center=FACE_CENTER,
                world_yaw_offset_deg=WORLD_YAW_OFF
            )

            # Finish intro with a quick outer square “diamond” (still outside)
            # E -> NE -> N -> NW -> W -> center-OUT on x (east) to reset facing
            route_along_perimeter(hl, ["E","NE","N","NW","W","NW","N","NE","E"], z=CHEST_Z, seg_t=0.8)
            hold(hl, 2.0)

            # 0:42–1:09 (27 s) — Approach & Retreat cycles (outside only)
            # Cycle: East edge -> via North edge -> West edge -> back to East via South edge
            # Each long traverse ~8–9 s across three perimeter hops
            for _ in range(3):
                # Start at E (ensure we are at E)
                goto(hl, *P["E"], CHEST_Z, 1.0)
                move_edge_safe(hl, "E", "W", CHEST_Z, seg_t=2.7)  # E->NE->N->NW->W (no interior)
                hold(hl, 0.5)
                move_edge_safe(hl, "W", "E", CHEST_Z, seg_t=2.7)  # W->SW->S->SE->E
                hold(hl, 0.5)

            # 1:09–1:30 (21 s) — Perimeter weave (figure-8 replacement, still outside)
            route_along_perimeter(hl, ["E","NE","N","NW","W","SW","S","SE","E"], z=CHEST_Z, seg_t=2.3)

            # 1:30–1:57 (27 s) — Spiral Arc (radius outside the box)
            spiral_arc(hl, cx=0.0, cy=0.0, z_start=CHEST_Z, z_end=HIGH_Z,
                       radius=max(CIRCLE_R, 0.7), segments=12, seg_t=1.1)
            # gentle absolute descend back to CHEST_Z (no relative)
            goto(hl, 0.0, 0.0, CHEST_Z, 4.0)

            # 1:57–2:20 (23 s) — Outer “diagonal” sweeps implemented as perimeter routes
            # E -> N -> W (via north edge), then back W -> S -> E (via south edge)
            move_edge_safe(hl, "E", "W", CHEST_Z, seg_t=2.6)
            hold(hl, 1.0)
            move_edge_safe(hl, "W", "E", CHEST_Z, seg_t=2.6)
            hold(hl, 1.0)

            # 2:20–2:50 (30 s) — Expressive Curves (two arcs fully outside)
            expressive_curves(hl, cx=0.0, cy=0.0, z=CHEST_Z,
                              total_s=30.0, radii=(0.85, 0.70),
                              segments=CIRCLE_SEG, face_center=FACE_CENTER,
                              world_yaw_offset_deg=WORLD_YAW_OFF)

            # 2:50–3:20 (30 s) — Slowing Circles (outside)
            slowing_circles(hl, cx=0.0, cy=0.0, z=CHEST_Z, radius=0.75,
                            times=(12.0, 10.0, 8.0), segments=CIRCLE_SEG,
                            face_center=FACE_CENTER, world_yaw_offset_deg=WORLD_YAW_OFF)

            # 3:20–3:27 (7 s) — End Prep: hold at East edge
            goto(hl, *P["E"], CHEST_Z, 2.5)
            hold(hl, 4.5)

            # ==============================
            # Post-Dance (3:27–3:50)
            # ==============================
            # Retreat along perimeter toward wing (E -> SE), then land
            goto(hl, *P["SE"], CHEST_Z, 4.0)
            hold(hl, 1.0)
            # Short settle and land from CHEST_Z with gentle descent velocity
            land(hl, from_height_m=CHEST_Z, descent_vel=DESCENT_VEL)
            print("[DONE] Landed.")

        except KeyboardInterrupt:
            print("[ABORT] KeyboardInterrupt — stopping HL.")
            try:
                cf.high_level_commander.stop()
            except Exception:
                pass
        finally:
            try:
                cf.commander.send_stop_setpoint()
            except Exception:
                pass
            cf.platform.send_arming_request(False)
            print("[DISARM] Disarmed.")