"""Conservative Cast output with hardware candidates verified by actual HLS startup."""

import logging
import subprocess
from dataclasses import dataclass
from functools import lru_cache

from .paths import process_options

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class EncoderPlan:
    codec: str = "libx264"
    label: str = "CPU x264"
    cuda_decode: bool = False
    cuda_scale: bool = False


CPU = EncoderPlan()


@lru_cache(maxsize=8)
def available_encoders(ffmpeg: str) -> frozenset[str]:
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"], capture_output=True, timeout=10,
            text=True, encoding="utf-8", errors="replace", **process_options(),
        )
        return frozenset(
            parts[1] for line in result.stdout.splitlines()
            if len(parts := line.split()) >= 2 and len(parts[0]) == 6
        )
    except (OSError, subprocess.SubprocessError):
        LOG.warning("Não foi possível listar encoders; usando CPU.")
        return frozenset()


def encoder_plans(ffmpeg, mode, info, subtitle=None):
    if mode not in {"auto", "cpu"}:
        raise ValueError("Processamento deve ser automático ou CPU.")
    if mode == "cpu":
        return [CPU]
    available = available_encoders(ffmpeg)
    plans = []
    if "h264_nvenc" in available:
        cuda_input = info.video_codec in {"h264", "hevc", "vp9", "av1"} and info.pixel_format in {
            "yuv420p", "yuv420p10le", "nv12", "p010le",
        }
        if cuda_input and not (subtitle and subtitle.kind == "bitmap"):
            gpu_scale = not info.hdr and subtitle is None
            plans.append(EncoderPlan(
                "h264_nvenc", "NVIDIA NVENC + CUDA" if gpu_scale
                else "NVIDIA NVENC + CUDA / filtros CPU", True, gpu_scale,
            ))
        plans.append(EncoderPlan("h264_nvenc", "NVIDIA NVENC / filtros CPU"))
    if "h264_qsv" in available:
        plans.append(EncoderPlan("h264_qsv", "Intel Quick Sync / filtros CPU"))
    if "h264_amf" in available:
        plans.append(EncoderPlan("h264_amf", "AMD AMF / filtros CPU"))
    return plans + [CPU]


def encoding_options(plan):
    if plan.codec == "h264_nvenc":
        return ["-c:v", plan.codec, "-preset", "p4", "-rc", "vbr", "-cq", "22",
                "-b:v", "4M", "-forced-idr", "1", "-bf", "2"]
    if plan.codec == "h264_qsv":
        return ["-c:v", plan.codec, "-preset", "veryfast", "-b:v", "4M",
                "-forced_idr", "1", "-bf", "2"]
    if plan.codec == "h264_amf":
        return ["-c:v", plan.codec, "-quality", "balanced", "-rc", "vbr_peak", "-b:v", "4M"]
    if plan.codec != "libx264":
        return ["-c:v", plan.codec]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-refs", "3", "-sc_threshold", "0"]
