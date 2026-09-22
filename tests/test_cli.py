import json

from deepseek_chan import cli, doctor


def test_doctor_subcommand_json_and_exit_status(monkeypatch, capsys):
    checks = [("assets", "missing idle", False), ("cache", "writable", True)]
    monkeypatch.setattr(doctor, "diagnose", lambda **kwargs: checks)
    assert cli.main(["doctor", "--json"]) == 1
    assert json.loads(capsys.readouterr().out) == [list(check) for check in checks]


def test_doctor_subcommand_success(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "diagnose", lambda **kwargs: [("cache", "writable", True)])
    assert cli.main(["doctor"]) == 0
    assert "OK cache: writable" in capsys.readouterr().out
