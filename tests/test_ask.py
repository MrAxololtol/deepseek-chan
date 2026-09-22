"""Building the ask-box command."""

from mochi.ask import build_command
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
