"""Shared flow vocabulary — the canonical application step order.

Every module that raises invalid-state errors references this one definition
instead of keeping its own copy of the string.
"""

STEP_ORDER = "created -> verified -> consented -> assessed -> scored"
