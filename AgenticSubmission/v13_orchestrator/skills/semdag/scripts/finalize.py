"""Root-only explicit finalization capability. No task/code or role argument."""
import os
import sys
sys.path.insert(0,os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"assets","engine"))
from role_policy import finalize_main
if __name__ == "__main__":
    result=finalize_main()
    raise SystemExit(0 if result.get("ok") else 1)
