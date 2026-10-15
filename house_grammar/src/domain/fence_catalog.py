"""Public fence selections shared by all grammar entry points."""

FENCE_STYLES = ('republicano', 'barroco', 'moderno', 'clasico', 'madera')


def validate_fence_style(style):
    if style not in FENCE_STYLES:
        raise ValueError(
            f"Unsupported fence catalog style {style!r}; choose one of: "
            + ', '.join(FENCE_STYLES)
        )
