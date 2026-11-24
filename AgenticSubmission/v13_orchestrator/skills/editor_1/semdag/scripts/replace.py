"""Editor-only exact fragment replacement in the statically bound slot."""
import os
import sys
sys.path.insert(0,os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"assets","engine"))
from role_policy import replace_main
if __name__ == "__main__":
    result=replace_main("1")
    raise SystemExit(0 if result.get("ok") else 1)
