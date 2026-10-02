"""Keep archived regression tests runnable without packaging the historical runner."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "archive/pilot-2026-10-01"))
