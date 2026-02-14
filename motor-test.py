import time
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

URI = 'radio://0/80/2M/E7E7E7E7E7' # Change to your CF's URI

def test_motor_sequence(scf):
    cf = scf.cf
    
    # List of motors to test: m1, m2, m3, m4
    motors = ['m1', 'm2', 'm3', 'm4']
    
    for m in motors:
        print(f"Isolating {m}...")
        
        # 1. Set the individual motor thrust (0 to 65535)
        # We use a safe value (approx 30%) for testing without props
        cf.param.set_value(f'motorPowerSet.{m}', 20000)
        
        # 2. ENABLE the motor power set group
        # IMPORTANT: The motors will not spin until this is set to 1
        cf.param.set_value('motorPowerSet.enable', 1)
        
        time.sleep(3) # Let it spin for 2 seconds
        
        # 3. DISABLE and reset for safety
        cf.param.set_value('motorPowerSet.enable', 0)
        cf.param.set_value(f'motorPowerSet.{m}', 0)
        
        print(f"Finished {m} test.")
        time.sleep(1)

if __name__ == '__main__':
    cflib.crtp.init_drivers()
    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
        test_motor_sequence(scf)