"""Regenerate assets/app.ico from the live QPainter mark.

The mark is drawn in code (app/ui/components.py), so the .ico must be rebuilt
whenever the drawing changes. Each size is rendered on its own instead of being
downscaled from 256px, which is what keeps the 16px entry readable.

Usage:  python tools/build_app_icon.py
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from app.ui.components import logo  # noqa: E402

SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
ASSETS = ROOT / "assets"


def png_bytes(size: int) -> bytes:
    """Render the mark for one icon size and hand back encoded PNG data.

    logo() paints at 2x for the screen; the ICO entry must be exactly `size`
    pixels, so the supersampled image is folded back down.
    """
    image = logo(size).toImage()
    image = image.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    buffer = QBuffer()
    buffer.open(QBuffer.ReadWrite)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def write_ico(path: Path, images: list[tuple[int, bytes]]) -> None:
    """Write a PNG-compressed ICO (supported by Windows Vista and newer)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    directory = b""
    payload = b""
    for size, data in images:
        edge = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", edge, edge, 0, 0, 1, 32, len(data), offset + len(payload))
        payload += data
    path.write_bytes(header + directory + payload)


def main(app: QGuiApplication) -> int:
    images = [(size, png_bytes(size)) for size in SIZES]
    write_ico(ASSETS / "app.ico", images)
    (ASSETS / "icon-256.png").write_bytes(png_bytes(256))
    print(f"wrote assets/app.ico ({', '.join(str(s) for s in SIZES)})")
    return 0


if __name__ == "__main__":
    application = QGuiApplication(sys.argv)
    status = main(application)
    sys.stdout.flush()
    # Qt tears down its platform plugin after the interpreter has started
    # finalising, which faults on the offscreen backend; leave cleanly instead.
    os._exit(status)
