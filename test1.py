#!/usr/bin/env python3
import time, math, sys, select, json, socket, threading
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig

from safe_sleep import safe_sleep, check_keyboard_input, get_emergency_flag

from cfutils import reset_estimator, hl_go_to_compat
from takeoff import takeoff
from hover import hover
from circle import circle
from land import land
from diagonal_orbit import diagonal_orbit

URI = "radio://0/80/2M"

# =========================
# UDP Streaming Configuration
# =========================
# Enable/disable UDP streaming to Unity
# Set UDP_ENABLED = True to stream real-time pose data to Unity for visualization
# Packet format matches mock_pos.py: {"x": float, "y": float, "z": float, "yaw_deg": float, "ts": float}
# Unity coordinate mapping: unityX = -cfY, unityY = cfZ, unityZ = cfX
UDP_ENABLED = True          # Set to False to disable UDP streaming
UDP_IP = "172.20.10.3"        # Destination IP (127.0.0.1 for local Unity, or Quest IP)
UDP_PORT = 5005             # Destination port (must match Unity receiver)
UDP_HZ = 30.0               # Send rate (Hz)

# =========================
# Global choreo parameters
# =========================
# Coordinate system:
# - Performer is at origin (0, 0, 0)
# - Positive Y is in front of the performer (toward audience)
# - Positive X is to the performer's right
# - Positive Z is upward

H_STD   = 1.3    # standard height (m)
H_LOW   = 1.2    # diagonal phase base height (m)
H_MAX   = 2.0    # spiral/wave max height (m)

# "Center front" = 0.5 meter in front of the performer (Original 1.0m)
CENTER_FRONT_Y = 0.5

RETREAT_DIST = 1.5  # additional distance back from center front (m)
SIDE_DIST    = 1.0  # left/right from center line (m) (Original 1.0m)
CIRCLE_R     = 0.7 # orbit radius around performer (m) (Original 1.2m)

# Diagonal movement parameters (1:26-1:50)
DIAG_HORIZONTAL = 1.0  # horizontal distance per diagonal pass (m) (Original 1.5m)
DIAG_VERTICAL   = 0.4  # height change per diagonal pass (m) - reduced from 0.7 for gentler slope

ASCENT_VEL   = 0.25 # take off much slower; approx. 0.25 meter per second; will take around 5 seconds to reach 1.3 meters (std.height)
DESCENT_VEL  = 0.125

FACE_CENTER  = True
YAW_OFF_DEG  = 0.0

# Named absolute points in the stage plane (x,y)
# Performer at (0,0), drone operates at y=CENTER_FRONT_Y normally
POINTS = {
    "CENTER":  (0.0, CENTER_FRONT_Y),                    # 0.5m in front of performer
    "RIGHT":   (+SIDE_DIST, CENTER_FRONT_Y),             # 0.5m right of center front
    "LEFT":    (-SIDE_DIST, CENTER_FRONT_Y),             # 0.5m left of center front
    "RETREAT": (0.0, 1.3),     # 1.3m from performer (Original 1.8m)
}

SLACK = 0.05  # timing slack after each commanded segment

# Global variables for UDP streaming
udp_sock = None
latest_pose = {"x": 0.0, "y": 0.0, "z": 0.0, "yaw_deg": 0.0, "ts": 0.0}
pose_lock = threading.Lock()
streaming_active = False

def pose_callback(timestamp, data, logconf):
    """Callback for Crazyflie pose logging - updates global pose for UDP streaming."""
    global latest_pose
    with pose_lock:
        latest_pose = {
            "x": data['stateEstimate.x'],
            "y": data['stateEstimate.y'],
            "z": data['stateEstimate.z'],
            "yaw_deg": data['stabilizer.yaw'],  # or 'stateEstimate.yaw' if available
            "ts": time.time()
        }

