"""Backend API package for the alternative credit scoring product.

Makes the existing explainability modules importable as top-level modules
(same pattern as app.py and test_explainability.py) without modifying
anything inside explainability/.
"""

import sys
from pathlib import Path

_EXPLAINABILITY_DIR = str(Path(__file__).resolve().parent.parent / "explainability")
if _EXPLAINABILITY_DIR not in sys.path:
    sys.path.insert(0, _EXPLAINABILITY_DIR)
