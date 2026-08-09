import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import app  # noqa: E402

TAG = "Yömusa"
tmp = Path(tempfile.mkdtemp())


def make_flac(path: Path):
    bits = ""
    bits += format(4096, "016b")
    bits += format(4096, "016b")
    bits += format(0, "024b")
    bits += format(0, "024b")
    bits += format(44100, "020b")
    bits += format(1, "03b")
    bits += format(15, "05b")
    bits += format(44100, "036b")
    streaminfo = int(bits, 2).to_bytes(18, "big") + b"\x00" * 16
    path.write_bytes(b"fLaC" + bytes([0x80]) + len(streaminfo).to_bytes(3, "big") + streaminfo)


def make_mp3(path: Path):
    path.write_bytes((b"\xff\xfb\x90\x00" + b"\x00" * 413) * 20)


print("keys:", app.ascii_tag_key(TAG), "|", app.ascii_tag_key("Ääni Päällä"), "|", app.ascii_tag_key("日本"))
print("parse:", app.parse_custom_tags("Yömusa, Yomusa, Rock"))

for name, maker in (("t.flac", make_flac), ("t.mp3", make_mp3)):
    p = tmp / name
    maker(p)
    print("---", name)
    print("before:", app.custom_tag_checked(p, TAG))
    app.set_custom_tag(p, TAG, True)
    print("after set:", app.custom_tag_checked(p, TAG))
    raw = app.load_raw_tags(p)
    print("raw keys:", list(raw.tags.keys()) if name.endswith("flac") else [f.desc for f in raw.tags.getall("TXXX")])
    print("ascii lookup:", app.custom_tag_checked(p, "YOMUSA"))
    app.set_custom_tag(p, TAG, False)
    print("after unset:", app.custom_tag_checked(p, TAG))
