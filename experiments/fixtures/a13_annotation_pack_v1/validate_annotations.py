#!/usr/bin/env python3
"""Standalone entry point copied into the teammate annotation bundle."""

from pathlib import Path
import sys

try:
    from a13_annotation_pack import main
except ModuleNotFoundError:
    repository_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repository_root))
    from experiments.a13_annotation_pack import main


if __name__ == "__main__":
    main()
