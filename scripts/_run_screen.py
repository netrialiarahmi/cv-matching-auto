"""Run auto_screen.py with dotenv loaded (for local testing)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in dir() else '.')
from dotenv import load_dotenv
load_dotenv()
from scripts.auto_screen import main
sys.exit(main())
