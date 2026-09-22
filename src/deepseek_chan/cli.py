"""Command line interface: ``deepseek-chan <command>``."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from . import __version__, config
from .ipc import emit


def _opencode_plugin_dir(project: bool) -> Path:
    if project:
        d = Path.cwd() / ".opencode" / "plugins"
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
        d = Path(base) / "opencode" / "plugins"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cmd_run(args: argparse.Namespace) -> int:
    if args.summon:
        emit("summon")
        return 0
    if args.pat:
        emit("pat")
        return 0
    if args.flick:
        emit("flick")
        return 0
    if args.wake:
        emit("wake")
        return 0
    if args.sleep:
        emit("sleep")
        return 0
    if args.outfit is not None:
        emit("outfit", args.outfit)
        return 0

    from .app import run

    return run(config_path=args.config, demo=args.demo, state=args.state)


def cmd_install_plugin(args: argparse.Namespace) -> int:
    src = Path(__file__).resolve().parent / "plugin" / "deepseek-pet.js"
    dest_dir = _opencode_plugin_dir(args.project)
    dest = dest_dir / "deepseek-pet.js"
    shutil.copyfile(src, dest)
    print(f"installed opencode plugin -> {dest}")
    print("restart opencode for the plugin to load")
    return 0


def cmd_paths(args: argparse.Namespace) -> int:
    from .sprites import BUNDLED_DIR

    print(f"config dir : {config.config_dir()}")
    print(f"cache dir  : {config.cache_dir()}")
    print(f"state file : {config.state_path()}")
    print(f"events log : {config.events_path()}")
    print(f"assets dir : {BUNDLED_DIR}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    dest = config.save_example()
    print(f"example config -> {dest}")
    return 0


def cmd_outfit(args: argparse.Namespace) -> int:
    emit("outfit", args.name or "")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    emit("ask", "hover" if args.hover else "")
    return 0


def cmd_install_hotkey(args: argparse.Namespace) -> int:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    rc = base / "sxhkd" / "sxhkdrc"
    ask_hotkey = getattr(args, "ask_hotkey", "super + alt + button1")
    block = (
        "\n# >>> deepseek-chan >>>\n"
        f"{args.hotkey}\n"
        "    deepseek-chan --summon\n"
        f"{ask_hotkey}\n"
        "    deepseek-chan ask --hover\n"
        "# <<< deepseek-chan <<<\n"
    )
    if not rc.is_file():
        print(f"no sxhkdrc found at {rc}")
        print("add these lines manually instead:")
        print(block)
        return 1
    text = rc.read_text(encoding="utf-8")
    if "# >>> deepseek-chan >>>" in text:
        print("deepseek-chan hotkeys already installed")
        return 0
    rc.write_text(text + block, encoding="utf-8")
    print(f"installed hotkeys in {rc}")
    print("reload sxhkd with:  pkill -USR1 sxhkd")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deepseek-chan", description="DeepSeek-chan desktop pet")
    parser.add_argument("--version", action="version", version=f"deepseek-chan {__version__}")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="run the overlay (default)")
    run.add_argument("--config", help="path to a config.toml")
    run.add_argument("--demo", action="store_true", help="cycle through every state")
    run.add_argument("--state", help="pin a single state (debugging)")
    run.add_argument("--summon", action="store_true")
    run.add_argument("--pat", action="store_true")
    run.add_argument("--flick", action="store_true")
    run.add_argument("--wake", action="store_true")
    run.add_argument("--sleep", action="store_true")
    run.add_argument("--outfit", nargs="?", const="", help="toggle or set the outfit")
    run.set_defaults(func=cmd_run)

    plugin = sub.add_parser("install-plugin", help="install the opencode plugin")
    plugin.add_argument("--project", action="store_true", help="install into ./.opencode/plugins")
    plugin.set_defaults(func=cmd_install_plugin)

    paths = sub.add_parser("paths", help="print runtime paths")
    paths.set_defaults(func=cmd_paths)

    cfg = sub.add_parser("config", help="write an example config.toml")
    cfg.set_defaults(func=cmd_config)

    outfit = sub.add_parser("outfit", help="toggle or set the character outfit")
    outfit.add_argument("name", nargs="?", choices=["hoodie", "hoodie_up"], default=None)
    outfit.set_defaults(func=cmd_outfit)

    ask = sub.add_parser("ask", help="open the ask-opencode box (optionally only over the pet)")
    ask.add_argument("--hover", action="store_true", help="only if the pointer is over the pet")
    ask.set_defaults(func=cmd_ask)

    hotkey = sub.add_parser("install-hotkey", help="add sxhkd summon + ask bindings")
    hotkey.add_argument("--hotkey", default="super + p")
    hotkey.add_argument("--ask-hotkey", default="super + alt + button1")
    hotkey.set_defaults(func=cmd_install_hotkey)

    from .doctor import configure_parser, run_checks

    doctor = sub.add_parser("doctor", help="check dependencies, assets, plugin and cache")
    configure_parser(doctor)
    doctor.set_defaults(func=run_checks)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not argv:
        argv = ["run"]
    elif argv[0].startswith("-") and argv[0] not in ("--version",):
        argv = ["run"] + argv
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
