# Contributing

Use Python 3.9-compatible syntax and keep the pet's state logic independent of Qt.
New runtime dependencies should be discussed before introduction. Project code is
MIT-licensed; include provenance and compatible redistribution terms for artwork.
Never commit reference videos, private session logs, or personal configuration.

From an integrated checkout:

```sh
python -m venv .venv
# Activate .venv using your shell's activation command.
python -m pip install -e . pytest ruff
ruff check .
```

Run headlessly on POSIX:

```sh
QT_QPA_PLATFORM=offscreen python -m pytest
```

Or in PowerShell:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest
```

State tests use explicit timestamps instead of waiting for wall-clock time. Slicer
tests create tiny synthetic QImages and write only to pytest temporary directories.
CI covers Ubuntu, Windows, and macOS on Python 3.9 through 3.13. Desktop behavior
still needs a manual check on a real compositor; headless checks cannot verify it.

In a pull request, explain the behavior changed, checks run, and any desktop-specific
limitations. For bug reports, include OS, Python/Qt version, display backend, a small
reproduction, and sanitized error output.

Plugin regression tests use Node's built-in test API with an isolated VM:

```sh
node --experimental-vm-modules tests/test_plugin.mjs
node --experimental-vm-modules tests/test_plugin_startup.mjs
```

No npm dependencies are required. The VM executes the real plugin source with
in-memory filesystem adapters and a simulated running pet, so tests neither launch
an overlay nor write session logs. The direct invocation avoids an extra test-runner
child process and still reports TAP results and a nonzero exit code on failure.
CI runs this in a separate Node 22 job.
