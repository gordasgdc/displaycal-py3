"""Tests for the Qt progress dialog throbber assets, ``DisplayCAL.ui.progress_widgets``.

See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 5 -- worker execution
layer). progress_type 0 ("processing") is regression-covered explicitly: its
frame count depends on a hardcoded sanity check
(``DisplayCAL.wx_windows.ProgressDialog.get_bitmaps``) that silently started
failing in the wx dialog itself back in 2022 once a 10th shutter frame was
added for issue #45, so it's easy to reintroduce without noticing.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL.ui import progress_widgets as pw  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.mark.parametrize(
    "progress_type,expected_count",
    [(0, 137), (1, 15), (2, 63)],
)
def test_get_progress_bitmaps_frame_counts(qapp, progress_type, expected_count):
    frames = pw.get_progress_bitmaps(progress_type)
    assert len(frames) == expected_count
    assert all(not frame.isNull() for frame in frames)
    assert all(
        frame.size().width() == 200 and frame.size().height() == 200 for frame in frames
    )


def _avg_brightness(pixmap):
    """Mean R/G/B value across a QPixmap's pixels, as a cheap content probe."""
    import numpy as np
    from qtpy.QtGui import QImage

    qimg = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = qimg.width(), qimg.height()
    buf = np.frombuffer(qimg.constBits(), dtype=np.uint8, count=h * qimg.bytesPerLine())
    arr = buf.reshape(h, qimg.bytesPerLine())[:, : w * 4].reshape(h, w, 4)
    return float(arr[..., :3].mean())


def test_processing_frames_shutter_closes_monotonically(qapp):
    """The first 9 processing frames are the shutter closing, frame-by-frame.

    Regression test: re-sorting ``get_data_path()``'s result by full path
    (instead of trusting its own basename sort) let a same-named but stale
    file from a lower-priority search dir (e.g. an old site-packages install)
    jump to the front, silently swapping in the wrong frame -- a frame-count
    assertion alone doesn't catch this, only wrong content/order does.
    """
    frames = pw.get_progress_bitmaps(0)
    brightness = [_avg_brightness(frames[i]) for i in range(9)]
    # Neighbouring frames are near-identical (sub-1% brightness change), so
    # allow a small tolerance for encoding/rounding noise between them.
    tolerance = 0.1
    assert all(
        brightness[i] >= brightness[i + 1] - tolerance
        for i in range(len(brightness) - 1)
    ), brightness
