"""Registered native entry: fixed role, no user-supplied role elevation."""
import os
import sys
sys.path.insert(0,os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"assets","engine"))
from role_policy import main
if __name__ == "__main__":
    main('editor','1')
