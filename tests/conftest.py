"""Shared fixtures. Audio files are synthesised so the suite needs no binary test data."""

import os
from pathlib import Path

import pytest

# Must be set before the first QApplication so the window tests need no display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SAMPLE_RATE = 44100

# MPEG-1 Layer III, 128 kbps, 44.1 kHz stereo. 417 bytes covers 26.1 ms of silence.
MP3_FRAME = b"\xff\xfb\x90\x00" + b"\x00" * 413


def _streaminfo(sample_rate: int, channels: int, bits: int, samples: int) -> bytes:
    packed = (sample_rate << 44) | ((channels - 1) << 41) | ((bits - 1) << 36) | samples
    return (
        b"\x10\x00" * 2  # min and max block size
        + b"\x00\x00\x00" * 2  # min and max frame size, left unknown
        + packed.to_bytes(8, "big")
        + b"\x00" * 16  # md5 of the (absent) audio data
    )


def write_flac(path: Path, seconds: float = 3.0) -> Path:
    """A header-only FLAC; mutagen reads and writes its tags without any audio frames."""
    info = _streaminfo(SAMPLE_RATE, 2, 16, int(SAMPLE_RATE * seconds))
    path.write_bytes(b"fLaC" + b"\x80" + len(info).to_bytes(3, "big") + info)
    return path


def write_mp3(path: Path, frames: int = 40) -> Path:
    path.write_bytes(MP3_FRAME * frames)
    return path


@pytest.fixture
def flac(tmp_path: Path) -> Path:
    return write_flac(tmp_path / "song.flac")


@pytest.fixture
def mp3(tmp_path: Path) -> Path:
    return write_mp3(tmp_path / "song.mp3")


@pytest.fixture(params=["flac", "mp3"])
def track(request, flac: Path, mp3: Path) -> Path:
    """Every custom tag test runs against both the Vorbis and the ID3 code path."""
    return {"flac": flac, "mp3": mp3}[request.param]


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
