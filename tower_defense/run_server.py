#!/usr/bin/env python3
"""Start the Tower Defense game server."""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from network.server import main

if __name__ == "__main__":
    main()
