"""Measure a large test chart in blocks so an interruption loses one block only.

Why: ArgyllCMS ``dispread`` (3.5.0, checked with ``-d dummy -xx``) keeps every
reading in memory and writes the ``.ti3`` file only when *all* patches are done
(or after an explicit "done"). If the application, the process, the computer or
the instrument stops half-way through an eight-hour run, nothing is on disk.
There is no resume option. Measuring the chart as several consecutive
``dispread`` runs, each over a subset of the ``.ti1``, makes every finished block
a durable file; the blocks are merged into the ``.ti3`` the rest of the
application expects.

This module is only the file handling (CGATS text): splitting, merging and
checking. Running the blocks, the journal and the user-facing explanation live
elsewhere. Nothing here touches colour maths.

Each block repeats the white reference patch, because ``dispread`` normalises
readings to the white patch of the chart it measures; the merged file keeps one
white row and the header of the first block. A block is therefore measured
relative to its own white (a small drift correction), at the price of one extra
patch per block and the instrument being re-initialised between blocks.
"""

from __future__ import annotations

import contextlib
import os
import re
from dataclasses import dataclass, field

BEGIN_FMT = "BEGIN_DATA_FORMAT"
END_FMT = "END_DATA_FORMAT"
BEGIN_DATA = "BEGIN_DATA"
END_DATA = "END_DATA"


class CGATSError(ValueError):
    """The text is not a CGATS table this module can handle."""


@dataclass
class Table:
    """A CGATS table: header lines, field names and raw data rows."""

    header: list[str]  # everything before BEGIN_DATA_FORMAT (keywords)
    fields: list[str]
    rows: list[list[str]]
    footer: list[str] = field(default_factory=list)

    def index(self, name: str) -> int:
        """Return the column of ``name`` or raise :class:`CGATSError`."""
        try:
            return self.fields.index(name)
        except ValueError as exc:
            raise CGATSError(f"field {name} missing") from exc


def parse(text: str) -> Table:
    """Parse CGATS text into a :class:`Table` (rows kept as raw tokens)."""
    lines = text.splitlines()
    try:
        f0 = next(i for i, ln in enumerate(lines) if ln.strip() == BEGIN_FMT)
        f1 = next(i for i, ln in enumerate(lines) if ln.strip() == END_FMT)
        d0 = next(i for i, ln in enumerate(lines) if ln.strip() == BEGIN_DATA)
        d1 = next(i for i, ln in enumerate(lines) if ln.strip() == END_DATA)
    except StopIteration as exc:
        raise CGATSError("not a CGATS data table") from exc
    fields = " ".join(lines[f0 + 1 : f1]).split()
    rows = [ln.split() for ln in lines[d0 + 1 : d1] if ln.strip()]
    bad = [r for r in rows if len(r) != len(fields)]
    if bad:
        raise CGATSError("a data row does not match the data format")
    return Table(lines[:f0], fields, rows, lines[d1 + 1 :])


def render(table: Table) -> str:
    """Render a :class:`Table` back to CGATS text (NUMBER_OF_SETS refreshed)."""
    header = []
    seen = False
    for ln in table.header:
        if ln.split()[:1] == ["NUMBER_OF_SETS"]:
            header.append(f"NUMBER_OF_SETS {len(table.rows)}")
            seen = True
        else:
            header.append(ln)
    if not seen:
        header.append(f"NUMBER_OF_SETS {len(table.rows)}")
    out = [*header, BEGIN_FMT, " ".join(table.fields), END_FMT, BEGIN_DATA]
    out += [" ".join(r) for r in table.rows]
    out += [END_DATA, *table.footer]
    return "\n".join(out) + "\n"


def read_table(path: str) -> Table:
    """Read a CGATS file."""
    with open(path, encoding="latin-1") as f:
        return parse(f.read())