def udp_streaming_thread():
    """Background thread that sends pose data over UDP at specified rate."""
    global streaming_active, udp_sock
    dt = 1.0 / UDP_HZ
    
    while streaming_active:
        try:
            with pose_lock:
                pkt = latest_pose.copy()
            
            # Send UDP packet
            if udp_sock:
                udp_sock.sendto(json.dumps(pkt).encode("utf-8"), (UDP_IP, UDP_PORT))
            
            time.sleep(dt)
        except Exception as e:
            print(f"[UDP] Error sending: {e}")
            time.sleep(dt)

def setup_pose_logging(cf):
    """Set up Crazyflie logging for position and orientation."""
    log_conf = LogConfig(name='Pose', period_in_ms=33)  # ~30Hz
    
    # Add pose variables to log
    log_conf.add_variable('stateEstimate.x', 'float')
    log_conf.add_variable('stateEstimate.y', 'float')
    log_conf.add_variable('stateEstimate.z', 'float')
    log_conf.add_variable('stabilizer.yaw', 'float')
    
    # Register callback
    cf.log.add_config(log_conf)
    log_conf.data_received_cb.add_callback(pose_callback)
    log_conf.start()
    
    return log_conf

def goto(hl, xy, z, dur, face_performer=True):
    """Absolute go_to with duration + small slack. Checks for keyboard input during movement.
    
    Args:
        hl: High-level commander
        xy: Target (x, y) position tuple
        z: Target z height
        dur: Duration in seconds
        face_performer: If True, drone faces performer at (0,0). If False, maintains current yaw.
    """
    from cfutils import face_center_yaw_deg
    
    x, y = xy
    
    # Calculate yaw to face performer at origin (0, 0)
    if face_performer:
        yaw_deg = face_center_yaw_deg(x, y, 0.0, 0.0, YAW_OFF_DEG)
    else:
        yaw_deg = None
    
    hl_go_to_compat(hl, x=x, y=y, z=z, yaw_deg=yaw_deg, duration_s=dur, relative=False)
    
    # Sleep in small increments to check for keyboard input
    elapsed = 0
    interval = 0.1
    total_sleep = dur + SLACK
    
    while elapsed < total_sleep:
        if check_keyboard_input():
            emergency_stop = True
            raise KeyboardInterrupt("Keyboard input detected - initiating smooth landing")
        time.sleep(min(interval, total_sleep - elapsed))
        elapsed += interval

