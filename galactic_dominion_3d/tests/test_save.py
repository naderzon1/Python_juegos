import json

from game.persistence.files import backup_path
from game.persistence.save_manager import SaveManager


def test_roundtrip_keeps_progress(tmp_path, config, profile):
    manager = SaveManager(tmp_path, config)
    profile.level, profile.credits = 7, 1234
    profile.upgrades["hull"] = 3
    profile.completed_missions.append("orion_tutorial")
    profile.unlocked_galaxies.append("crimson")
    profile.blueprints.append("precision_laser")
    manager.save(1, profile)
    loaded, warnings = manager.load(1)
    assert not warnings
    assert loaded.level == 7 and loaded.credits == 1234
    assert loaded.upgrades["hull"] == 3
    assert loaded.completed_missions == ["orion_tutorial"]
    assert loaded.unlocked_galaxies == ["orion", "crimson"]


def test_second_save_keeps_backup(tmp_path, config, profile):
    manager = SaveManager(tmp_path, config)
    manager.save(1, profile)
    profile.credits = 99
    manager.save(1, profile)
    assert backup_path(manager.slot_path(1)).exists()


def test_corrupt_save_recovers_from_backup(tmp_path, config, profile):
    manager = SaveManager(tmp_path, config)
    profile.credits = 500
    manager.save(1, profile)
    manager.save(1, profile)  # crea .bak con 500 créditos
    manager.slot_path(1).write_text("{ dañado", encoding="utf-8")
    loaded, warnings = manager.load(1)
    assert loaded is not None and loaded.credits == 500
    assert any("copia de seguridad" in w for w in warnings)


def test_unrecoverable_save_is_quarantined(tmp_path, config):
    manager = SaveManager(tmp_path, config)
    manager.slot_path(2).write_text("basura", encoding="utf-8")
    loaded, warnings = manager.load(2)
    assert loaded is None and warnings
    assert not manager.slot_path(2).exists()
    assert list(tmp_path.glob("slot_2.json.corrupt-*"))
    assert manager.summary(3)["exists"] is False


def test_validation_clamps_and_drops_unknown_data(tmp_path, config, profile):
    manager = SaveManager(tmp_path, config)
    data = {"version": 1, "profile": profile.to_dict()}
    data["profile"].update({"credits": -50, "level": 999, "upgrades": {"hull": 999},
                            "unlocked_weapons": ["energy_cannon", "arma_fantasma"],
                            "loadout": {"primary": "arma_fantasma"}, "ship": "nave_fantasma",
                            "completed_missions": ["mision_fantasma"]})
    manager.slot_path(1).write_text(json.dumps(data), encoding="utf-8")
    loaded, warnings = manager.load(1)
    assert loaded.credits == 0
    assert loaded.level == config.economy["pilot_level"]["max_level"]
    assert loaded.upgrades["hull"] == config.upgrades["hull"]["max_level"]
    assert "arma_fantasma" not in loaded.unlocked_weapons
    assert loaded.loadout["primary"] == "energy_cannon"
    assert loaded.ship == config.start_ship
    assert loaded.completed_missions == []
    assert warnings