def atomic_write(path: str, text: str) -> None:
    """Write ``text`` so a reader never sees a half-written file.

    Written to a sibling temp file, flushed and fsynced, then renamed over the
    target; the previous content survives any failure before the rename.
    """
    tmp = f"{path}.tmp-{os.getpid()}"
    try:
        with open(tmp, "w", encoding="latin-1", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _is_white(row: list[str], rgb_cols: list[int]) -> bool:
    vals = [float(row[c]) for c in rgb_cols]
    return all(v >= 99.99 for v in vals)  # ti1 values are 0..100


def find_white(table: Table) -> int | None:
    """Index of the first white (100/100/100) row, or ``None``."""
    cols = [table.index(n) for n in ("RGB_R", "RGB_G", "RGB_B")]
    for i, r in enumerate(table.rows):
        if _is_white(r, cols):
            return i
    return None


def plan_blocks(count: int, block_size: int) -> int:
    """Number of blocks for ``count`` patches (0/1 means do not split)."""
    if block_size <= 0 or count <= block_size * 1.2:
        return 1
    return -(-count // block_size)


@dataclass
class Block:
    """One block of the plan: the rows (indices into the ti1) it measures."""

    number: int  # 1-based
    base: str  # basename of its ti1/ti3 (no extension)
    row_indices: list[int]


def split_ti1(ti1_path: str, base: str, block_size: int) -> list[Block]:
    """Write one ``.ti1`` per block next to ``ti1_path`` and return the plan.

    Args:
        ti1_path: The full chart.
        base: Prefix for the block basenames (``<base>.blkNNNN``).
        block_size: Target patches per block (excluding the repeated white).

    Raises:
        CGATSError: No white patch to repeat, or the chart is unusable.
    """
    table = read_table(ti1_path)
    white = find_white(table)
    if white is None:
        raise CGATSError("chart has no white patch; cannot split into blocks")
    others = [i for i in range(len(table.rows)) if i != white]
    n_blocks = plan_blocks(len(others), block_size)
    per = -(-len(others) // n_blocks)
    blocks: list[Block] = []
    out_dir = os.path.dirname(ti1_path) or "."
    for k in range(n_blocks):
        idx = others[k * per : (k + 1) * per]
        rows = [table.rows[white]] + [table.rows[i] for i in idx]
        name = os.path.join(out_dir, f"{os.path.basename(base)}.blk{k + 1:04d}")
        atomic_write(
            f"{name}.ti1", render(Table(table.header, table.fields, rows, table.footer))
        )
        blocks.append(Block(k + 1, name, [white, *idx]))
    return blocks


def merge_ti3(parts: list[str], full_ti1: str, out_path: str) -> dict[str, object]:
    """Merge block ``.ti3`` files into one table covering the whole chart.

    One white row is kept (the first block's); every other chart patch must be
    present exactly once. The header (keywords, calibration data) is the first
    block's.

    Returns:
        A report ``{"patches": int, "missing": [...], "duplicates": [...]}``.

    Raises:
        CGATSError: A patch of the chart is missing from the blocks.
    """
    chart = read_table(full_ti1)
    sid = chart.index("SAMPLE_ID")
    white_i = find_white(chart)
    first = read_table(parts[0])
    by_id: dict[str, list[str]] = {}
    dups: list[str] = []
    white_id = chart.rows[white_i][sid] if white_i is not None else None
    for path in parts:
        t = read_table(path)
        if t.fields != first.fields:
            raise CGATSError("blocks were measured with different data formats")
        ti = t.index("SAMPLE_ID")
        for r in t.rows:
            key = r[ti]
            if key == white_id and key in by_id:
                continue  # the repeated reference white
            if key in by_id:
                dups.append(key)
                continue
            by_id[key] = r
    missing = [r[sid] for r in chart.rows if r[sid] not in by_id]
    if missing or dups:
        raise CGATSError(
            f"merge incomplete: {len(missing)} missing, {len(set(dups))} duplicated"
        )
    ordered = [by_id[r[sid]] for r in chart.rows]
    atomic_write(
        out_path, render(Table(first.header, first.fields, ordered, first.footer))
    )
    return {"patches": len(ordered), "missing": [], "duplicates": []}


def block_ti3_valid(path: str, expected_rows: int) -> bool:
    """Whether a block ``.ti3`` exists and holds every row it should."""
    try:
        t = read_table(path)
    except (OSError, CGATSError):
        return False
    return len(t.rows) == expected_rows


_BLOCK_RE = re.compile(r"\.blk(\d{4})$")


def block_number(base: str) -> int | None:
    """Extract ``N`` from a ``<name>.blkNNNN`` basename."""
    m = _BLOCK_RE.search(base)
    return int(m.group(1)) if m else None
