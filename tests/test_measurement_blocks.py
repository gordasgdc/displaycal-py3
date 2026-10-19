"""Block measurement: splitting and merging keep every patch exactly once."""

import os

import pytest

from DisplayCAL import measurement_blocks as mb


def make_ti1(path, n):
    rows = ["1 100.0 100.0 100.0 95.0 100.0 108.0"]  # white first, ids are strings
    for i in range(2, n + 1):
        v = (i * 7) % 100
        rows.append(f"{i} {v}.0 {(v * 3) % 100}.0 {(v * 5) % 100}.0 {v} {v} {v}")
    text = (
        'CTI1\nKEYWORD "DEVICE_CLASS"\nDEVICE_CLASS "DISPLAY"\nNUMBER_OF_FIELDS 7\n'
        "BEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n" + "\n".join(rows) + "\nEND_DATA\n"
    )
    path.write_text(text)


def fake_ti3(block_ti1, out):
    """What dispread would write: the block's rows with measured XYZ."""
    t = mb.read_table(block_ti1)
    rows = []
    for r in t.rows:
        # XYZ = 2 * RGB-derived value; white normalised to Y=100 in each block
        y = 100.0 if r[1:4] == ["100.0"] * 3 else float(r[1]) * 0.9
        rows.append([r[0], *r[1:4], f"{y * 0.95:.3f}", f"{y:.3f}", f"{y * 1.08:.3f}"])
    mb.atomic_write(out, mb.render(mb.Table(t.header, t.fields, rows, t.footer)))


def test_plan_blocks():
    assert mb.plan_blocks(300, 500) == 1
    assert mb.plan_blocks(560, 500) == 1  # not worth splitting (within 20%)
    assert mb.plan_blocks(11000, 500) == 22
    assert mb.plan_blocks(11000, 0) == 1


def test_split_repeats_white_and_covers_everything_once(tmp_path):
    ti1 = tmp_path / "chart.ti1"
    make_ti1(ti1, 1001)
    blocks = mb.split_ti1(str(ti1), "chart", 250)
    assert len(blocks) == 4
    seen = []
    for b in blocks:
        t = mb.read_table(b.base + ".ti1")
        assert t.rows[0][0] == "1"  # white reference first in every block
        seen += [r[0] for r in t.rows[1:]]
    assert sorted(seen, key=int) == [str(i) for i in range(2, 1002)]


def test_merge_equals_single_run_for_consistent_readings(tmp_path):
    ti1 = tmp_path / "chart.ti1"
    make_ti1(ti1, 401)
    blocks = mb.split_ti1(str(ti1), "chart", 100)
    parts = []
    for b in blocks:
        fake_ti3(b.base + ".ti1", b.base + ".ti3")
        parts.append(b.base + ".ti3")
    out = tmp_path / "chart.ti3"
    rep = mb.merge_ti3(parts, str(ti1), str(out))
    assert rep["patches"] == 401
    # the same readings measured in one run
    fake_ti3(str(ti1), str(tmp_path / "single.ti3"))
    assert mb.read_table(str(out)).rows == mb.read_table(str(tmp_path / "single.ti3")).rows


def test_merge_refuses_when_a_block_is_missing(tmp_path):
    ti1 = tmp_path / "chart.ti1"
    make_ti1(ti1, 401)
    blocks = mb.split_ti1(str(ti1), "chart", 100)
    parts = []
    for b in blocks[:-1]:  # last block never finished
        fake_ti3(b.base + ".ti1", b.base + ".ti3")
        parts.append(b.base + ".ti3")
    with pytest.raises(mb.CGATSError):
        mb.merge_ti3(parts, str(ti1), str(tmp_path / "chart.ti3"))
    assert not (tmp_path / "chart.ti3").exists()  # no incomplete result is left


def test_chart_without_white_cannot_be_split(tmp_path):
    ti1 = tmp_path / "c.ti1"
    make_ti1(ti1, 50)
    t = mb.read_table(str(ti1))
    t.rows[0][1:4] = ["50.0"] * 3
    ti1.write_text(mb.render(t))
    with pytest.raises(mb.CGATSError):
        mb.split_ti1(str(ti1), "c", 10)


def test_atomic_write_keeps_previous_content_on_failure(tmp_path, monkeypatch):
    p = tmp_path / "x.ti3"
    p.write_text("old valid")

    def boom(*a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        mb.atomic_write(str(p), "new")
    assert p.read_text() == "old valid"
    assert not [f for f in os.listdir(tmp_path) if ".tmp-" in f]  # temp cleaned


def test_block_ti3_valid(tmp_path):
    ti1 = tmp_path / "chart.ti1"
    make_ti1(ti1, 120)
    b = mb.split_ti1(str(ti1), "chart", 50)[0]
    fake_ti3(b.base + ".ti1", b.base + ".ti3")
    assert mb.block_ti3_valid(b.base + ".ti3", len(b.row_indices))
    assert not mb.block_ti3_valid(b.base + ".ti3", len(b.row_indices) + 1)
    assert not mb.block_ti3_valid(str(tmp_path / "nope.ti3"), 3)
