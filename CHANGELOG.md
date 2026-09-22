# Changelog

All notable changes to DeepSeek-chan are recorded here. Every push to GitHub
adds an entry, newest first, with the commit it shipped in.

## 2026-09-23

### Follow the desktop theme — `6aa271b`
- The pet now watches the accent `colorChange` writes to
  `~/.config/polybar/colors.ini` (rofi/kitty/dunst share it) and **hue-shifts her
  blue parts** — hair, outfit and trim — to match live, leaving skin untouched.
- Recolours are cached per hue delta (`~/.cache/deepseek-chan/theme-pack/`).
- `deepseek-chan theme` re-reads the accent; `deepseek-chan theme '#hex'` pins one.
- New config: `theme_follow`, `theme_accent_file`, `theme_color`, `theme_base_hue`.

### Ask-opencode box + pipx install — `da978ab`
- **Ask her anything:** Super+Alt-click the pet (or `deepseek-chan ask`) opens a
  small input box above her; Enter runs `opencode run "<question>"` in a terminal.
  `deepseek-chan ask --hover` only opens when the pointer is over the pet; the
  sxhkd binding uses that. The command is configurable via `ask_command` /
  `ask_hotkey` (`{prompt}` is substituted).
- `deepseek-chan install-hotkey` now installs the summon and ask bindings.
- Switched to a self-contained **pipx** install so the launcher no longer depends
  on the source checkout.

### Pat/flick show their own lines — `0cf6d8f`
- Clicking her face no longer shows a stale "Finished thinking" bubble. Mouse
  pat and flick now go through the same reaction path as the event stream, so
  they set their own cycling lines (and hearts/mood) correctly.

### Quips, grab-to-drag, lifted lines — `3bc040a`
- Petting now cycles through **five** lines in order instead of picking randomly.
- Added dedicated lines for **flicking** her nose and for being **lifted**.
- Dragging now starts only when you grab her **stomach**, so petting her hair
  and dragging her no longer happen at the same time.
- `[quips]` in config now merges per category, so you only override what you set.
- Flicking, waking and summoning each have their own lines.

### Dropped `idle_smile` — `73bf429`
- Removed the hands-behind-back mood sprite; high mood falls back to the plain
  idle pose.

### Fixed upscaled mood poses — `a1e45ce`
- The sheet drew the `idle_smile`/`idle_sleepy`/`error` rows smaller and
  squished, so height-only normalization inflated their heads ~40%.
- Poses are now scaled X by head width and Y by body height, keeping head size
  and body height consistent across every expression.

### Picom exclusions documented — `a8ce939`
- README now notes the picom `blur/shadow/fade/rounded-corners` exclusions a
  transparent overlay needs.

### Overlay behaviour on fullscreen — `f14621c`
- Fullscreen hide/show now changes **window opacity** instead of unmapping, so
  bspwm never re-manages her as a plain window; clicks pass through while hidden.
- She is kept floating, borderless, sticky and on the **above** layer, re-asserted
  after showing.

### Sprite pack re-aligned — `b525619`
- Each pose is shifted to best overlap the idle pose (head/torso registration)
  instead of being centred by its own asymmetric bounding box, removing
  pose-to-pose sideways jumps.

### Blink pose-swap glitch — `7a3477f`
- A raster blink is a whole idle pose, so swapping it in while thinking/working
  changed her pose for half a second. Blinking is now restricted to listening.

### Follow across bspwm desktops — `0755581`
- The pet is now a managed, non-focusable window that bspwm floats, de-borders
  and marks **sticky**, so she appears on every workspace.
- New `follow_desktops` option (default on).

### CI runs on Linux — `4c33ba6`
- Install Qt system libraries (`libegl1`, `libgl1`, `libxkbcommon0`, …) on Linux
  runners so PyQt6 imports headlessly.

### Continuous integration — `3911255`
- GitHub Actions: ruff + pytest on Ubuntu/Windows/macOS across Python 3.9–3.13,
  plus Node plugin tests.

### Scruff-grab physics — `05589bd`
- Grab her by the back of her shirt and she dangles from that point.
- A fast drag flings her sideways; a damped spring swings her past centre and
  settles her back. Tunable `[physics]` block in the config.

### Raster renderer, diagnostics, themes and tests — `fd86a3b`
- PNG sprite renderer with pose fallbacks, hooded variants and a held pose,
  shipping the bundled 16-pose adult pack as the default.
- New modules: `event_stream` (partial-line-safe NDJSON), `colors`, `manifest`,
  `doctor`; three theme presets; opencode plugin fixes (async launch, Windows
  cache path, result classification).
- 116 Python + 14 Node tests, ruff clean, CI workflow, README and docs.

### Baseline — `65b0d8d`
- Initial working SVG DeepSeek-chan pet: transparent overlay, click-through,
  drag, state machine (listening/thinking/thinking-longer/working/finished/
  error/pat/surprised/sleep), blink, breathing, idle flip, ahoge, Zzz, and the
  opencode plugin bridge.

## Related repositories

### `MrAxololtol/dotfiles`
- `093cf2a` — bspwm: autostart the pet on login (guarded, only if installed).
- `bc55d5e` — picom: exclude `deepseek-chan` from blur, shadow, fade and rounded corners.
