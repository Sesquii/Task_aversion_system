# ui/slider_style.py
"""Shared slider styling: blue by default, green when adjusted (page fill progress)."""
from typing import Any

from nicegui import ui


def progress_slider(
    min_val: int | float,
    max_val: int | float,
    step: int | float,
    value: int | float,
) -> Any:
    """
    Create a slider that is blue by default and turns green when the user
    adjusts it from its initial value (to indicate form fill progress).
    """
    default_val = value
    slider = ui.slider(min=min_val, max=max_val, step=step, value=value).props(
        "color=primary"
    )

    def update_color() -> None:
        try:
            v = int(slider.value) if slider.value is not None else default_val
        except (ValueError, TypeError):
            v = default_val
        color = "positive" if v != default_val else "primary"
        slider.props(f"color={color}")

    slider.on("update:model-value", lambda _: update_color())
    return slider
