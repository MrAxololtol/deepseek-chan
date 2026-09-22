# Preparing a sprite sheet

Use your own or appropriately licensed artwork. Do not commit reference videos.
The canonical sheet is 2048×2560: four columns and four rows, each cell 512×640.
Cells are read left to right, then top to bottom:

| Row | Column 1 | Column 2 | Column 3 | Column 4 |
| --- | --- | --- | --- | --- |
| 1 | idle | blink | thinking | thinking_hard |
| 2 | working | finished | pat | surprised |
| 3 | error | sleep | idle_smile | idle_sleepy |
| 4 | hoodie_up_idle | hoodie_up_thinking | hoodie_up_sleep | held |

```sh
python scripts/slice_sheet.py --sheet sheet.png --out sprites --report
```

The default `--bg auto` detects exact RGB `#FF00FF` pixels and sets their alpha
to zero. `--bg magenta` explicitly requests the same key; `--bg none` preserves
source colors and alpha. All other pixels retain their original alpha. Near-magenta
pixels are untouched, so prefer lossless PNG input without JPEG fringes.

Custom sheets can specify dimensions and a space-separated name list:

```sh
python scripts/slice_sheet.py --sheet small.png --out small-sprites --cols 2 --rows 1 --cell 32x40 --names idle blink --bg none --report
```

Names must be unique portable filename stems. Fewer names than grid slots are
allowed; trailing unnamed slots are ignored. Extra pixels outside the requested
grid are ignored. Incomplete edge cells, fully transparent/keyed cells, and
solid-color placeholders are skipped, retaining the original positional mapping.
The tool cannot detect malformed anatomy or other artistic defects. Inspect outputs.

Existing named output PNGs cause an error before any files are written. Use a fresh
output directory for every run. An I/O failure may leave earlier outputs from the
same run in place. Reports distinguish produced names from missing names and give
reasons. Exit status is 0 if any sprites were produced (even for partial sheets),
1 if every cell was skipped, and 2 for invalid input or an I/O failure.

No QApplication or display server is required. QImage comes from the project's
existing PyQt6 dependency. Output dimensions equal the requested cell dimensions;
there is no resizing, trimming, or repacking.

Set `sprite_pack` to the sliced output directory to use the [PNG renderer](raster-packs.md).
A readable `idle.png` is required; missing optional states fall back to available poses.
The slicer and runtime share `src/mochi/manifest.py` as their canonical name source.
