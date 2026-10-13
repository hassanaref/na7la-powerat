#!/usr/bin/env python3
"""Na7la Powerat 2.0 (نحلة باورات) - CLI Entry Point.
Alias for powerk.py
"""
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from powerk import main

if __name__ == "__main__":
    sys.exit(main())
