#!/usr/bin/env python3
"""Simple Tkinter UI for converting videos to GIFs."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from video_to_gif import (
    GifConversionError,
    MEDIA_INPUT_DIR,
    MEDIA_OUTPUT_DIR,
    VIDEO_SUFFIXES,
    convert_video_to_gif,
    ensure_media_directories,
    probe_video_dimensions,
)


VIDEO_PATTERNS = " ".join(f"*{suffix}" for suffix in sorted(VIDEO_SUFFIXES))


class VideoToGifApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Video to GIF")
        self.root.minsize(640, 360)
        self.root.columnconfigure(1, weight=1)

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.gif_fps_var = tk.StringVar(value="10")
        self.playback_rate_var = tk.StringVar(value="1.0")
        self.start_var = tk.StringVar(value="0")
        self.length_var = tk.StringVar()
        self.width_var = tk.StringVar()
        self.height_var = tk.StringVar()
        self.loop_var = tk.StringVar(value="0")
        self.status_var = tk.StringVar(value="Ready.")
        self.source_size_var = tk.StringVar(value="Source resolution: unknown")
        self.overwrite_var = tk.BooleanVar(value=True)
        self.last_auto_output = ""

        self.generate_button: ttk.Button | None = None

        ensure_media_directories()
        self._build_layout()
        self._load_default_video()

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.grid(sticky="nsew")
        container.columnconfigure(1, weight=1)

        row = 0
        self._add_file_row(
            container,
            row,
            "Input Video",
            self.input_var,
            self._browse_input,
        )
        row += 1

        self._add_file_row(
            container,
            row,
            "Output GIF",
            self.output_var,
            self._browse_output,
        )
        row += 1

        ttk.Label(container, textvariable=self.source_size_var).grid(
            row=row, column=1, sticky="w", pady=(0, 10)
        )
        row += 1

        row = self._add_entry_row(container, row, "GIF FPS", self.gif_fps_var)
        row = self._add_entry_row(
            container, row, "Playback Rate", self.playback_rate_var
        )
        row = self._add_entry_row(
            container, row, "Start Time", self.start_var, "seconds or HH:MM:SS"
        )
        row = self._add_entry_row(
            container, row, "Clip Length", self.length_var, "blank = rest of video"
        )

        resolution_frame = ttk.Frame(container)
        resolution_frame.grid(row=row, column=1, sticky="ew", pady=4)
        resolution_frame.columnconfigure(0, weight=1)
        resolution_frame.columnconfigure(2, weight=1)

        ttk.Label(container, text="Resolution").grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=4
        )
        ttk.Entry(resolution_frame, textvariable=self.width_var).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Label(resolution_frame, text="x").grid(row=0, column=1, padx=8)
        ttk.Entry(resolution_frame, textvariable=self.height_var).grid(
            row=0, column=2, sticky="ew"
        )
        ttk.Label(
            container,
            text="Keeps the original aspect ratio. If both are set, the GIF fits inside that box.",
        ).grid(row=row + 1, column=1, sticky="w", pady=(2, 10))
        row += 2

        row = self._add_entry_row(container, row, "Loop Count", self.loop_var)

        ttk.Checkbutton(
            container,
            text="Overwrite existing GIF",
            variable=self.overwrite_var,
        ).grid(row=row, column=1, sticky="w", pady=(2, 10))
        row += 1

        ttk.Separator(container).grid(row=row, column=0, columnspan=3, sticky="ew", pady=8)
        row += 1

        button_row = ttk.Frame(container)
        button_row.grid(row=row, column=0, columnspan=3, sticky="ew")
        button_row.columnconfigure(0, weight=1)

        ttk.Label(button_row, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        self.generate_button = ttk.Button(
            button_row,
            text="Generate GIF",
            command=self._start_conversion,
        )
        self.generate_button.grid(row=0, column=1, sticky="e")

    def _add_file_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        command,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="Browse...", command=command).grid(row=row, column=2, pady=4)

    def _add_entry_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        hint: str | None = None,
    ) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        if hint:
            ttk.Label(parent, text=hint).grid(row=row, column=2, sticky="w", pady=4)
        return row + 1

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a video",
            initialdir=str(MEDIA_INPUT_DIR),
            filetypes=[("Video files", VIDEO_PATTERNS), ("All files", "*.*")],
        )
        if path:
            self.input_var.set(path)
            self._update_from_input_selection()

    def _browse_output(self) -> None:
        input_name = Path(self.input_var.get().strip() or "output").stem
        path = filedialog.asksaveasfilename(
            title="Save GIF as",
            initialdir=str(MEDIA_OUTPUT_DIR),
            initialfile=f"{input_name}.gif",
            defaultextension=".gif",
            filetypes=[("GIF files", "*.gif")],
        )
        if path:
            self.output_var.set(path)
            self.last_auto_output = ""

    def _load_default_video(self) -> None:
        for path in sorted(MEDIA_INPUT_DIR.iterdir()):
            if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES:
                self.input_var.set(str(path.resolve()))
                self._update_from_input_selection()
                break

    def _update_from_input_selection(self) -> None:
        input_path = self.input_var.get().strip()
        if not input_path:
            self.source_size_var.set("Source resolution: unknown")
            return

        source = Path(input_path)
        default_output = (MEDIA_OUTPUT_DIR / f"{source.stem}.gif").resolve()
        current_output = self.output_var.get().strip()
        if not current_output or current_output == self.last_auto_output:
            self.last_auto_output = str(default_output)
            self.output_var.set(self.last_auto_output)

        dimensions = probe_video_dimensions(source)
        if dimensions is None:
            self.source_size_var.set("Source resolution: unknown")
            return

        width, height = dimensions
        self.source_size_var.set(f"Source resolution: {width} x {height}")
        if not self.width_var.get().strip():
            self.width_var.set(str(width))
        if not self.height_var.get().strip():
            self.height_var.set(str(height))

    def _start_conversion(self) -> None:
        input_path = self.input_var.get().strip()
        output_path = self.output_var.get().strip()

        if not input_path:
            messagebox.showerror("Missing input", "Choose an input video first.")
            return

        if not output_path:
            messagebox.showerror("Missing output", "Choose where to save the GIF.")
            return

        options = {
            "input_path": input_path,
            "output_path": output_path,
            "gif_fps": self.gif_fps_var.get().strip() or "10",
            "playback_rate": self.playback_rate_var.get().strip() or "1.0",
            "start": self.start_var.get().strip() or "0",
            "length": self.length_var.get().strip() or None,
            "width": self.width_var.get().strip() or None,
            "height": self.height_var.get().strip() or None,
            "loop": self.loop_var.get().strip() or "0",
            "overwrite": self.overwrite_var.get(),
        }

        self._set_busy(True)
        self.status_var.set("Generating GIF...")
        threading.Thread(
            target=self._run_conversion,
            args=(options,),
            daemon=True,
        ).start()

    def _run_conversion(self, options: dict[str, object]) -> None:
        try:
            result = convert_video_to_gif(
                options["input_path"],
                options["output_path"],
                gif_fps=options["gif_fps"],
                playback_rate=options["playback_rate"],
                start=options["start"],
                length=options["length"],
                width=options["width"],
                height=options["height"],
                loop=options["loop"],
                overwrite=bool(options["overwrite"]),
                log_level="warning",
            )
        except GifConversionError as exc:
            self.root.after(0, lambda: self._finish_conversion(False, str(exc)))
            return
        except Exception as exc:
            self.root.after(0, lambda: self._finish_conversion(False, f"Unexpected error: {exc}"))
            return

        self.root.after(0, lambda: self._finish_conversion(True, f"GIF created: {result}"))

    def _finish_conversion(self, success: bool, message: str) -> None:
        self._set_busy(False)
        self.status_var.set(message)
        if success:
            messagebox.showinfo("Done", message)
        else:
            messagebox.showerror("Conversion failed", message)

    def _set_busy(self, busy: bool) -> None:
        if self.generate_button is not None:
            self.generate_button.configure(state="disabled" if busy else "normal")


def main() -> None:
    root = tk.Tk()
    VideoToGifApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
