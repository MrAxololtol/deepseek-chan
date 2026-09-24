# Cozy catgirl sprite pack

Mochi in a periwinkle cable-knit sweater, navy lounge shorts, striped knee-high socks, and slippers, with blue cat ears and a tail. Includes all 16 canonical state images as transparent 512 x 640 PNGs.

The reactions include paw gestures, slow blinking, flattened grumpy ears, a puffed startled tail, and curled-up sleep. The three `hoodie_up_*` states use a matching knitted cat-ear hood. These are complete state illustrations, not frame-by-frame animation.

## Use

From the repository root, after closing any existing Mochi instance:

```sh
mochi run --config sprite-packs/catgirl-cozy.toml
```

Or set `sprite_pack` in your own config to the absolute path of this directory. The standard `hoodie` and `hoodie_up` outfit names are retained for compatibility. Theme following is disabled in the sample config to preserve the blue palette.

## Included states

| Idle and thinking | Reactions | Rest | Alternate and held |
| --- | --- | --- | --- |
| idle | working | error | hoodie_up_idle |
| blink | finished | sleep | hoodie_up_thinking |
| thinking | pat | idle_smile | hoodie_up_sleep |
| thinking_hard | surprised | idle_sleepy | held |

High-resolution source images and exact generation prompts are in `art/character-designs/catgirl-cozy-poses/`. The canonical 4 x 4 sheet is `art/character-designs/catgirl-cozy-sheet.png`, ordered according to `src/mochi/manifest.py`.

Created with built-in image generation using the approved cozy outfit as the character reference. Packaging preserves generated alpha and fits the artwork into uniform sprite canvases. Individual generations can have small drawing and alignment differences.
