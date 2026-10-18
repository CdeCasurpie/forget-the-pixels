"""Style inheritance for the piece catalog.

The building style is a heredable preference, not a purity constraint. A piece
that leaves its style automatic inherits the building style; a piece that names
one explicitly replaces the preference for that piece only and is never rejected
for being different. Unknown catalog values still fail downstream, where the
catalogue actually knows the vocabulary.
"""

AUTOMATIC = (None, 'auto', '')


def resolve_style(local, building_style):
    """The style a piece should use: its own when explicit, else the building's."""
    return building_style if local in AUTOMATIC else local
