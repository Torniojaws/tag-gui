"""Shared fixtures. Audio files are synthesised so the suite needs no binary test data."""

import os
import struct
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


def write_aiff(path: Path, seconds: float = 3.0) -> Path:
    """An AIFF with only its COMM chunk; 44100 Hz as an 80-bit extended float."""
    rate = b"\x40\x0e" + (SAMPLE_RATE << 16).to_bytes(4, "big") + b"\x00" * 4
    comm = b"COMM" + struct.pack(">IhIh", 18, 2, int(SAMPLE_RATE * seconds), 16) + rate
    path.write_bytes(b"FORM" + struct.pack(">I", 4 + len(comm)) + b"AIFF" + comm)
    return path


def write_wavpack(path: Path, seconds: float = 3.0) -> Path:
    """One WavPack block header: 16-bit stereo, sample rate index 9 (44100 Hz), no audio."""
    samples = int(SAMPLE_RATE * seconds)
    flags = 0x1 | (9 << 23)
    header = struct.pack("<IHBBIIIII", 24, 0x410, 0, 0, samples, 0, samples, flags, 0)
    path.write_bytes(b"wvpk" + header)
    return path


def _box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I", 8 + len(payload)) + kind + payload


def write_m4a(path: Path, seconds: float = 3.0) -> Path:
    """An MP4 with no tracks; mutagen falls back to the movie header for the length."""
    mvhd = _box(b"mvhd", b"\x00" * 12 + struct.pack(">II", 1000, int(seconds * 1000)) + b"\x00" * 80)
    path.write_bytes(_box(b"ftyp", b"M4A \x00\x00\x00\x00M4A isom") + _box(b"moov", mvhd))
    return path


@pytest.fixture
def flac(tmp_path: Path) -> Path:
    return write_flac(tmp_path / "song.flac")


@pytest.fixture
def mp3(tmp_path: Path) -> Path:
    return write_mp3(tmp_path / "song.mp3")


@pytest.fixture
def m4a(tmp_path: Path) -> Path:
    return write_m4a(tmp_path / "song.m4a")


@pytest.fixture
def wavpack(tmp_path: Path) -> Path:
    return write_wavpack(tmp_path / "song.wv")


_WRITERS = {
    "flac": write_flac,
    "mp3": write_mp3,
    "m4a": write_m4a,
    "wv": write_wavpack,
    "aiff": write_aiff,
}


@pytest.fixture(params=list(_WRITERS))
def track(request, tmp_path: Path) -> Path:
    """Every tag test runs against each tag format: Vorbis, ID3, MP4, APEv2 and ID3 in AIFF."""
    return _WRITERS[request.param](tmp_path / f"song.{request.param}")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
