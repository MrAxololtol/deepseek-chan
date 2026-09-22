# PNG sprite packs

The pet ships with a bundled PNG character pack under
`src/deepseek_chan/assets/adult/` and uses it by default. Set `sprite_pack` to a
directory of your own sliced PNGs to override it; SVG rendering is the fallback
when no pack is present.

Slice your own sheet, then set the directory in your TOML configuration:

```toml
sprite_pack = "/absolute/path/to/sprites"
outfit = "hoodie"
```

```sh
deepseek-chan run --config my-pet.toml
python -m deepseek_chan.doctor --assets /absolute/path/to/sprites
```

`idle.png` is required. The other canonical poses are optional. Each PNG is a
complete character, not a face layer. Missing or corrupt optional poses fall back
to an available pose and ultimately idle. The doctor reports unreadable files and
lists missing optional poses. PNG dimensions can differ, but consistent 512×640
canvases, placement, and transparent padding give the most stable animation.
Images above 4096 pixels on either edge are rejected before full decoding.

The renderer preserves aspect ratio and alpha, centers the sprite, and reserves
space for the status pill. It keeps the existing speech bubbles, sleep indicators,
and particle effects, using bundled SVG assets for the particles. Hover gaze and
independent hair animation are not possible with flattened PNGs. PNG palettes are
baked in, so TOML palette changes affect UI/effects, not the character's colors.

Selection priority:

- While dragging: `held`, then the normal state candidates.
- Hood up: `hoodie_up_idle`, `hoodie_up_thinking`, or `hoodie_up_sleep` for those
  states, before falling back to the equivalent ordinary pose.
- Hood down: `blink` while listening when the blink timer fires. Because a raster
  blink is a whole idle pose, it is not swapped into other states (that would
  visibly change her pose mid-thought).
- Idle mood: `idle_smile` or `idle_sleepy`, then `idle`.
- Other states: matching name; `thinking_hard` also falls back to `thinking`.
- Finally: `idle`.

The canonical manifest has no hood-up blink or hood-up error variant. Those states
therefore follow the rules above. Sprite caches persist for the process lifetime;
restart the pet after editing assets. Programmatic consumers can call
`RasterPack.clear()` to reload.

Hit regions are approximate adult-character regions; placement and anatomy vary
between packs. Raster masks refresh each frame so pose and breathing changes do
not retain an old input outline. Actual compositor support still varies by OS.

## Bundled artwork

The bundled pack is a 16-pose adult character with transparent backgrounds, one PNG
per state under `src/deepseek_chan/assets/adult/`. Because the source sheet had
irregular row heights, each character was cropped by its true alpha bounds and
normalized to a common baseline and scale rather than sliced on a fixed grid. The
original concept images live under `art/character-designs/`.

Replacement packs work best with a clean 4×4 sheet sliced by
`scripts/slice_sheet.py` (see [sprite-sheets.md](sprite-sheets.md)).
