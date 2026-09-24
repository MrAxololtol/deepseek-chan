# Cozy catgirl pack: Linux / DeepSeek handoff

This branch contains Mochi's complete 16-state cozy catgirl skin. Keep the same adult character, cobalt-blue hair and eyes, cat ears and tail, periwinkle cable-knit sweater, navy lounge shorts, blue-and-white striped knee-high socks, and navy slippers when making more poses.

## Files to open

- `sprite-packs/catgirl-cozy/`: all 16 runtime PNGs, each 512 x 640 with transparency.
- `sprite-packs/catgirl-cozy.toml`: ready-to-use config; run from the repo root.
- `art/character-designs/catgirl-cozy-poses/`: high-resolution original PNGs and exact generation prompts.
- `art/character-designs/catgirl-cozy-sheet.png`: canonical 2048 x 2560, 4 x 4 sprite sheet.
- `scripts/package_catgirl.py`: reproducible packaging script; preserves alpha and fits sources into runtime canvases.
- `docs/raster-packs.md`, `docs/sprite-sheets.md`, and `src/mochi/manifest.py`: runtime format and canonical state names.

## Linux setup

```sh
git clone --branch catgirl-cozy-sprites https://github.com/MrAxololtol/mochi.git
cd mochi
python3 -m venv .venv
source .venv/bin/activate
pip install .
mochi run --config sprite-packs/catgirl-cozy.toml
```

Close any already-running Mochi instance before launching with the new config. A graphical desktop is required. For automatic reactions to OpenCode, run `mochi install-plugin` and restart OpenCode.

If this repository is already cloned, commit or stash your local changes before switching branches, then:

```sh
git fetch origin
git switch --track origin/catgirl-cozy-sprites
```

## Editing instructions for DeepSeek

Read this file and the pack README first. Open the high-resolution pose PNGs using your image-viewing tool if available. They are flattened raster artwork, not layered source files. An image-generation or graphics-editing tool is needed to redraw artwork; code alone can package and validate the assets.

Preserve all 16 canonical filenames and transparent backgrounds. Keep idle and blink aligned as closely as possible. The three `hoodie_up_*` images use a matching knitted cat-ear hood. Catlike behavior includes paw gestures, ear posture, a puffed tail when surprised, curled-up sleeping, and dangling when held. These are state illustrations, not frame-by-frame animation.

After editing the high-resolution PNGs:

```sh
python scripts/package_catgirl.py
mochi doctor --assets sprite-packs/catgirl-cozy
```

Restart Mochi to clear its sprite cache. Inspect all states visually. The doctor should report 16/16 readable poses; its compositor CHECK is expected outside a running GUI and does not mean the PNG pack failed.

The sample config disables automatic theme recoloring to preserve the intended blue palette. Small drawing/alignment differences remain between independently generated poses. The pack does not replace the default bundled artwork.
