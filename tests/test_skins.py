"""Skin registry, pack resolution and persistence."""

from mochi import config, skins


def test_normalize_known_and_unknown():
    assert skins.normalize("neko") == "neko"
    assert skins.normalize("WHALE") == "whale"
    assert skins.normalize("") == "whale"
    assert skins.normalize("dragon") == "whale"


def test_bundled_paths():
    assert skins.bundled("neko").name == "neko"
    assert skins.bundled("whale").name == "adult"


def test_follows_theme_per_skin():
    assert skins.follows_theme("whale") is True
    assert skins.follows_theme("neko") is False
    assert skins.follows_theme("bogus") is True


def test_pack_for_prefers_existing_pack(tmp_path):
    neko = tmp_path / "neko"
    neko.mkdir()
    (neko / "idle.png").write_bytes(b"x")
    assert skins.pack_for("neko", neko_pack=str(neko)) == neko


def test_pack_for_falls_back_to_adult(tmp_path):
    out = skins.pack_for("neko", neko_pack=str(tmp_path / "nope"))
    assert out.name == "adult"


def test_pack_for_whale_uses_base_pack(tmp_path):
    base = tmp_path / "custom"
    base.mkdir()
    (base / "idle.png").write_bytes(b"x")
    assert skins.pack_for("whale", base_pack=str(base)) == base


def test_remember_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "cache_dir", lambda: tmp_path)
    assert skins.remembered() == "whale"
    skins.remember("neko")
    assert skins.remembered() == "neko"
    skins.remember("bogus")
    assert skins.remembered() == "whale"
