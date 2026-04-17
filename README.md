# Parametric Video Clip To Gif


Convert a video clip into a GIF with either a simple desktop UI or a command-line script.

## Requirements

- Python 3
- `ffmpeg` on your `PATH`
- `ffprobe` on your `PATH` for automatic source-resolution detection in the GUI

## Project Layout

```text
media/
  input/   # put source videos here
  output/  # generated GIFs are created here by default
```

## Files

- `video_to_gif_gui.py`: Tkinter desktop UI
- `video_to_gif.py`: command-line script and shared conversion logic
- `open_gui.bat`: Windows launcher for the GUI
- `open_gui.sh`: macOS/Linux launcher for the GUI

## GUI Usage

Run:

```powershell
python video_to_gif_gui.py
```

Or use the launcher script for your platform:

```powershell
open_gui.bat
```

```bash
./open_gui.sh
```

Defaults:

- the GUI looks for videos in `media/input`
- the suggested output location is `media/output`
- supported input formats include `.mp4`, `.mov`/`.MOV`, `.avi`, `.mkv`, `.webm`, `.wmv`, and `.m4v`

What the GUI lets you set:

- input video
- output GIF path
- GIF frame rate
- video playback rate
- start time
- clip length
- output width and height
- loop count

Notes:

- Width and height preserve the original video aspect ratio.
- If you set both width and height, the GIF is scaled to fit inside that box.
- Start time and length accept seconds like `2.5` or time values like `00:00:02.500`.
- On macOS/Linux, you may need to run `chmod +x open_gui.sh` once before using it.

## Script Usage

Basic format:

```powershell
python video_to_gif.py INPUT_VIDEO OUTPUT_GIF [options]
```

Defaults:

- if `INPUT_VIDEO` is just a file name, it is loaded from `media/input`
- if `OUTPUT_GIF` is just a file name, it is created in `media/output`
- supported input formats include `.mp4`, `.mov`/`.MOV`, `.avi`, `.mkv`, `.webm`, `.wmv`, and `.m4v`

Options:

- `--gif-fps`: GIF frames per second
- `--playback-rate`: playback speed, where `2.0` is faster and `0.5` is slower
- `--start`: clip start time
- `--length`: clip length
- `--width`: output width
- `--height`: output height
- `--loop`: GIF loop count, where `0` means infinite loop
- `--overwrite`: overwrite the output file if it already exists

Example:

```powershell
python video_to_gif.py "sample_video_Shravan1991_pixabay.mp4" "output.gif" --start 1 --length 3 --gif-fps 12 --playback-rate 1.25 --width 480 --height 480 --overwrite
```

That command reads from `media/input/sample_video_Shravan1991_pixabay.mp4` and writes to `media/output/output.gif`.

## Help

To see the built-in command help:

```powershell
python video_to_gif.py --help
```
