"""Writes tag-gui.ico, the icon PyInstaller embeds into the executable."""

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from tag_gui.constants import ICON_SIZES  # noqa: E402
from tag_gui.ui.icons import note_pixmap  # noqa: E402

OUTPUT = Path(__file__).with_name("tag-gui.ico")


def png_bytes(size: int) -> bytes:
    buffer = QBuffer()
    buffer.open(QBuffer.WriteOnly)
    note_pixmap(size).save(buffer, "PNG")
    return bytes(buffer.data())


def main() -> int:
    QApplication(sys.argv)
    images = [png_bytes(size) for size in ICON_SIZES]

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries = b""
    for size, data in zip(ICON_SIZES, images):
        entries += struct.pack(
            "<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset
        )
        offset += len(data)

    OUTPUT.write_bytes(header + entries + b"".join(images))
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
