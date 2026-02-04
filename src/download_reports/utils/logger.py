"""Logger utility."""


class Logger:
    @staticmethod
    def info(msg: str):
        print(f"[INFO] {msg}")
    
    @staticmethod
    def success(msg: str):
        print(f"[OK] {msg}")
    
    @staticmethod
    def error(msg: str):
        print(f"[ERROR] {msg}")
    
    @staticmethod
    def step(num, msg: str):
        print(f"[Step {num}] {msg}")
    
    @staticmethod
    def warning(msg: str):
        print(f"[WARNING] {msg}")