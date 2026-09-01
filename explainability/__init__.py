"""Explainable AI repayment assessment package.

Supports both script usage (python explainability/generate_report.py) and
package imports (from explainability import generate_repayment_report).
"""

import sys
from pathlib import Path

_PACKAGE_DIR = str(Path(__file__).resolve().parent)
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)

from generate_report import generate_repayment_report  # noqa: E402

__all__ = ["generate_repayment_report"]
