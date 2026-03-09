#!/usr/bin/env python3
"""Generate an animated GIF from a video clip using ffmpeg."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


VALID_LOG_LEVELS = {"quiet", "panic", "fatal", "error", "warning", "info", "verbose"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".m4v"}
PROJECT_ROOT = Path(__file__).resolve().parent
MEDIA_DIR = PROJECT_ROOT / "media"
MEDIA_INPUT_DIR = MEDIA_DIR / "input"
MEDIA_OUTPUT_DIR = MEDIA_DIR / "output"


class GifConversionError(RuntimeError):
    """Raised when the video-to-GIF conversion cannot be completed."""


def ensure_media_directories() -> None:
    MEDIA_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def resolve_input_path(input_path: str | Path) -> Path:
    raw_path = Path(input_path).expanduser()
    if raw_path.is_absolute():
        return raw_path.resolve()

    cwd_candidate = (Path.cwd() / raw_path).resolve()
    project_candidate = (PROJECT_ROOT / raw_path).resolve()

    candidates: list[Path] = []
    if raw_path.parent == Path("."):
        candidates.append((MEDIA_INPUT_DIR / raw_path.name).resolve())
    candidates.extend([cwd_candidate, project_candidate])

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return candidate

    return candidates[0] if raw_path.parent == Path(".") else cwd_candidate


def resolve_output_path(output_path: str | Path) -> Path:
    raw_path = Path(output_path).expanduser()
    if raw_path.is_absolute():
        return raw_path.resolve()

    if raw_path.parent == Path("."):
        return (MEDIA_OUTPUT_DIR / raw_path.name).resolve()

    return (Path.cwd() / raw_path).resolve()


def parse_time_value(value: str | float | int) -> float:
    """Parse seconds or HH:MM:SS(.ms) into total seconds."""
    if isinstance(value, (int, float)):
        seconds = float(value)
    else:
        text = value.strip()
        if not text:
            raise ValueError("time value cannot be empty")

        try:
            seconds = float(text)
        except ValueError:
            parts = text.split(":")
            if len(parts) > 3:
                raise ValueError(
                    f"invalid time value '{value}'. Use seconds or HH:MM:SS(.ms)."
                ) from None

            try:
                numbers = [float(part) for part in parts]
            except ValueError as exc:
                raise ValueError(
                    f"invalid time value '{value}'. Use seconds or HH:MM:SS(.ms)."
                ) from exc

            seconds = 0.0
            for number in numbers:
                seconds = seconds * 60 + number

    if seconds < 0:
        raise ValueError("time values must be 0 or greater")

    return seconds


def parse_positive_float(value: str | float | int, label: str = "value") -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc

    if number <= 0:
        raise ValueError(f"{label} must be greater than 0")

    return number


def parse_positive_int(value: str | int, label: str = "value") -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc

    if number <= 0:
        raise ValueError(f"{label} must be greater than 0")

    return number


def argparse_time(value: str) -> float:
    try:
        return parse_time_value(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def argparse_positive_float(value: str) -> float:
    try:
        return parse_positive_float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def argparse_positive_int(value: str) -> int:
    try:
        return parse_positive_int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def format_seconds(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def get_ffmpeg_path() -> str:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise GifConversionError("ffmpeg was not found on PATH. Install ffmpeg and try again.")
    return ffmpeg_path


def get_ffprobe_path() -> str | None:
    return shutil.which("ffprobe")


def probe_video_dimensions(input_path: str | Path) -> tuple[int, int] | None:
    ffprobe_path = get_ffprobe_path()
    if ffprobe_path is None:
        return None

    ensure_media_directories()
    video_path = resolve_input_path(input_path)
    if not video_path.is_file():
        return None

    command = [
        ffprobe_path,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=p=0:s=x",
        str(video_path),
    ]

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    text = result.stdout.strip()
    if not text or "x" not in text:
        return None

    width_text, height_text = text.split("x", 1)
    try:
        return int(width_text), int(height_text)
    except ValueError:
        return None


def build_filter(
    gif_fps: float,
    playback_rate: float,
    width: int | None,
    height: int | None,
) -> str:
    playback_factor = 1.0 / playback_rate
    filters = [
        f"setpts={playback_factor:.10g}*PTS",
        f"fps={gif_fps:.10g}",
    ]

    if width is not None and height is not None:
        filters.append(
            f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos"
        )
    elif width is not None:
        filters.append(f"scale={width}:-1:flags=lanczos")
    elif height is not None:
        filters.append(f"scale=-1:{height}:flags=lanczos")

    chain = ",".join(filters)
    return (
        f"{chain},split[s0][s1];"
        "[s0]palettegen=stats_mode=full[p];"
        "[s1][p]paletteuse=dither=sierra2_4a"
    )


def build_command(
    *,
    ffmpeg_path: str,
    input_path: Path,
    output_path: Path,
    gif_fps: float,
    playback_rate: float,
    start: float,
    length: float | None,
    width: int | None,
    height: int | None,
    loop: int,
    overwrite: bool,
    log_level: str,
) -> list[str]:
    command = [ffmpeg_path]
    command.append("-y" if overwrite else "-n")
    command.extend(["-hide_banner", "-loglevel", log_level])

    if start > 0:
        command.extend(["-ss", format_seconds(start)])

    if length is not None:
        command.extend(["-t", format_seconds(length)])

    command.extend(
        [
            "-i",
            str(input_path),
            "-vf",
            build_filter(gif_fps, playback_rate, width, height),
            "-loop",
            str(loop),
            str(output_path),
        ]
    )
    return command


def convert_video_to_gif(
    input_path: str | Path,
    output_path: str | Path,
    *,
    gif_fps: float = 10.0,
    playback_rate: float = 1.0,
    start: float = 0.0,
    length: float | None = None,
    width: int | None = None,
    height: int | None = None,
    loop: int = 0,
    overwrite: bool = False,
    log_level: str = "error",
) -> Path:
    ensure_media_directories()
    ffmpeg_path = get_ffmpeg_path()

    source_path = resolve_input_path(input_path)
    target_path = resolve_output_path(output_path)

    if not source_path.is_file():
        raise GifConversionError(f"Input video not found: {source_path}")

    if target_path.suffix.lower() != ".gif":
        raise GifConversionError("Output file must use the .gif extension.")

    gif_fps = parse_positive_float(gif_fps, "GIF frame rate")
    playback_rate = parse_positive_float(playback_rate, "Playback rate")
    start = parse_time_value(start)

    if length is not None:
        length = parse_time_value(length)
        if length <= 0:
            raise GifConversionError("Clip length must be greater than 0.")

    if width is not None:
        width = parse_positive_int(width, "Width")

    if height is not None:
        height = parse_positive_int(height, "Height")

    try:
        loop = int(loop)
    except (TypeError, ValueError) as exc:
        raise GifConversionError("Loop count must be an integer.") from exc

    if loop < 0:
        raise GifConversionError("Loop count must be 0 or greater.")

    if log_level not in VALID_LOG_LEVELS:
        raise GifConversionError(
            f"Invalid log level '{log_level}'. Choose one of: {', '.join(sorted(VALID_LOG_LEVELS))}."
        )

    target_path.parent.mkdir(parents=True, exist_ok=True)

    command = build_command(
        ffmpeg_path=ffmpeg_path,
        input_path=source_path,
        output_path=target_path,
        gif_fps=gif_fps,
        playback_rate=playback_rate,
        start=start,
        length=length,
        width=width,
        height=height,
        loop=loop,
        overwrite=overwrite,
        log_level=log_level,
    )

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise GifConversionError(f"ffmpeg failed with exit code {exc.returncode}.") from exc
    except OSError as exc:
        raise GifConversionError(str(exc)) from exc

    return target_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert part of a video into a GIF with adjustable GIF FPS, "
            "playback rate, start time, clip length, and output size. "
            "Plain file names default to media/input for videos and media/output for GIFs."
        )
    )
    parser.add_argument(
        "input",
        type=Path,
        help="input video path, or just a file name from media/input",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="output GIF path, or just a file name to create in media/output",
    )
    parser.add_argument(
        "--gif-fps",
        type=argparse_positive_float,
        default=10.0,
        help="GIF frame rate in frames per second (default: %(default)s)",
    )
    parser.add_argument(
        "--playback-rate",
        type=argparse_positive_float,
        default=1.0,
        help=(
            "video playback multiplier where 2.0 is twice as fast and 0.5 is half speed "
            "(default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--start",
        type=argparse_time,
        default=0.0,
        help="start time in seconds or HH:MM:SS(.ms) (default: %(default)s)",
    )
    parser.add_argument(
        "--length",
        type=argparse_time,
        help="clip length in seconds or HH:MM:SS(.ms); defaults to the rest of the video",
    )
    parser.add_argument(
        "--width",
        type=argparse_positive_int,
        help="optional output width in pixels; aspect ratio is preserved",
    )
    parser.add_argument(
        "--height",
        type=argparse_positive_int,
        help="optional output height in pixels; aspect ratio is preserved",
    )
    parser.add_argument(
        "--loop",
        type=int,
        default=0,
        help="GIF loop count where 0 means infinite looping (default: %(default)s)",
    )
    parser.add_argument(
        "--log-level",
        default="error",
        choices=sorted(VALID_LOG_LEVELS),
        help="ffmpeg log level (default: %(default)s)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="overwrite the output file if it already exists",
    )
    args = parser.parse_args()

    if args.loop < 0:
        parser.error("--loop must be 0 or greater")

    return args


def main() -> int:
    args = parse_args()

    try:
        output_path = convert_video_to_gif(
            args.input,
            args.output,
            gif_fps=args.gif_fps,
            playback_rate=args.playback_rate,
            start=args.start,
            length=args.length,
            width=args.width,
            height=args.height,
            loop=args.loop,
            overwrite=args.overwrite,
            log_level=args.log_level,
        )
    except GifConversionError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"GIF created: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
