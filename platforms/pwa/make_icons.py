"""Draw the app icon into ``web/``.

    python platforms/pwa/make_icons.py

Writes ``icon.svg`` (what browsers prefer) plus the two PNG sizes that only
exist because some places still refuse an SVG — iOS's home-screen icon most of
all, which falls back to a screenshot of the page without one.

The mark is the same one the app wears in its top-left corner: a pen over the
line you write on, white on the accent colour.

No Pillow, no cairosvg. Adding an image library to a project whose only real
dependency is a web server, in order to draw one icon twice a year, is a bad
trade — so the few hundred lines of PNG that are actually needed are written
out by hand. ``zlib`` is in the standard library and does the compression.

Icons are checked in, so nobody needs to run this to build the app. Run it when
the mark changes.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"

#: Matches --accent in web/styles.css and .brand .mark.
ACCENT = (0xA8, 0x54, 0x2F)
GLYPH = (0xFF, 0xFF, 0xFF)

#: Anti-aliasing. Each output pixel is decided by SS x SS samples.
SS = 4


# --------------------------------------------------------------------------
# The mark, in a 100 x 100 box
# --------------------------------------------------------------------------

def _mark() -> list[list[tuple[float, float]]]:
    """The pen and its line, as filled polygons."""
    # Pen body: a bar running down-left at 45 degrees.
    ax, ay = 73.0, 21.0   # top end
    bx, by = 39.0, 55.0   # where the tip starts
    half = 8.5            # half the bar's width, measured across it
    # Unit vector across the bar. The bar runs along (-1, 1)/sqrt2, so across
    # it is (1, 1)/sqrt2.
    px, py = 0.70710678 * half, 0.70710678 * half

    body = [
        (ax - px, ay - py),
        (ax + px, ay + py),
        (bx + px, by + py),
        (bx - px, by - py),
    ]
    # Nib: the bar narrowing to a point.
    tip = [
        (bx - px, by - py),
        (bx + px, by + py),
        (25.0, 69.0),
    ]
    # The line being written on, with its ends cut at an angle so it reads as
    # drawn rather than as a rectangle someone forgot to round.
    rule = [
        (25.0, 79.0),
        (77.0, 79.0),
        (75.0, 86.0),
        (23.0, 86.0),
    ]
    return [body, tip, rule]


def _coverage(size: int) -> list[list[int]]:
    """Rasterise the mark at ``size`` px, returning 0..SS*SS per pixel."""
    polys = [
        [(x / 100.0 * size, y / 100.0 * size) for x, y in poly] for poly in _mark()
    ]
    acc = [[0] * size for _ in range(size)]
    width = size * SS

    for sy in range(size * SS):
        y = (sy + 0.5) / SS
        row = bytearray(width)
        for poly in polys:
            # Even-odd scanline fill: collect where this row crosses the
            # polygon's edges, then fill between alternate pairs.
            xs: list[float] = []
            n = len(poly)
            for i in range(n):
                x0, y0 = poly[i]
                x1, y1 = poly[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                start = max(0, int(round(xs[i] * SS)))
                end = min(width, int(round(xs[i + 1] * SS)))
                for sx in range(start, end):
                    row[sx] = 1
        out_row = acc[sy // SS]
        for ox in range(size):
            base = ox * SS
            out_row[ox] += sum(row[base : base + SS])
    return acc


def _png(size: int) -> bytes:
    """A full-bleed RGB PNG. No alpha: iOS composites a transparent icon onto
    white, which would leave the mark floating on a white square."""
    acc = _coverage(size)
    full = SS * SS
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # per-scanline filter: none
        for x in range(size):
            a = acc[y][x] / full
            for channel in range(3):
                value = ACCENT[channel] * (1 - a) + GLYPH[channel] * a
                raw.append(int(round(value)))

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def _svg() -> str:
    hexes = "#%02x%02x%02x" % ACCENT
    paths = []
    for poly in _mark():
        points = " ".join(f"{x:.2f},{y:.2f}" for x, y in poly)
        paths.append(f'  <polygon points="{points}" fill="#ffffff"/>')
    body = "\n".join(paths)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
        'width="100" height="100" role="img" aria-label="每日日記">\n'
        f'  <rect width="100" height="100" fill="{hexes}"/>\n'
        f"{body}\n"
        "</svg>\n"
    )


def main() -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "icon.svg").write_text(_svg(), encoding="utf-8")
    print(f"wrote {(WEB / 'icon.svg').relative_to(ROOT)}")
    for size in (180, 512):
        path = WEB / f"icon-{size}.png"
        path.write_bytes(_png(size))
        print(f"wrote {path.relative_to(ROOT)}  ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
