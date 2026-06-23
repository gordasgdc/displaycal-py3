"""Qt user interface layer for DisplayCAL (4.0).

This package hosts the Qt port of DisplayCAL's user interface. It is the
successor to the legacy ``wx_*`` modules, which are being phased out.

Binding policy
--------------
We talk to Qt exclusively through `qtpy`, so the actual binding can be swapped
without touching call sites. PySide6 is the default and the only binding we
ship/test against; ``QT_API`` is pinned to it here before ``qtpy`` is imported
anywhere, so importing this package first guarantees a consistent binding for
the whole process.

Subsequent modules should ``import`` Qt symbols from ``qtpy`` (e.g.
``from qtpy.QtWidgets import QMainWindow``), never directly from ``PySide6``.
"""

from __future__ import annotations

import os

# Pin the binding before qtpy is imported anywhere in the process. Respect an
# explicit override (e.g. for experimenting with another binding) if present.
os.environ.setdefault("QT_API", "pyside6")

import qtpy  # noqa: E402  (must follow the QT_API pin above)

#: The Qt binding qtpy resolved to (e.g. ``"pyside6"``).
BINDING = qtpy.API_NAME

__all__ = ["BINDING"]
