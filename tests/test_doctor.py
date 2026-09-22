"""Diagnostics isolate desktop inspection and never start the actual overlay."""
import json
from types import SimpleNamespace

import pytest

from mochi import doctor


@pytest.fixture
def environment(tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    assets.mkdir()
    for name in doctor.REQUIRED_ASSETS:
        (assets / name).write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / "mochi-pet.js").write_text("MochiPlugin tool.execute.before")
    monkeypatch.setattr(doctor, "_qt_check", lambda: ("test Qt", True))
    monkeypatch.setattr(doctor, "_mask_check", lambda: ("test backend", True))
    return dict(asset_dir=assets, plugin_dir=plugins, cache_dir=tmp_path / "cache")


def test_diagnose_public_contract_and_probe_cleanup(environment):
    results = doctor.diagnose(**environment)
    assert [name for name, _, _ in results] == [
        "PyQt6", "compositor/setMask", "assets", "plugin", "cache",
    ]
    assert all(isinstance(detail, str) and ok is True for _, detail, ok in results)
    assert list(environment["cache_dir"].iterdir()) == []


@pytest.mark.parametrize("contents", [None, "broken XML", "<html/>"])
def test_bad_asset_reported_without_fallback(environment, contents):
    path = environment["asset_dir"] / "body.svg"
    if contents is None:
        path.unlink()
    else:
        path.write_text(contents)
    result = {name: (detail, ok) for name, detail, ok in doctor.diagnose(**environment)}
    assert result["assets"][1] is False
    assert "body.svg" in result["assets"][0]
    assert result["cache"][1] is True


def test_cache_failure_does_not_raise(environment):
    environment["cache_dir"].write_text("a file blocks this directory")
    assert doctor.diagnose(**environment)[-1][2] is False


def test_missing_plugin_does_not_create_directory(tmp_path):
    directory = tmp_path / "missing"
    detail, ok = doctor._plugin_check(tmp_path, directory)
    assert not ok
    assert "mochi-pet.js" in detail
    assert not directory.exists()


def test_project_plugin_discovery(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    plugin = tmp_path / ".opencode" / "plugins" / "mochi-pet.js"
    plugin.parent.mkdir(parents=True)
    plugin.write_text("MochiPlugin tool.execute.before")
    assert doctor._plugin_check(tmp_path, None)[1]


def test_qt_import_failure(monkeypatch):
    def fail(name):
        raise ImportError("not installed")
    monkeypatch.setattr(doctor.importlib, "import_module", fail)
    detail, ok = doctor._qt_check()
    assert not ok
    assert "not installed" in detail


@pytest.mark.parametrize("backend,expected", [(None, False), ("offscreen", False), ("xcb", True)])
def test_mask_backend_capability(monkeypatch, backend, expected):
    instance = None if backend is None else SimpleNamespace(platformName=lambda: backend)
    module = SimpleNamespace(
        QWidget=SimpleNamespace(setMask=lambda: None),
        QApplication=SimpleNamespace(instance=lambda: instance),
    )
    monkeypatch.setattr(doctor.importlib, "import_module", lambda name: module)
    assert doctor._mask_check()[1] is expected


def test_json_cli(environment, capsys):
    result = doctor.main([
        "--assets", str(environment["asset_dir"]),
        "--plugin-dir", str(environment["plugin_dir"]),
        "--cache-dir", str(environment["cache_dir"]), "--json",
    ])
    assert result == 0
    assert len(json.loads(capsys.readouterr().out)) == 5