def main():
    global emergency_stop, udp_sock, streaming_active
    cflib.crtp.init_drivers(enable_debug_driver=False)
    
    # Initialize UDP socket if enabled
    if UDP_ENABLED:
        try:
            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print(f"[UDP] Initialized - sending to {UDP_IP}:{UDP_PORT} at {UDP_HZ}Hz")
        except Exception as e:
            print(f"[UDP] Failed to initialize: {e}")
            udp_sock = None
    
    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
        cf = scf.cf
        current_height = 0.0  # Track current height for emergency landing
        log_conf = None
        udp_thread = None

        # High-level + safety setup
        cf.param.set_value('commander.enHighLevel', '1')
        try:
            cf.param.set_value('motorPowerSet.enable', '0')
        except Exception:
            pass

        # Brushless arming (no-op on some platforms)
        try:
            cf.platform.send_arming_request(True)
        except Exception:
            pass
        time.sleep(0.3)
        print("[ARM] Armed.")
        print("[INFO] Press any key at any time to initiate emergency smooth landing...")
        
        # Set up pose logging for UDP streaming
        if UDP_ENABLED and udp_sock:
            try:
                log_conf = setup_pose_logging(cf)
                time.sleep(0.5)  # Let logging stabilize
                
                # Start UDP streaming thread
                streaming_active = True
                udp_thread = threading.Thread(target=udp_streaming_thread, daemon=True)
                udp_thread.start()
                print("[UDP] Streaming started")
            except Exception as e:
                print(f"[UDP] Failed to start logging: {e}")

        try:
            reset_estimator(cf)
            hl = cf.high_level_commander

            # =========================
            # Pre-Dance (0:00–0:15)
            # =========================
            # Initial placement: Drone is on the ground at center front (0, 0.5, 0.0)
            # facing the performer (toward negative Y direction).

            # Takeoff from ground to 1.5 m at center front position
            print("[DEBUG] Sending takeoff command...")
            takeoff(hl, height_m=H_STD, ascent_vel=ASCENT_VEL)
            print("[DEBUG] Takeoff command issued.")
            current_height = H_STD
            # goto(hl, POINTS["CENTER"], H_STD, 0.0)   # ensure we're at center front

            # 0:00–0:05 Hover
            hover(hl, 5.0)
            print("[DEBUG] hover command issued.")
            

            # 0:05–0:10 Retreat farther back
            goto(hl, POINTS["RETREAT"], H_STD, 5.0)
            print("[DEBUG] retreat command issued.")
            
            # 0:10–0:15 Approach again to center front
            goto(hl, POINTS["CENTER"], H_STD, 5.0)
            print("[DEBUG] center command issued.")
            
            # =========================
            # Main Dance (0:16–3:30)
            # =========================

            # 0:16–0:20 Fly right
            goto(hl, POINTS["RIGHT"], H_STD, 4.0)
            print("[DEBUG] right command issued.")
            
            # 0:21–0:23 Hover
            hover(hl, 2.0)

            # 0:23–0:29 Back to center
            goto(hl, POINTS["CENTER"], H_STD, 6.0)

            # 0:30–0:36 Fly left
            goto(hl, POINTS["LEFT"], H_STD, 6.0)

            # 0:37–0:40 Hover
            hover(hl, 3.0)

            # 0:40–0:46 Back to center
            goto(hl, POINTS["CENTER"], H_STD, 6.0)

            # 0:46–1:15 Circle around performer (flat at 1.5m height), end at center front
            
            # Move to top of circle to start
            # NOTE: The circle radius (0.7m) is larger than the center front Y (0.5m).
            # We will start the circle from 90 degrees (0.0, 0.7)
            # First, move from (0, 0.5) to (0, 0.7)
            goto(hl, (0.0, CIRCLE_R), H_STD, 0.5)
            
            # First circle (14.5 seconds) - faster orbit
            start_angle_deg = 90.0
            circle(hl,
                   cx=0.0, cy=0.0, z=H_STD,
                   radius=CIRCLE_R, total_time=14.5,
                   segments=45, face_center=FACE_CENTER,
                   world_yaw_offset_deg=YAW_OFF_DEG,
                   start_angle_deg=start_angle_deg)
            
            # Second circle (14.5 seconds) - same speed, continues smoothly
            circle(hl,
                   cx=0.0, cy=0.0, z=H_STD,
                   radius=CIRCLE_R, total_time=14.5,
                   segments=45, face_center=FACE_CENTER,
                   world_yaw_offset_deg=YAW_OFF_DEG,
                   start_angle_deg=start_angle_deg)
            
            # Return to center front after circles
            goto(hl, POINTS["CENTER"], H_STD, 0.6)

            # 1:16–1:20 Retreat
            goto(hl, POINTS["RETREAT"], H_STD, 4.0)

            # 1:21–1:26 Approach
            goto(hl, POINTS["CENTER"], H_STD, 5.0)

            # 1:26–1:50 Diagonal movements while circling around the performer
            diagonal_orbit(hl,
                        cx=0.0, cy=0.0,
                        z_low=H_LOW,
                        z_high=H_LOW + DIAG_VERTICAL,
                        radius=CIRCLE_R,
                        passes=10,
                        total_time=24.0, # 10 passes * 2.4s each
                        face_center=FACE_CENTER,
                        world_yaw_offset_deg=YAW_OFF_DEG)

            # Update current height after the full sequence
            current_height = H_LOW # The last pass (i=9, "down") ends at z_low

            start_angle_deg = 90.0
            circle(hl,
                   cx=0.0, cy=0.0, z=H_STD,
                   radius=CIRCLE_R, total_time=9.67,
                   segments=30, face_center=FACE_CENTER,
                   world_yaw_offset_deg=YAW_OFF_DEG,
                   start_angle_deg=start_angle_deg)
            
            # Second circle (9.67 seconds)
            circle(hl,
                   cx=0.0, cy=0.0, z=H_STD,
                   radius=CIRCLE_R, total_time=9.67,
                   segments=30, face_center=FACE_CENTER,
                   world_yaw_offset_deg=YAW_OFF_DEG,
                   start_angle_deg=start_angle_deg)
            
            # Third circle (9.67 seconds)
            circle(hl,
                   cx=0.0, cy=0.0, z=H_STD,
                   radius=CIRCLE_R, total_time=9.67,
                   segments=30, face_center=FACE_CENTER,
                   world_yaw_offset_deg=YAW_OFF_DEG,
                   start_angle_deg=start_angle_deg)
            
            # End at center front
            goto(hl, POINTS["CENTER"], H_STD, 0.8)
            current_height = H_STD

            # 2:21–2:43 Diagonal Retreat/Approach blocks with hovers
            # 2:21–2:25 Retreat
            goto(hl, POINTS["RETREAT"], H_STD, 4.0)
            # 2:25–2:28 Hover
            hover(hl, 3.0)
            # 2:28–2:32 Approach
            goto(hl, POINTS["CENTER"], H_STD, 4.0)
            # 2:32–2:36 Retreat
            goto(hl, POINTS["RETREAT"], H_STD, 4.0)
            # 2:36–2:39 Hover
            hover(hl, 3.0)
            # 2:39–2:43 Approach
            goto(hl, POINTS["CENTER"], H_STD, 4.0)

            # 2:51–3:30 Wave path while circling (using diagonal_orbit)
            diagonal_orbit(hl,
                        cx=0.0, cy=0.0,
                        z_low=H_LOW,
                        z_high=H_LOW + DIAG_VERTICAL,
                        radius=CIRCLE_R,
                        passes=10,
                        total_time=39.0, # 10 passes * 3.9s each
                        face_center=FACE_CENTER,
                        world_yaw_offset_deg=YAW_OFF_DEG)

            # Update current height after the full sequence
            current_height = H_LOW # The last pass (i=9, "down") ends at z_low
            
            # Ensure we finish at center front
            goto(hl, POINTS["CENTER"], H_STD, 0.8)

            # =========================
            # Post-Dance (3:30–3:43+)
            # =========================
            # 3:30–3:35 Retreat ~1.5 m
            goto(hl, POINTS["RETREAT"], H_STD, 5.0)
            # 3:35–3:43 Approach to center front
            goto(hl, POINTS["CENTER"], H_STD, 8.0)

            # Descent & landing
            land(hl, from_height_m=H_STD, descent_vel=DESCENT_VEL)
            current_height = 0.0
            print("[DONE] Landed.")

        except KeyboardInterrupt:
            print("\n[EMERGENCY] Keyboard input detected — initiating smooth emergency landing...")
            try:
                # Stop current high-level commands
                cf.high_level_commander.stop()
                time.sleep(0.2)
                
                # Perform smooth emergency landing from current height
                # Estimate height (use last known height or default to H_STD)
                emergency_height = current_height if current_height > 0 else H_STD
                print(f"[EMERGENCY] Landing from approximately {emergency_height:.2f}m...")
                
                # Smooth descent at safe velocity
                land(hl, from_height_m=emergency_height, descent_vel=DESCENT_VEL)
                print("[EMERGENCY] Emergency landing completed.")
            except Exception as e:
                print(f"[ERROR] Error during emergency landing: {e}")
                # Final fallback - send stop command
                try:
                    cf.high_level_commander.stop()
                except Exception:
                    pass
        finally:
            # Stop UDP streaming
            if UDP_ENABLED and streaming_active:
                streaming_active = False
                if udp_thread:
                    udp_thread.join(timeout=1.0)
                print("[UDP] Streaming stopped")
            
            # Stop logging
            if log_conf:
                try:
                    log_conf.stop()
                except Exception:
                    pass
            
            # Close UDP socket
            if udp_sock:
                try:
                    udp_sock.close()
                except Exception:
                    pass
            
            # Stop drone commands
            try:
                cf.commander.send_stop_setpoint()
            except Exception:
                pass
            try:
                cf.platform.send_arming_request(False)
            except Exception:
                pass
            print("[DISARM] Disarmed.")

if __name__ == "__main__":
    main()