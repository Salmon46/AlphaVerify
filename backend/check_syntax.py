import sys
import os

sys.path.append(os.getcwd())

print("Checking imports...")

try:
    from routers.backtest import router as backtest_router
    print("Backtest Router: OK")
except Exception as e:
    print(f"Backtest Router Failed: {e}")

try:
    from routers.backtest import event_engine
    print("Event Engine: OK")
except Exception as e:
    print(f"Event Engine Failed: {e}")

try:
    from mocks import redis_mock
    print("Redis Mock: OK")
except Exception as e:
    print(f"Redis Mock Failed: {e}")

try:
    from routers.wfa import wfa_logic
    print("WFA Logic: OK")
except Exception as e:
    print(f"WFA Logic Failed: {e}")

# ... other checks ...
