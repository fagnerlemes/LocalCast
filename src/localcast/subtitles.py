"""Embedded captions rendered into video; no receiver subtitle codec assumptions."""

from .media import MediaInfo, SubtitleTrack


def escape_filter_filename(filename: str) -> str:
    # FFmpeg parses option values, then the filter graph. Escape both layers; no shell.
    value = filename.replace("\\", "/")
    for character in ("\\", "'", ":"):
        value = value.replace(character, "\\" + character)
    for character in ("\\", "'", "[", "]", ",", ";"):
        value = value.replace(character, "\\" + character)
    return value


def text_filter(info: MediaInfo, track: SubtitleTrack, base: str, offset: float) -> str:
    if track.kind != "text":
        raise ValueError("Legenda selecionada não é texto.")
    filename = escape_filter_filename(str(info.path))
    # Input -ss resets video timestamps; libass reads captions in the original file timeline.
    return (
        f"{base},setpts=PTS+{offset:.6f}/TB,"
        f"subtitles=filename={filename}:si={track.ordinal},setpts=PTS-STARTPTS"
    )


def bitmap_graph(info: MediaInfo, track: SubtitleTrack, base: str) -> str:
    if track.kind != "bitmap":
        raise ValueError("Legenda selecionada não é imagem.")
    # Decoder sub2video supplies transparent frames when a PGS/VobSub cue clears.
    return (
        f"[0:{info.video_index}][0:{track.index}]overlay=eof_action=pass:repeatlast=0[captioned];"
        f"[captioned]{base}[vout]"
    )
