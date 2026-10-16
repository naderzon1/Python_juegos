"""Perfil persistente del piloto: todo lo que se conserva entre sesiones."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from game.core.config import GameConfig


@dataclass
class PlayerProfile:
    name: str = "Piloto"
    level: int = 1
    xp: int = 0
    credits: int = 0
    materials: dict = field(default_factory=dict)
    unlocked_weapons: list = field(default_factory=list)
    blueprints: list = field(default_factory=list)
    loadout: dict = field(default_factory=lambda: {"primary": None, "secondary": None, "special": None})
    upgrades: dict = field(default_factory=dict)
    ship: str = "vanguard"
    owned_ships: list = field(default_factory=list)
    inventory: list = field(default_factory=list)
    equipped_components: list = field(default_factory=list)
    completed_missions: list = field(default_factory=list)
    unlocked_galaxies: list = field(default_factory=list)
    current_galaxy: str = ""
    flags: dict = field(default_factory=dict)
    stats: dict = field(default_factory=lambda: {"kills": 0, "deaths": 0, "missions": 0, "play_time": 0.0,
                                                 "bosses": 0})
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def new(cls, config: GameConfig, name: str = "Piloto") -> "PlayerProfile":
        start = config.economy["start"]
        first = config.galaxies[0]["id"]
        return cls(
            name=name,
            credits=int(start["credits"]),
            materials=dict(start["materials"]),
            unlocked_weapons=list(start["weapons"]),
            loadout=dict(start["loadout"]),
            upgrades={uid: 0 for uid in config.upgrades},
            ship=config.start_ship,
            owned_ships=[config.start_ship],
            unlocked_galaxies=[first],
            current_galaxy=first,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def material(self, material_id: str) -> int:
        return int(self.materials.get(material_id, 0))

    def add_material(self, material_id: str, amount: int) -> None:
        self.materials[material_id] = self.material(material_id) + int(amount)

    def item(self, item_id: str) -> dict | None:
        for item in self.inventory:
            if item.get("id") == item_id:
                return item
        return None

    def is_mission_available(self, mission: dict) -> bool:
        return all(req in self.completed_missions for req in mission.get("requires", []))
