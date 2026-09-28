from datetime import datetime
class DataCollector:
    def __init__(self, filename):
        self.filename =filename
    def save(self, value):
        timestamp =datetime.now().strftime("%Y-%m-%d%H:%M:%S")
        with open(self.filename, "a") as f:
            f.write(f"{timestamp},{value}\n")
        print(timestamp, value)