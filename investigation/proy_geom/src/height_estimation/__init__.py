"""Compatibility imports for the former height-estimation prototype.

New code must import from facade_observations or structural_estimation.
"""
from facade_observations.roof_boundary import split_vertical_strip
from structural_estimation.height import fit_height, predicted_row


def split_strip(rgb, min_segment=8):
    """Deprecated alias retained so the recorded Step 8 experiment reproduces."""
    return split_vertical_strip(rgb, min_segment)
