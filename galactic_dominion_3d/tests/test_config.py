import json
import shutil

import pytest

from game.core.config import ConfigError, GameConfig


def test_all_config_files_load_and_cross_reference(config):
    assert len(config.galaxies) == 5
    assert [g["tier"] for g in config.galaxies] == [1, 2, 3, 4, 5]
    assert len(config.player_weapons()) == 8
    for galaxy in config.galaxies:
        assert any(m["type"] == "boss" for m in galaxy["missions"])


def test_invalid_reference_is_reported(tmp_path, config):
    for file in config.dir.glob("*.json"):
        shutil.copy(file, tmp_path / file.name)
    data = json.loads((tmp_path / "galaxies.json").read_text(encoding="utf-8"))
    data["galaxies"][0]["missions"][0]["waves"][0]["enemies"] = {"no_existe": 2}
    (tmp_path / "galaxies.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigError, match="no_existe"):
        GameConfig(tmp_path)


def test_broken_json_gives_readable_error(tmp_path, config):
    for file in config.dir.glob("*.json"):
        shutil.copy(file, tmp_path / file.name)
    (tmp_path / "weapons.json").write_text("{ roto", encoding="utf-8")
    with pytest.raises(ConfigError, match="weapons.json"):
        GameConfig(tmp_path)
