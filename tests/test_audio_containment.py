"""pyglet must not take over the macOS application or its signals."""

import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific")

CODE = r"""
import signal, sys
before = (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM))
sys.path.insert(0, ".")
from DisplayCAL import audio
audio.safe_init()
import pyglet.media, pyglet.app
after = (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM))
print("SAME" if before == after else "CHANGED", type(pyglet.app.platform_event_loop).__name__)
"""


def test_importing_the_audio_stack_keeps_our_signal_handlers():
    pytest.importorskip("pyglet")
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-I", "-c", CODE],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    ).stdout
    assert "SAME InertPlatformEventLoop" in out, out


def test_application_quits_cleanly_on_sigterm(monkeypatch):
    import signal

    from DisplayCAL.ui import application as app_mod

    quits = []
    fake = type("A", (), {"quit": lambda self: quits.append(1)})()
    app_mod.Application._signal_handler(fake, signal.SIGTERM, None)
    assert quits == [1]
