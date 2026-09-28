import time
from sensor import MotorSensor
from collector import DataCollector
sensor = MotorSensor()
collector =DataCollector("motor.txt")
while True:
    value = sensor.read()
    collector.save(value)
    time.sleep(1)