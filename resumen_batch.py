import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from daemon import send_summary

if __name__ == "__main__":
    send_summary()
