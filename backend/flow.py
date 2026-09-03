"""Shared flow vocabulary — the canonical application step order.

Every module that raises invalid-state errors references this one definition
instead of keeping its own copy of the string.
"""

STEP_ORDER = "created -> verified -> consented -> assessed -> scored"

# Phase 3: the employment / document verification is a sub-step that happens
# while the application is 'verified' and must be completed before consent —
# it intentionally does not add a status to the canonical order above.
