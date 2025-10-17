import time

def hover(_hl, duration_s=2.0):
    """
    After HL takeoff or any go_to, the CF holds setpoint.
    A simple sleep maintains hover at last setpoint.
    """
    time.sleep(duration_s)