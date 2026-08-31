"""Official single-file import entry; helper modules are bundled locally."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from starter.delivery import Agent

__all__ = ["Agent"]
