import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# test_pipeline.py is a script (runs on import, needs the fake Studio): python tests/test_pipeline.py
collect_ignore = ["test_pipeline.py"]
