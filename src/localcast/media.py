"""Probe and conservative direct-play policy for 2nd-generation Chromecast."""

import json
import math
import subprocess
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path

from .paths import process_options, tool_path

TEXT_SUBTITLES = {"subrip", "srt", "ass", "ssa", "webvtt", "mov_text", "text"}
BITMAP_SUBTITLES = {"hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle"}
LANGUAGES = {
    "por": "Português",
    "pt": "Português",
    "pt-br": "Português (Brasil)",
    "eng": "Inglês",
    "en": "Inglês",
    "spa": "Espanhol",
    "es": "Espanhol",
    "fra": "Francês",
    "fre": "Francês",
    "fr": "Francês",
    "ita": "Italiano",
    "deu": "Alemão",
    "ger": "Alemão",
    "jpn": "Japonês",
    "ja": "Japonês",
}


def language_name(code: str) -> str:
    return LANGUAGES.get(code.lower(), code if code not in {"", "und"} else "Idioma não informado")


@dataclass(frozen=True)
class AudioTrack:
    index: int
    codec: str
    language: str
    title: str
    default: bool
    channels: int
    sample_rate: int
    profile: str = ""

    @property
    def label(self) -> str:
        channel = "estéreo" if self.channels == 2 else f"{self.channels} canais"
        parts = [language_name(self.language), self.title, self.codec.upper(), channel]
        return " • ".join(part for part in parts if part) + (" (padrão)" if self.default else "")


@dataclass(frozen=True)
class SubtitleTrack:
    index: int
    ordinal: int
    codec: str
    language: str
    title: str
    default: bool
    forced: bool

    @property
    def kind(self) -> str:
        if self.codec in TEXT_SUBTITLES:
            return "text"
        if self.codec in BITMAP_SUBTITLES:
            return "bitmap"
        return "unsupported"

    @property
    def label(self) -> str:
        parts = [language_name(self.language), self.title, self.codec.upper()]
        if self.forced:
            parts.append("forçada")
        if self.kind == "unsupported":
            parts.append("formato não suportado")
        return " • ".join(part for part in parts if part)


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    duration: float
    video_codec: str
    profile: str
    level: int
    width: int
    height: int
    fps: float
    pixel_format: str
    video_index: int
    audio_codec: str | None
    audio_profile: str | None
    channels: int
    sample_rate: int
    audio_index: int | None
    hdr: bool
    color_transfer: str
    bit_rate: int
    audio_tracks: tuple[AudioTrack, ...] = ()
    subtitle_tracks: tuple[SubtitleTrack, ...] = ()

    def with_audio(self, index: int | None):
        if index is None:
            return replace(
                self,
                audio_index=None,
                audio_codec=None,
                audio_profile=None,
                channels=0,
                sample_rate=0,
            )
        track = next((track for track in self.audio_tracks if track.index == index), None)
        if not track:
            raise ValueError("Faixa de áudio não pertence a este arquivo.")
        return replace(
            self,
            audio_index=track.index,
            audio_codec=track.codec,
            audio_profile=track.profile,
            channels=track.channels,
            sample_rate=track.sample_rate,
        )

    def subtitle_track(self, index: int | None) -> SubtitleTrack | None:
        if index is None:
            return None
        track = next((track for track in self.subtitle_tracks if track.index == index), None)
        if not track or track.kind == "unsupported":
            raise ValueError("Faixa de legenda ausente ou formato não suportado.")
        return track

    @property
    def direct_reasons(self) -> list[str]:
        reasons = []
        if self.path.suffix.lower() != ".mp4":
            reasons.append("contêiner MKV: usar HLS/MPEG-TS")
        if len(self.audio_tracks) > 1:
            reasons.append("múltiplos áudios: gerar HLS com a faixa escolhida")
        if self.video_codec != "h264":
            reasons.append(f"vídeo {self.video_codec}: converter para H.264")
        if self.pixel_format != "yuv420p":
            reasons.append(f"pixel format {self.pixel_format}: converter para 8 bits yuv420p")
        if self.profile not in {"Baseline", "Constrained Baseline", "Main", "High"}:
            reasons.append(f"perfil H.264 {self.profile} fora da política conservadora")
        if not 0 < self.level <= 41:
            reasons.append(f"nível H.264 {self.level / 10:g}: alvo máximo 4.1")
        if not (0 < self.width <= 1920 and 0 < self.height <= 1080):
            reasons.append("resolução fora do alvo até 1920×1080")
        if not 0 < self.fps <= 30.01:
            reasons.append("taxa de quadros fora do alvo até 30 fps")
        if self.audio_codec is not None and (
            self.audio_codec != "aac"
            or self.audio_profile != "LC"
            or self.channels not in (1, 2)
            or not 0 < self.sample_rate <= 48000
        ):
            reasons.append("áudio: converter para AAC-LC estéreo 48 kHz")
        if self.hdr:
            reasons.append("HDR: aplicar conversão para SDR")
        if self.bit_rate > 12_000_000:
            reasons.append("bitrate acima da política conservadora de 12 Mb/s")
        return reasons

    @property
    def direct_ok(self) -> bool:
        return not self.direct_reasons

    def summary(self) -> str:
        audio = (
            f"{self.audio_codec}, {self.channels} canal(is)" if self.audio_codec else "sem áudio"
        )
        return (
            f"{self.video_codec} {self.width}×{self.height} {self.fps:.2f} fps | {audio} | {self.duration:.1f}s"
            + (" | HDR" if self.hdr else "")
        )


