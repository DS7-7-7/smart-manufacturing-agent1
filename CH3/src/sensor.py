import random
class MotorSensor:
    def read(self) -> float:
        """진동 센서 값을 생성"""
        if random.random() <0.05:
            return round(random.uniform(0.8, 1.5), 3)
        return round(random.uniform(0.2, 0.5), 3)