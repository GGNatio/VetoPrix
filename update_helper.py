#!/usr/bin/env python3
"""Point d'entrée CLI du helper de mise à jour (mode source)."""
import sys
from app.update.apply import main

if __name__ == "__main__":
    sys.exit(main())