def _number(value, default=0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (ValueError, TypeError):
        return default


def parse_probe(path: Path, raw: dict) -> MediaInfo:
    streams = raw.get("streams", [])
    video = next(
        (
            s
            for s in streams
            if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
        ),
        None,
    )
    if not video:
        raise ValueError("Arquivo sem faixa de vídeo utilizável.")
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    audio = next((s for s in audio_streams if s.get("disposition", {}).get("default")), None)
    audio = audio or (audio_streams[0] if audio_streams else {})
    audio_tracks = tuple(
        AudioTrack(
            index=int(stream["index"]),
            codec=stream.get("codec_name", "unknown"),
            language=stream.get("tags", {}).get("language", "und"),
            title=stream.get("tags", {}).get("title", ""),
            default=bool(stream.get("disposition", {}).get("default")),
            channels=int(_number(stream.get("channels"))),
            sample_rate=int(_number(stream.get("sample_rate"))),
            profile=stream.get("profile", ""),
        )
        for stream in audio_streams
    )
    subtitle_tracks = tuple(
        SubtitleTrack(
            index=int(stream["index"]),
            ordinal=ordinal,
            codec=stream.get("codec_name", "unknown"),
            language=stream.get("tags", {}).get("language", "und"),
            title=stream.get("tags", {}).get("title", ""),
            default=bool(stream.get("disposition", {}).get("default")),
            forced=bool(stream.get("disposition", {}).get("forced")),
        )
        for ordinal, stream in enumerate(s for s in streams if s.get("codec_type") == "subtitle")
    )
    fps = 0.0
    for key in ("avg_frame_rate", "r_frame_rate"):
        try:
            fps = float(Fraction(video.get(key, "0/1")))
        except (ValueError, ZeroDivisionError):
            continue
        if fps > 0:
            break
    fmt = raw.get("format", {})
    duration = _number(fmt.get("duration"), _number(video.get("duration")))
    transfer = video.get("color_transfer", "unknown")
    return MediaInfo(
        path=path,
        duration=duration,
        video_codec=video.get("codec_name", "unknown"),
        profile=video.get("profile", "unknown"),
        level=int(_number(video.get("level"))),
        width=int(_number(video.get("width"))),
        height=int(_number(video.get("height"))),
        fps=fps,
        pixel_format=video.get("pix_fmt", "unknown"),
        video_index=int(video["index"]),
        audio_codec=audio.get("codec_name"),
        audio_profile=audio.get("profile"),
        channels=int(_number(audio.get("channels"))),
        sample_rate=int(_number(audio.get("sample_rate"))),
        audio_index=int(audio["index"]) if audio else None,
        hdr=transfer in {"smpte2084", "arib-std-b67"},
        color_transfer=transfer,
        bit_rate=int(_number(fmt.get("bit_rate"))),
        audio_tracks=audio_tracks,
        subtitle_tracks=subtitle_tracks,
    )


def probe(path: Path, ffprobe: str | None = None) -> MediaInfo:
    path = path.expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in {".mp4", ".mkv"}:
        raise ValueError("Selecione um arquivo MP4 ou MKV.")
    command = [
        ffprobe or tool_path("ffprobe"),
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(
            command, check=False, capture_output=True, timeout=45, **process_options()
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("ffprobe excedeu 45 segundos; confira o arquivo e o disco.") from exc
    if result.returncode:
        raise RuntimeError("ffprobe: " + result.stderr.decode("utf-8", errors="replace")[-2000:])
    return parse_probe(path, json.loads(result.stdout))
