"""Guardado y carga de partidas con validación y recuperación.

- Cada ranura es ``saves/slot_N.json``; la versión anterior queda en ``.bak``.
- Al cargar se validan tipos y rangos y se descartan referencias a armas,
  naves, misiones o galaxias que ya no existan en la configuración.
- Si el archivo está dañado se intenta la copia ``.bak``; si también falla, el
  archivo se renombra a ``.corrupt-<fecha>`` y el juego sigue arrancando.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from game.core.config import GameConfig
from game.persistence.files import atomic_write_json, backup_path, read_json
from game.progression.profile import PlayerProfile

SAVE_VERSION = 1
SLOTS = 3


class SaveManager:
    def __init__(self, directory: Path, config: GameConfig):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.config = config

    def slot_path(self, slot: int) -> Path:
        return self.dir / f"slot_{slot}.json"

    def exists(self, slot: int) -> bool:
        return self.slot_path(slot).exists()

    # --- guardar -------------------------------------------------------------
    def save(self, slot: int, profile: PlayerProfile) -> None:
        profile.updated_at = time.time()
        data = {"version": SAVE_VERSION, "game": "galactic_dominion_3d", "profile": profile.to_dict()}
        atomic_write_json(self.slot_path(slot), data)

    # --- cargar --------------------------------------------------------------
    def load(self, slot: int) -> tuple[PlayerProfile | None, list[str]]:
        warnings: list[str] = []
        path = self.slot_path(slot)
        if not path.exists():
            return None, warnings
        for candidate in (path, backup_path(path)):
            if not candidate.exists():
                continue
            try:
                profile, notes = self.validate(read_json(candidate))
                warnings += notes
                if candidate != path:
                    warnings.append("La partida estaba dañada; se recuperó la copia de seguridad anterior.")
                    atomic_write_json(path, {"version": SAVE_VERSION, "game": "galactic_dominion_3d",
                                             "profile": profile.to_dict()}, keep_backup=False)
                return profile, warnings
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                warnings.append(f"No se pudo leer {candidate.name}: {exc}")
        stamp = time.strftime("%Y%m%d-%H%M%S")
        quarantine = path.with_name(f"{path.name}.corrupt-{stamp}")
        try:
            path.replace(quarantine)
            warnings.append(f"La partida dañada se apartó como {quarantine.name}.")
        except OSError:
            pass
        return None, warnings

    def summary(self, slot: int) -> dict:
        """Resumen para el menú (no modifica nada aunque el archivo esté dañado)."""
        path = self.slot_path(slot)
        if not path.exists():
            return {"slot": slot, "exists": False}
        try:
            profile, _ = self.validate(read_json(path))
        except Exception:  # noqa: BLE001 - cualquier fallo se muestra como partida dañada
            return {"slot": slot, "exists": True, "corrupt": True}
        galaxy = self.config.galaxy(profile.current_galaxy)["name"]
        return {"slot": slot, "exists": True, "corrupt": False, "name": profile.name, "level": profile.level,
                "credits": profile.credits, "galaxy": galaxy, "updated_at": profile.updated_at,
                "missions": len(profile.completed_missions)}

    def latest_slot(self) -> int | None:
        best, best_time = None, -1.0
        for slot in range(1, SLOTS + 1):
            info = self.summary(slot)
            if info.get("exists") and not info.get("corrupt") and info["updated_at"] > best_time:
                best, best_time = slot, info["updated_at"]
        return best

    # --- validación ----------------------------------------------------------
    def validate(self, data: dict) -> tuple[PlayerProfile, list[str]]:
        notes: list[str] = []
        if not isinstance(data, dict) or "profile" not in data:
            raise ValueError("estructura de partida desconocida")
        if int(data.get("version", 0)) > SAVE_VERSION:
            raise ValueError("la partida es de una versión más nueva del juego")
        raw = data["profile"]
        if not isinstance(raw, dict):
            raise ValueError("perfil inválido")
        cfg = self.config
        default = PlayerProfile.new(cfg)
        profile = PlayerProfile.new(cfg)

        def num(key, low=0, high=None, kind=int):
            value = raw.get(key, getattr(default, key))
            value = kind(value)
            if value < low:
                notes.append(f"Valor corregido: {key}")
                value = low
            if high is not None and value > high:
                notes.append(f"Valor corregido: {key}")
                value = high
            return value

        profile.name = str(raw.get("name", default.name))[:24] or default.name
        profile.level = num("level", 1, int(cfg.economy["pilot_level"]["max_level"]))
        profile.xp = num("xp")
        profile.credits = num("credits")
        mats = raw.get("materials", {})
        profile.materials = {k: max(0, int(v)) for k, v in mats.items() if k in cfg.economy["materials"]} \
            if isinstance(mats, dict) else {}
        player_weapons = cfg.player_weapons()
        profile.unlocked_weapons = [w for w in raw.get("unlocked_weapons", []) if w in player_weapons] \
            or list(default.unlocked_weapons)
        for w in cfg.economy["start"]["weapons"]:
            if w not in profile.unlocked_weapons:
                profile.unlocked_weapons.append(w)
        profile.blueprints = [w for w in raw.get("blueprints", []) if w in player_weapons]
        loadout = raw.get("loadout", {}) if isinstance(raw.get("loadout"), dict) else {}
        for slot in ("primary", "secondary", "special"):
            wid = loadout.get(slot)
            valid = wid in profile.unlocked_weapons and cfg.weapons[wid]["slot"] == slot
            profile.loadout[slot] = wid if valid else default.loadout.get(slot)
        upgrades = raw.get("upgrades", {}) if isinstance(raw.get("upgrades"), dict) else {}
        profile.upgrades = {uid: max(0, min(int(upgrades.get(uid, 0)), cfg.upgrades[uid]["max_level"]))
                            for uid in cfg.upgrades}
        profile.owned_ships = [s for s in raw.get("owned_ships", []) if s in cfg.ships] or [cfg.start_ship]
        if cfg.start_ship not in profile.owned_ships:
            profile.owned_ships.insert(0, cfg.start_ship)
        ship = raw.get("ship")
        profile.ship = ship if ship in profile.owned_ships else profile.owned_ships[0]
        items = []
        for item in raw.get("inventory", []) if isinstance(raw.get("inventory"), list) else []:
            if isinstance(item, dict) and item.get("stat") in cfg.economy["components"] \
                    and item.get("rarity") in cfg.economy["rarities"] and item.get("id"):
                item["value"] = float(item.get("value", 0))
                item["tier"] = max(1, min(5, int(item.get("tier", 1))))
                items.append(item)
        profile.inventory = items[: int(cfg.economy["inventory_limit"])]
        ids = {i["id"] for i in profile.inventory}
        slots = int(cfg.ships[profile.ship]["component_slots"])
        profile.equipped_components = [i for i in raw.get("equipped_components", []) if i in ids][:slots]
        mission_ids = {m["id"] for g in cfg.galaxies for m in g["missions"]}
        profile.completed_missions = [m for m in raw.get("completed_missions", []) if m in mission_ids]
        galaxy_ids = [g["id"] for g in cfg.galaxies]
        profile.unlocked_galaxies = [g for g in galaxy_ids if g in raw.get("unlocked_galaxies", [])] \
            or [galaxy_ids[0]]
        if galaxy_ids[0] not in profile.unlocked_galaxies:
            profile.unlocked_galaxies.insert(0, galaxy_ids[0])
        current = raw.get("current_galaxy")
        profile.current_galaxy = current if current in profile.unlocked_galaxies else profile.unlocked_galaxies[-1]
        profile.flags = {k: bool(v) for k, v in raw.get("flags", {}).items()} \
            if isinstance(raw.get("flags"), dict) else {}
        stats = raw.get("stats", {}) if isinstance(raw.get("stats"), dict) else {}
        for key, value in default.stats.items():
            try:
                profile.stats[key] = type(value)(stats.get(key, value))
            except (TypeError, ValueError):
                profile.stats[key] = value
        profile.created_at = float(raw.get("created_at", default.created_at))
        profile.updated_at = float(raw.get("updated_at", default.updated_at))
        return profile, notes
