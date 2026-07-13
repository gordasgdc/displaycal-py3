"""Regression tests for the console/gui-script entry points in pyproject.toml.

See issue #797: several entry points pointed at DisplayCAL.main:main_*
functions that did not exist, so the installed console scripts raised
AttributeError/ModuleNotFoundError on launch.
"""

from importlib.metadata import entry_points

import pytest


def _displaycal_entry_points():
    eps = entry_points()
    for group in ("console_scripts", "gui_scripts"):
        for ep in eps.select(group=group):
            if ep.name.startswith("displaycal"):
                yield ep


@pytest.mark.parametrize(
    "ep", list(_displaycal_entry_points()), ids=lambda ep: ep.name
)
def test_entry_point_resolves_to_callable(ep):
    """Every declared displaycal-* entry point must load to a callable."""
    target = ep.load()

    assert callable(target), f"{ep.name} ({ep.value}) did not resolve to a callable"


def test_at_least_one_entry_point_was_checked():
    """Guard against the parametrization silently collecting zero entries."""
    assert list(_displaycal_entry_points())
