"""Building the ask-box command."""

from mochi.ask import build_command, skin_command
from mochi.config import Config


def test_template_placeholder_replaced():
    cfg = Config(ask_command=["kitty", "--hold", "-e", "opencode", "run", "{prompt}"])
    assert build_command(cfg, "hello world") == [
        "kitty", "--hold", "-e", "opencode", "run", "hello world",
    ]


def test_default_runs_opencode_run():
    command = build_command(Config(ask_command=[]), "what is 2+2")
    assert command[-3:] == ["run"] or "run" in command
    assert command[-1] == "what is 2+2"
    assert any("opencode" in part for part in command)


def test_skin_command_parses_bare_commands():
    assert skin_command("/neko") == "neko"
    assert skin_command("/whale") == "whale"
    assert skin_command("  /NEKO  ") == "neko"
    assert skin_command("/whale please come back") == "whale"
    assert skin_command("/neko extra args") == "neko"


def test_skin_command_ignores_everything_else():
    assert skin_command("hello") is None
    assert skin_command("/help") is None
    assert skin_command("/nekoo") is None
    assert skin_command("") is None
    assert skin_command("  ") is None
