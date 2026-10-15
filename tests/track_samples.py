"""Synthetic multi-track MKV and tiny PGS bitmap; no external media."""

import struct
import subprocess
from pathlib import Path

from localcast.paths import process_options


def pgs_sample(path: Path):
    packets = bytearray()

    def segment(time, kind, payload):
        pts = round(time * 90000)
        packets.extend(b"PG" + struct.pack(">IIBH", pts, pts, kind, len(payload)) + payload)

    for number, start in enumerate((2, 7)):
        # PGS canvas, composition, palette and a 160×20 white rectangle as caption bitmap.
        pcs = struct.pack(">HHBHBBBB", 640, 360, 0x10, number * 2, 0x80, 0, 0, 1)
        pcs += struct.pack(">HBBHH", 0, 0, 0, 240, 310)
        segment(start, 0x16, pcs)
        segment(start, 0x17, b"\x01\x00" + struct.pack(">HHHH", 240, 310, 160, 20))
        segment(start, 0x14, bytes([0, 0, 0, 0, 128, 128, 0, 1, 235, 128, 128, 255]))
        rle = (b"\x01" * 160 + b"\x00\x00") * 20
        ods = (
            b"\x00\x00\x00\xc0"
            + (len(rle) + 4).to_bytes(3, "big")
            + struct.pack(">HH", 160, 20)
            + rle
        )
        segment(start, 0x15, ods)
        segment(start, 0x80, b"")
        clear = struct.pack(">HHBHBBBB", 640, 360, 0x10, number * 2 + 1, 0, 0, 0, 0)
        segment(start + 2, 0x16, clear)
        segment(start + 2, 0x80, b"")
    path.write_bytes(packets)


def make_track_sample(ffmpeg: str, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    srt = directory / "por.srt"
    srt.write_text(
        "1\n00:00:02,000 --> 00:00:04,000\nPORTUGUÊS TESTE\n\n2\n00:00:07,000 --> 00:00:09,000\nLEGENDA APÓS SEEK\n",
        encoding="utf-8",
    )
    ass = directory / "eng.ass"
    ass.write_text(
        """[Script Info]
ScriptType: v4.00+
PlayResX: 640
PlayResY: 360
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,28,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,20,20,24,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:02.00,0:00:04.00,Default,,0,0,0,,ENGLISH TEST
Dialogue: 0,0:00:07.00,0:00:09.00,Default,,0,0,0,,AFTER SEEK
""",
        encoding="utf-8",
    )
    sup = directory / "bitmap.sup"
    pgs_sample(sup)
    movie = directory / "filme [áudio]'demo,2.mkv"
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-copyts",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:size=640x360:rate=24",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=220:sample_rate=48000",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880:sample_rate=48000",
        "-i",
        str(srt),
        "-i",
        str(ass),
        "-i",
        str(sup),
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-map",
        "2:a",
        "-map",
        "3:s",
        "-map",
        "4:s",
        "-map",
        "5:s",
        "-t",
        "12",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "aac",
        "-ac",
        "2",
        "-c:s",
        "copy",
        "-metadata:s:a:0",
        "language=por",
        "-metadata:s:a:0",
        "title=Português 220 Hz",
        "-metadata:s:a:1",
        "language=eng",
        "-metadata:s:a:1",
        "title=English 880 Hz",
        "-disposition:a:0",
        "default",
        "-disposition:a:1",
        "0",
        "-metadata:s:s:0",
        "language=por",
        "-metadata:s:s:1",
        "language=eng",
        "-metadata:s:s:2",
        "title=PGS bitmap",
        "-disposition:s:0",
        "0",
        "-disposition:s:1",
        "0",
        "-disposition:s:2",
        "0",
        str(movie),
    ]
    subprocess.run(command, capture_output=True, check=True, timeout=60, **process_options())
    return movie
