"""
Root conftest.py - pytest configuration

Adds the root project folder (containing pyproject.toml and /pyon) to sys.path
so that `import pyon` always succeeds from anywhere pytest is run.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
