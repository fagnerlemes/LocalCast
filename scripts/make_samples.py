"""Small synthetic files; no copyrighted media or Internet downloads."""

import argparse
import subprocess
from pathlib import Path

from localcast.paths import process_options, tool_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("samples"))
    parser.add_argument(
        "--include-4k", action="store_true", help="Also generate 12 seconds of HEVC 4K + EAC3 5.1"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    ffmpeg = tool_path("ffmpeg")
    common = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-f", "lavfi"]
    commands = [
        common
        + [
            "-i",
            "testsrc2=size=1280x720:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000",
            "-t",
            "20",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-profile:v",
            "high",
            "-level:v",
            "4.1",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(args.output / "teste-h264-aac.mp4"),
        ]
    ]
    if args.include_4k:
        commands.append(
            common
            + [
                "-i",
                "testsrc2=size=3840x2160:rate=24",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=5.1:sample_rate=48000",
                "-t",
                "12",
                "-c:v",
                "libx265",
                "-preset",
                "ultrafast",
                "-x265-params",
                "log-level=error",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "eac3",
                "-b:a",
                "640k",
                str(args.output / "teste-hevc4k-eac3.mkv"),
            ]
        )
    for command in commands:
        subprocess.run(command, check=True, **process_options())
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-i",
            str(args.output / "teste-h264-aac.mp4"),
            "-c",
            "copy",
            str(args.output / "teste-h264-aac.mkv"),
        ],
        check=True,
        **process_options(),
    )
    print("Amostras criadas em", args.output.resolve())


if __name__ == "__main__":
    main()
