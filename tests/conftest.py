"""Test configuration: make the repository root importable without installing."""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# GUI smoke tests must work on headless CI runners.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
