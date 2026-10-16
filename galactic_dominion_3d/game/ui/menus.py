"""Pantallas de menú navegables (DirectGUI).

Cada pantalla registra sus widgets y los destruye al cerrarse. Las acciones
llaman a métodos de ``GameApp`` (empezar misión, guardar, comprar...), que
es quien conoce el estado del juego.
"""
from __future__ import annotations

import copy
import time

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectEntry, DirectFrame, DirectScrolledFrame
from panda3d.core import TextNode

from game.economy import shop
from game.inventory.items import describe_item, equip_component, sell_item, sell_value, unequip_component
from game.persistence.save_manager import SLOTS
from game.progression.evolution import evolution
from game.progression.leveling import level_progress, xp_for_next_level
from game.ships.stats import compute_ship_stats
from game.ui import theme
from game.ui.theme import CYAN, DIM, GOLD, GREEN, MAGENTA, ORANGE, RED, TEXT, Bar

SLOT_NAMES = {"primary": "Principal", "secondary": "Secundaria", "special": "Especial"}
STAT_NAMES = {"damage_mult": "daño", "max_speed": "velocidad", "accel": "aceleración", "turn_rate": "giro",
              "roll_rate": "alabeo", "max_shield": "escudo", "shield_regen": "regeneración de escudo",
              "max_hull": "casco", "max_energy": "energía", "energy_regen": "regeneración de energía",
              "missile_capacity": "misiles", "crit_bonus": "crítico", "lock_range": "alcance de fijación",
              "lock_time": "tiempo de fijación", "boost_mult": "impulso", "boost_cost": "consumo de impulso",
              "drone_damage_mult": "daño de drones", "drone_count": "drones"}
TYPE_NAMES = {"destroy_count": "Destrucción", "destroy_fleet": "Destruir flota", "defend_station": "Defensa",
              "escort": "Escolta", "recover_materials": "Recuperación", "survive_time": "Supervivencia",
              "eliminate_elite": "Eliminar élite", "boss": "Jefe"}


def fmt(n) -> str:
    return f"{int(n):,}".replace(",", ".")


class Screen:
    def __init__(self, app, name: str):
        self.app = app
        self.root = app.aspect2d.attachNewNode(name)
        self.widgets: list = []
        self.events: list[str] = []

    def w(self, widget):
        self.widgets.append(widget)
        return widget

    def accept(self, event: str, fn) -> None:
        self.app.accept(event, fn)
        self.events.append(event)

    def click(self):
        self.app.audio.play("ui_click", 0.5)

    def button(self, label, pos, command, width=0.5, enabled=True, parent=None, scale=0.045, extra=None, color=None,
               height=0.075):
        return self.w(theme.button(parent or self.root, label, pos, command, width, height, scale, enabled, color,
                                   extra, self.click))

    def text(self, value, pos, scale=0.045, color=TEXT, align=TextNode.ALeft, parent=None, wordwrap=None):
        return self.w(theme.text(parent or self.root, value, pos, scale, color, align, wordwrap=wordwrap))

    def panel(self, frame, pos=(0, 0), parent=None, color=theme.PANEL):
        return self.w(theme.panel(parent or self.root, frame, color=color, pos=pos))

    def slider(self, pos, value, on_change, width=0.6, value_range=(0, 1)):
        """Deslizador que llama a ``on_change(valor)`` cada vez que se mueve."""
        widget = self.w(theme.slider(self.root, pos, value, None, width, value_range))
        widget["command"] = lambda: on_change(float(widget["value"]))
        return widget

    def destroy(self) -> None:
        for event in self.events:
            self.app.ignore(event)
        for widget in reversed(self.widgets):
            try:
                widget.destroy()
            except Exception:  # noqa: BLE001 - el widget pudo destruirse con su padre
                pass
        self.root.removeNode()


def scrolled(screen: Screen, frame, canvas_height: float):
    l, r, b, t = frame
    sf = screen.w(DirectScrolledFrame(parent=screen.root, frameSize=frame, canvasSize=(l, r - 0.04, -canvas_height, 0),
                                      frameColor=(0.01, 0.03, 0.06, 0.75), scrollBarWidth=0.03,
                                      verticalScroll_frameColor=(0.05, 0.1, 0.16, 1),
                                      verticalScroll_thumb_frameColor=CYAN,
                                      verticalScroll_incButton_frameColor=(0.1, 0.25, 0.4, 1),
                                      verticalScroll_decButton_frameColor=(0.1, 0.25, 0.4, 1),
                                      horizontalScroll_frameSize=(0, 0, 0, 0), pos=(0, 0, 0)))
    sf.setPos(0, 0, 0)
    canvas = sf.getCanvas()
    canvas.setZ(t)

    def wheel(step):
        bar = sf.verticalScroll
        bar["value"] = max(0, min(1, bar["value"] + step))

    screen.accept("wheel_up", lambda: wheel(-0.08))
    screen.accept("wheel_down", lambda: wheel(0.08))
    return sf, canvas


class ConfirmDialog(Screen):
    def __init__(self, app, message: str, on_yes, on_no=None):
        super().__init__(app, "confirm")
        self.root.setBin("gui-popup", 50)
        self.w(DirectFrame(parent=self.root, frameColor=(0, 0, 0, 0.6), frameSize=(-3, 3, -2, 2), state=DGG.NORMAL))
        self.panel((-0.75, 0.75, -0.25, 0.25))
        self.text(message, (0, 0.1), 0.045, TEXT, TextNode.ACenter, wordwrap=30)
        self.button("Sí", (-0.25, -0.15), lambda: self._done(on_yes), 0.36)
        self.button("No", (0.25, -0.15), lambda: self._done(on_no), 0.36)

    def _done(self, fn):
        self.destroy()
        if fn:
            fn()


# =============================================================================
class MainMenu(Screen):
    def __init__(self, app, warnings: list[str]):
        super().__init__(app, "main-menu")
        self.text("GALACTIC DOMINION", (0, 0.62), 0.13, CYAN, TextNode.ACenter)
        self.text("3D", (0, 0.5), 0.09, ORANGE, TextNode.ACenter)
        self.text("Arcade espacial con progresión · Cinco galaxias · Un destino", (0, 0.42), 0.04, DIM,
                  TextNode.ACenter)
        latest = app.saves.latest_slot()
        y = 0.22
        self.button("Continuar partida", (0, y), lambda: app.load_game(latest), 0.62, enabled=latest is not None)
        self.button("Nueva partida", (0, y - 0.11), lambda: app.show_slots("new"), 0.62)
        self.button("Cargar partida", (0, y - 0.22), lambda: app.show_slots("load"), 0.62)
        self.button("Configuración", (0, y - 0.33), lambda: app.show_settings(app.show_main_menu), 0.62)
        self.button("Créditos y licencias", (0, y - 0.44), app.show_credits, 0.62)
        self.button("Salir", (0, y - 0.55), app.quit_game, 0.62)
        if warnings:
            self.text("\n".join(warnings[-4:]), (0, -0.62), 0.032, ORANGE, TextNode.ACenter, wordwrap=60)
        self.text("v1.0 · Panda3D · Ratón y teclado (mando opcional)", (0, -0.9), 0.03, DIM, TextNode.ACenter)


class CreditsScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "credits")
        self.panel((-1.1, 1.1, -0.75, 0.75))
        self.text("Créditos y licencias", (0, 0.62), 0.07, CYAN, TextNode.ACenter)
        body = ("GALACTIC DOMINION 3D — proyecto original.\n\n"
                "Motor: Panda3D (licencia BSD modificada). Cálculo: NumPy (BSD).\n"
                "Modelos 3D, texturas, sonidos y música: generados por el propio juego (código original del "
                "proyecto). No se usan recursos de terceros.\n"
                "Fuente de texto: la del sistema (Bahnschrift/Segoe UI en Windows) o la interna de Panda3D; "
                "no se redistribuye ninguna fuente.\n\n"
                "Los sonidos son síntesis provisionales: se pueden sustituir por grabaciones con el mismo "
                "nombre en assets/audio/generated.")
        self.text(body, (-1.0, 0.45), 0.038, TEXT, wordwrap=52)
        self.button("Volver", (0, -0.62), app.show_main_menu, 0.4)


class SlotScreen(Screen):
    def __init__(self, app, mode: str):
        super().__init__(app, "slots")
        self.mode = mode
        title = "Nueva partida: elige ranura" if mode == "new" else "Cargar partida"
        self.text(title, (0, 0.7), 0.07, CYAN, TextNode.ACenter)
        if mode == "new":
            self.text("Nombre del piloto:", (-0.6, 0.53), 0.045, DIM)
            self.entry = self.w(DirectEntry(parent=self.root, initialText="Piloto", numLines=1, width=12,
                                            scale=0.05, pos=(0.0, 0, 0.53), frameColor=(0.05, 0.12, 0.2, 1),
                                            text_fg=TEXT, entryFont=theme.font(), focus=0))
        for slot in range(1, SLOTS + 1):
            info = app.saves.summary(slot)
            y = 0.32 - (slot - 1) * 0.27
            self.panel((-0.85, 0.85, -0.11, 0.11), pos=(0, y))
            if not info["exists"]:
                desc = f"Ranura {slot}: vacía"
            elif info.get("corrupt"):
                desc = f"Ranura {slot}: partida dañada (se intentará recuperar la copia de seguridad)"
            else:
                stamp = time.strftime("%d/%m/%Y %H:%M", time.localtime(info["updated_at"]))
                desc = (f"Ranura {slot}: {info['name']} · nivel {info['level']} · {fmt(info['credits'])} CR\n"
                        f"{info['galaxy']} · {info['missions']} misiones · {stamp}")
            self.text(desc, (-0.8, y + 0.03), 0.038, TEXT)
            if mode == "new":
                label = "Sobrescribir" if info["exists"] else "Empezar"
                self.button(label, (0.62, y), self._new, 0.36, extra=[slot, info["exists"]])
            else:
                self.button("Cargar", (0.62, y), app.load_game, 0.36, enabled=info["exists"], extra=[slot])
        self.button("Volver", (0, -0.62), app.show_main_menu, 0.4)

    def _new(self, slot: int, occupied: bool) -> None:
        name = self.entry.get().strip() or "Piloto"
        if occupied:
            ConfirmDialog(self.app, f"¿Sobrescribir la ranura {slot}? La partida anterior se conservará como copia "
                                    f"de seguridad (.bak) hasta el próximo guardado.",
                          lambda: self.app.new_game(slot, name))
        else:
            self.app.new_game(slot, name)


# =============================================================================
class PilotBar:
    def __init__(self, screen: Screen):
        app = screen.app
        p = app.profile
        tl = screen.panel((-1.7, 1.7, -0.07, 0.07), pos=(0, 0.9))
        mats = "  ".join(f"{app.game_config.material_name(m)} {v}" for m, v in p.materials.items() if v)
        screen.text(f"{p.name} · Nivel {p.level}", (-1.64, 0.885), 0.042, CYAN)
        screen.text(f"{fmt(p.credits)} CR", (-0.85, 0.885), 0.042, GOLD)
        screen.text(mats or "Sin materiales", (-0.45, 0.885), 0.032, DIM)
        screen.text(f"XP {p.xp}/{xp_for_next_level(p.level, app.game_config)}", (1.64, 0.885), 0.032, DIM,
                    TextNode.ARight)
        self.bar = Bar(tl, (-1.64, -0.062), 3.28, 0.008, GREEN)
        self.bar.set(level_progress(p, app.game_config))
        screen.widgets.append(self.bar)


class GalaxyMap(Screen):
    def __init__(self, app, galaxy_id: str | None = None, mission_id: str | None = None):
        super().__init__(app, "galaxy-map")
        self.cfg = app.game_config
        self.profile = app.profile
        self.galaxy_id = galaxy_id or self.profile.current_galaxy
        self.mission_id = mission_id
        PilotBar(self)
        self.text("MAPA GALÁCTICO", (-1.62, 0.72), 0.06, CYAN)
        self.detail_widgets: list = []
        positions = [(-1.35, 0.35), (-1.0, 0.0), (-1.4, -0.3), (-0.95, -0.55), (-1.25, -0.8)]
        lines = theme.panel(self.root, (-1.65, -0.62, -0.92, 0.6), color=(0.01, 0.025, 0.05, 0.75))
        self.widgets.append(lines)
        from game.ui.hud import lines_node
        path = lines_node([[(x, y) for x, y in positions]], (0.25, 0.6, 0.9, 0.5), 1.4)
        path.reparentTo(self.root)
        for i, galaxy in enumerate(self.cfg.galaxies):
            unlocked = galaxy["id"] in self.profile.unlocked_galaxies
            x, y = positions[i]
            done = sum(1 for m in galaxy["missions"] if m["id"] in self.profile.completed_missions)
            label = f"{galaxy['name']}\n{done}/{len(galaxy['missions'])}" if unlocked else "Bloqueada"
            color = (0.1, 0.35, 0.55, 0.95) if galaxy["id"] == self.galaxy_id else None
            self.button(label, (x + 0.12, y), self.select_galaxy, 0.5, enabled=unlocked, extra=[galaxy["id"]],
                        scale=0.034, color=color, height=0.1)
        y = -0.83
        bottom = [("Hangar", lambda: app.show_hangar("ships"), True),
                  ("Taller", lambda: app.show_hangar("workshop"), bool(self.profile.flags.get("workshop_unlocked"))),
                  ("Armería", lambda: app.show_hangar("weapons"), True),
                  ("Inventario", lambda: app.show_hangar("inventory"), True),
                  ("Guardar", app.save_game, True),
                  ("Configuración", lambda: app.show_settings(lambda: app.show_map(self.galaxy_id)), True),
                  ("Menú principal", app.show_main_menu, True)]
        for i, (label, fn, enabled) in enumerate(bottom):
            self.button(label, (-0.42 + i * 0.31, y), fn, 0.29, enabled=enabled, scale=0.036)
        if not self.profile.flags.get("workshop_unlocked"):
            self.text("El taller de la estación Orión-7 se abre al completar «Primer vuelo».", (-0.55, -0.93),
                      0.03, DIM)
        self.status = self.text("", (0.5, -0.72), 0.035, GREEN, TextNode.ACenter)
        self.build_details()

    def select_galaxy(self, galaxy_id: str) -> None:
        self.app.show_map(galaxy_id)

    def select_mission(self, mission_id: str) -> None:
        self.mission_id = mission_id
        self.build_details()

    def build_details(self) -> None:
        for widget in self.detail_widgets:
            widget.destroy()
        self.detail_widgets = []
        galaxy = self.cfg.galaxy(self.galaxy_id)

        def add(widget):
            self.detail_widgets.append(widget)
            return widget

        ids = [m["id"] for m in galaxy["missions"]]
        if self.mission_id not in ids:
            pending = [m["id"] for m in galaxy["missions"]
                       if self.profile.is_mission_available(m) and m["id"] not in self.profile.completed_missions]
            self.mission_id = pending[0] if pending else ids[0]
        add(theme.panel(self.root, (-0.55, 1.65, -0.68, 0.66)))
        add(theme.text(self.root, galaxy["name"], (-0.5, 0.58), 0.065, GOLD))
        add(theme.text(self.root, galaxy["description"], (-0.5, 0.5), 0.034, DIM, wordwrap=55))
        diff = galaxy["difficulty"]
        add(theme.text(self.root, f"Nivel de amenaza x{diff['hp_mult']:.2f} · Recompensas x{diff['reward_mult']:.2f}"
                                  f" · Material: {self.cfg.material_name(galaxy['material'])}",
                       (-0.5, 0.41), 0.032, CYAN))
        y = 0.3
        for m in galaxy["missions"]:
            done = m["id"] in self.profile.completed_missions
            available = self.profile.is_mission_available(m)
            status = "Completada" if done else ("Disponible" if available else "Bloqueada")
            kind = "Principal" if m.get("main") else "Secundaria"
            label = f"{m['name']}  ·  {TYPE_NAMES[m['type']]}  ·  {kind}  ·  {status}"
            color = (0.1, 0.35, 0.55, 0.95) if m["id"] == self.mission_id else None
            add(theme.button(self.root, label, (0.05, y), self.select_mission, 1.0, 0.07, 0.032, available, color,
                             [m["id"]], self.click))
            y -= 0.085
        _, m = self.cfg.mission(self.mission_id)
        y -= 0.04
        add(theme.text(self.root, m["name"], (-0.5, y), 0.05, CYAN))
        add(theme.text(self.root, m["description"], (-0.5, y - 0.065), 0.035, TEXT, wordwrap=58))
        rewards = m.get("rewards", {})
        parts = [f"{rewards.get('xp', 0)} XP", f"{fmt(rewards.get('credits', 0))} CR"]
        parts += [f"{v} {self.cfg.material_name(k)}" for k, v in rewards.get("materials", {}).items()]
        if m["type"] == "boss":
            b = self.cfg.bosses[m["params"]["boss"]]["rewards"]
            parts.append(f"+{b['xp']} XP y {fmt(b['credits'])} CR del jefe")
            if b.get("blueprint"):
                parts.append("plano: " + self.cfg.weapons[b["blueprint"]]["name"])
        if rewards.get("blueprint"):
            parts.append("plano: " + self.cfg.weapons[rewards["blueprint"]]["name"])
        if rewards.get("item_rarity"):
            parts.append("componente " + self.cfg.economy["rarities"][rewards["item_rarity"]]["name"].lower())
        if m["id"] in self.profile.completed_missions:
            parts.append("(repetición: 40% y sin planos)")
        add(theme.text(self.root, "Recompensas: " + " · ".join(parts), (-0.5, y - 0.16), 0.032, GOLD, wordwrap=60))
        missing = [r for r in m.get("requires", []) if r not in self.profile.completed_missions]
        if missing:
            names = ", ".join(self.cfg.mission(r)[1]["name"] for r in missing)
            add(theme.text(self.root, f"Requiere completar: {names}", (-0.5, y - 0.24), 0.032, RED))
        ok = self.profile.is_mission_available(m)
        add(theme.button(self.root, "INICIAR MISIÓN", (1.25, -0.6), self.app.start_mission, 0.6, 0.09, 0.045, ok,
                         (0.1, 0.4, 0.25, 0.95), [galaxy["id"], m["id"]], self.click))

    def flash(self, value: str, color=GREEN) -> None:
        self.status.setText(value)
        self.status["fg"] = color

    def destroy(self) -> None:
        for widget in self.detail_widgets:
            widget.destroy()
        super().destroy()


# =============================================================================
class HangarScreen(Screen):
    TABS = [("ships", "Naves"), ("weapons", "Armería"), ("workshop", "Taller"), ("inventory", "Inventario")]

    def __init__(self, app, tab: str = "ships"):
        super().__init__(app, "hangar")
        self.cfg = app.game_config
        self.profile = app.profile
        self.tab = tab
        PilotBar(self)
        self.text("HANGAR · ESTACIÓN ORIÓN-7", (-1.62, 0.72), 0.06, CYAN)
        for i, (key, label) in enumerate(self.TABS):
            enabled = key != "workshop" or self.profile.flags.get("workshop_unlocked")
            color = (0.1, 0.35, 0.55, 0.95) if key == tab else None
            self.button(label, (-1.42 + i * 0.36, 0.6), app.show_hangar, 0.34, enabled, extra=[key], color=color,
                        scale=0.038)
        self.button("Volver al mapa", (1.42, 0.6), lambda: app.show_map(), 0.4, scale=0.038)
        self.status = self.text("", (-0.3, -0.9), 0.036, GREEN, TextNode.ACenter)
        self._stats_panel()
        getattr(self, "_tab_" + tab)()

    def say(self, value: str, ok: bool = True) -> None:
        self.status.setText(value)
        self.status["fg"] = GREEN if ok else RED
        self.app.audio.play("ui_confirm" if ok else "ui_error", 0.5)

    def refresh(self, message: str | None = None, ok: bool = True) -> None:
        self.app.autosave()
        self.app.show_hangar(self.tab, message, ok)

    def _stats_panel(self) -> None:
        st = compute_ship_stats(self.profile, self.cfg)
        ship = self.cfg.ships[self.profile.ship]
        self.panel((0.86, 1.68, -0.82, 0.52))
        evo = evolution(self.profile.level, self.cfg)
        nxt = f"siguiente en nivel {evo.next_level}" if evo.next_level else "etapa máxima"
        self.text(f"Nave activa · Evolución {evo.name} ({nxt})", (0.9, 0.45), 0.03, DIM)
        self.text(f"{ship['name']} {evo.name}", (0.9, 0.38), 0.05, GOLD)
        lo = self.profile.loadout
        weapons = [self.cfg.weapons[w]["name"] if w else "—" for w in (lo["primary"], lo["secondary"], lo["special"])]
        lines = [f"Casco {st.max_hull:.0f}   Escudo {st.max_shield:.0f}", f"Regeneración de escudo {st.shield_regen:.1f}/s",
                 f"Energía {st.max_energy:.0f} (+{st.energy_regen:.1f}/s)", f"Velocidad {st.max_speed:.0f} m/s",
                 f"Impulso x{st.boost_mult:.2f} ({st.boost_cost:.0f} E/s)", f"Aceleración {st.accel:.2f}",
                 f"Giro {st.turn_rate:.0f}°/s  Alabeo {st.roll_rate:.0f}°/s", f"Daño x{st.damage_mult:.2f}",
                 f"Crítico +{st.crit_bonus * 100:.1f}%", f"Misiles {st.missile_capacity}",
                 f"Fijación {st.lock_range:.0f} m en {st.lock_time:.2f} s",
                 f"Drones {st.drone_count} (daño x{st.drone_damage_mult:.2f})",
                 f"Ranuras de componente {len(self.profile.equipped_components)}/{st.component_slots}", "",
                 f"Principal: {weapons[0]}", f"Secundaria: {weapons[1]}", f"Especial: {weapons[2]}"]
        self.text("\n".join(lines), (0.9, 0.29), 0.033, TEXT)

    def _row(self, canvas, y, title, desc, color=TEXT, buttons=()):
        self.w(theme.panel(canvas, (0, 2.32, -0.14, 0), color=theme.PANEL_LIGHT, pos=(-1.66, y)))
        self.w(theme.text(canvas, title, (-1.62, y - 0.045), 0.04, color))
        self.w(theme.text(canvas, desc, (-1.62, y - 0.095), 0.03, DIM, wordwrap=58))
        for i, (label, fn, enabled, extra) in enumerate(buttons):
            btn = theme.button(canvas, label, (0.5 - i * 0.33, y - 0.07), fn, 0.3, 0.07, 0.034, enabled, None, extra,
                               self.click)
            self.w(btn)

    def _tab_ships(self) -> None:
        ships = list(self.cfg.ships.items())
        _, canvas = scrolled(self, (-1.68, 0.8, -0.82, 0.52), len(ships) * 0.16 + 0.02)
        for i, (sid, ship) in enumerate(ships):
            owned = sid in self.profile.owned_ships
            ok, reason = shop.can_buy_ship(self.profile, sid, self.cfg)
            desc = (f"{ship['description']}  Casco {ship['hull']} · Escudo {ship['shield']} · Velocidad "
                    f"{ship['max_speed']} · Giro {ship['turn_rate']}°/s · Ranuras {ship['component_slots']}")
            buttons = []
            if owned:
                buttons.append(("Activa" if self.profile.ship == sid else "Seleccionar", self._select_ship,
                                self.profile.ship != sid, [sid]))
            else:
                buttons.append((f"Comprar {fmt(ship['cost'])}", self._buy_ship, ok, [sid]))
            title = ship["name"] + ("" if owned or ok else f"  ({reason})")
            self._row(canvas, -0.01 - i * 0.16, title, desc, GOLD if self.profile.ship == sid else TEXT, buttons)

    def _select_ship(self, sid):
        shop.select_ship(self.profile, sid)
        slots = int(self.cfg.ships[sid]["component_slots"])
        del self.profile.equipped_components[slots:]
        self.refresh(f"{self.cfg.ships[sid]['name']} lista para el despegue")

    def _buy_ship(self, sid):
        ok, msg = shop.buy_ship(self.profile, sid, self.cfg)
        self.refresh(msg, ok)

    def _tab_weapons(self) -> None:
        weapons = list(self.cfg.player_weapons().items())
        _, canvas = scrolled(self, (-1.68, 0.8, -0.82, 0.52), len(weapons) * 0.16 + 0.02)
        rarities = self.cfg.economy["rarities"]
        for i, (wid, w) in enumerate(weapons):
            unlocked = wid in self.profile.unlocked_weapons
            equipped = self.profile.loadout.get(w["slot"]) == wid
            rate = f"{w['fire_rate']:.1f}/s" if not w.get("cooldown") else f"recarga {w['cooldown']:.0f} s"
            desc = (f"{SLOT_NAMES[w['slot']]} · daño {w['damage']} · {rate} · alcance {w['range']} m · "
                    f"energía {w['energy_cost']} · crítico {w['crit_chance'] * 100:.0f}% · "
                    f"tec. {w['tech_level']} · {rarities[w['rarity']]['name']}. {w.get('description', '')}")
            buttons = []
            if unlocked:
                buttons.append(("Equipada" if equipped else "Equipar", self._equip, not equipped, [wid]))
            else:
                ok, reason = shop.can_unlock_weapon(self.profile, wid, self.cfg)
                cost = w.get("unlock", {}).get("credits", 0)
                buttons.append((f"Desbloquear {fmt(cost)}", self._unlock, ok, [wid]))
                desc = f"[{reason}] " + desc
            color = tuple(rarities[w["rarity"]]["color"]) + (1,)
            self._row(canvas, -0.01 - i * 0.16, w["name"], desc, color, buttons)

    def _equip(self, wid):
        ok, msg = shop.equip_weapon(self.profile, wid, self.cfg)
        self.refresh(msg, ok)

    def _unlock(self, wid):
        ok, msg = shop.unlock_weapon(self.profile, wid, self.cfg)
        self.refresh(msg, ok)

    def _tab_workshop(self) -> None:
        upgrades = list(self.cfg.upgrades.items())
        _, canvas = scrolled(self, (-1.68, 0.8, -0.82, 0.52), len(upgrades) * 0.16 + 0.02)
        for i, (uid, upg) in enumerate(upgrades):
            level = int(self.profile.upgrades.get(uid, 0))
            ok, reason = shop.can_buy_upgrade(self.profile, uid, self.cfg)
            effects = ", ".join(f"{STAT_NAMES.get(e['stat'], e['stat'])} {'+' if e['per_level'] > 0 else ''}"
                                f"{e['per_level'] * (100 if e.get('mode') == 'percent' or e['stat'].endswith('mult') else 1):.1f}"
                                f"{'%' if e.get('mode') == 'percent' or e['stat'].endswith('mult') else ''}"
                                for e in upg["effects"])
            if level < upg["max_level"]:
                credits, mats = shop.upgrade_cost(uid, level + 1, self.cfg)
                cost = f"{fmt(credits)} CR + " + ", ".join(f"{v} {self.cfg.material_name(k)}" for k, v in mats.items())
            else:
                cost = "máximo"
            desc = f"Por nivel: {effects}. Siguiente: {cost}. {'' if ok else reason}"
            bar = "[" + "|" * level + "·" * (upg["max_level"] - level) + "]"
            self._row(canvas, -0.01 - i * 0.16, f"{upg['name']}  {level}/{upg['max_level']}  {bar}", desc,
                      GREEN if level else TEXT, [("Mejorar", self._upgrade, ok, [uid])])

    def _upgrade(self, uid):
        ok, msg = shop.buy_upgrade(self.profile, uid, self.cfg)
        self.refresh(msg, ok)

    def _tab_inventory(self) -> None:
        items = self.profile.inventory
        slots = compute_ship_stats(self.profile, self.cfg).component_slots
        self.text(f"Componentes equipados {len(self.profile.equipped_components)}/{slots} · "
                  f"Inventario {len(items)}/{self.cfg.economy['inventory_limit']}", (-1.66, 0.48), 0.034, DIM)
        if not items:
            self.text("Aún no tienes componentes. Se consiguen al destruir enemigos (sobre todo élites y jefes) "
                      "y como recompensa de misiones.", (-1.6, 0.3), 0.038, TEXT, wordwrap=50)
            return
        _, canvas = scrolled(self, (-1.68, 0.8, -0.82, 0.44), len(items) * 0.16 + 0.02)
        rarities = self.cfg.economy["rarities"]
        order = {r: i for i, r in enumerate(rarities)}
        for i, item in enumerate(sorted(items, key=lambda it: (-order[it["rarity"]], it["name"]))):
            equipped = item["id"] in self.profile.equipped_components
            buttons = [("Quitar" if equipped else "Equipar", self._toggle_item, True, [item["id"]]),
                       (f"Vender {sell_value(item, self.cfg)}", self._sell, True, [item["id"]])]
            color = tuple(rarities[item["rarity"]]["color"]) + (1,)
            self._row(canvas, -0.01 - i * 0.16, describe_item(item, self.cfg) + ("  [EQUIPADO]" if equipped else ""),
                      "Mejora pasiva mientras está equipado.", color, buttons)

    def _toggle_item(self, item_id):
        if item_id in self.profile.equipped_components:
            unequip_component(self.profile, item_id)
            self.refresh("Componente retirado")
        else:
            slots = compute_ship_stats(self.profile, self.cfg).component_slots
            ok, msg = equip_component(self.profile, item_id, slots)
            self.refresh(msg, ok)

    def _sell(self, item_id):
        value = sell_item(self.profile, item_id, self.cfg)
        self.refresh(f"Vendido por {value} CR")


# =============================================================================
class SettingsScreen(Screen):
    PRESETS = [("low", "Bajo"), ("medium", "Medio"), ("high", "Alto")]
    FPS = [30, 60, 120, 144]

    def __init__(self, app, back):
        super().__init__(app, "settings")
        self.back = back
        self.s = app.settings
        self.capture_action = None
        self.panel((-1.6, 1.6, -0.82, 0.8))
        self.text("CONFIGURACIÓN", (0, 0.68), 0.07, CYAN, TextNode.ACenter)
        self.text("Gráficos", (-1.5, 0.55), 0.05, GOLD)
        preset = dict(self.PRESETS)[self.s["graphics_preset"]]
        self.button(f"Calidad: {preset}", (-1.15, 0.45), self._cycle_preset, 0.62)
        bloom = self.s.quality()["bloom"]
        self.button(f"Bloom y HDR: {'Sí' if bloom else 'No'}", (-1.15, 0.35), self._toggle_bloom, 0.62)
        self.button(f"Pantalla completa: {'Sí' if self.s['fullscreen'] else 'No'}", (-1.15, 0.25),
                    self._toggle, 0.62, extra=["fullscreen"])
        self.button(f"FPS objetivo: {self.s['fps_target']}", (-1.15, 0.15), self._cycle_fps, 0.62)
        self.button(f"Mostrar FPS (F3): {'Sí' if self.s['show_fps'] else 'No'}", (-1.15, 0.05), self._toggle, 0.62,
                    extra=["show_fps"])
        self.text("Campo de visión", (-1.46, -0.07), 0.035, DIM)
        self.fov_label = self.text(f"{self.s['fov']:.0f}°", (-0.85, -0.07), 0.035, TEXT)
        self.slider((-1.15, -0.13), self.s["fov"], self._fov, 0.6, (60, 95))
        self.text("El suavizado (MSAA) y la calidad de texturas se aplican al reiniciar o en la siguiente misión.",
                  (-1.5, -0.25), 0.027, DIM, wordwrap=26)

        self.text("Audio", (-0.38, 0.55), 0.05, GOLD)
        self.vol_labels = {}
        for i, (key, label) in enumerate((("master", "General"), ("music", "Música"), ("sfx", "Efectos"))):
            y = 0.44 - i * 0.14
            self.text(label, (-0.38, y), 0.036, DIM)
            self.vol_labels[key] = self.text(f"{self.s[key] * 100:.0f}%", (0.3, y), 0.036, TEXT, TextNode.ARight)
            self.slider((-0.04, y - 0.05), self.s[key], lambda v, k=key: self._volume(k, v), 0.62)

        self.text("Controles", (-0.38, 0.0), 0.05, GOLD)
        self.text("Sensibilidad del ratón", (-0.38, -0.1), 0.034, DIM)
        self.sens_label = self.text(f"{self.s['mouse_sensitivity']:.2f}", (0.3, -0.1), 0.034, TEXT, TextNode.ARight)
        self.slider((-0.04, -0.15), self.s["mouse_sensitivity"], self._sens, 0.62, (0.2, 3.0))
        self.button(f"Invertir eje Y: {'Sí' if self.s['invert_y'] else 'No'}", (-0.04, -0.27), self._toggle, 0.62,
                    extra=["invert_y"])
        self.button(f"Mando: {'Activado' if self.s['gamepad_enabled'] else 'Desactivado'}", (-0.04, -0.37),
                    self._toggle, 0.62, extra=["gamepad_enabled"])

        self.text("Asignación de teclas (clic para cambiar)", (0.45, 0.55), 0.04, GOLD)
        names = app.game_config.controls["action_names"]
        self.bind_buttons = {}
        for i, (action, keys) in enumerate(self.s["bindings"].items()):
            y = 0.46 - i * 0.073
            self.text(names.get(action, action), (0.45, y - 0.012), 0.03, DIM)
            self.bind_buttons[action] = self.button(", ".join(keys), (1.33, y), self._start_capture, 0.42,
                                                    extra=[action], scale=0.03, height=0.06)
        self.capture_label = self.text("", (0.95, -0.74), 0.034, ORANGE, TextNode.ACenter)
        self.button("Restablecer teclas", (-0.95, -0.72), self._reset_keys, 0.5)
        self.button("Guardar y volver", (-0.3, -0.72), self._back, 0.5)
        self.accept("raw-button-down", self._captured)

    def _apply(self, rebuild: bool = False) -> None:
        self.app.apply_settings()
        if rebuild:
            self.app.show_settings(self.back)

    def _cycle_preset(self):
        keys = [k for k, _ in self.PRESETS]
        self.s["graphics_preset"] = keys[(keys.index(self.s["graphics_preset"]) + 1) % len(keys)]
        self.s["bloom"] = None
        self._apply(True)

    def _toggle_bloom(self):
        self.s["bloom"] = not self.s.quality()["bloom"]
        self._apply(True)

    def _toggle(self, key):
        self.s[key] = not self.s[key]
        self._apply(True)

    def _cycle_fps(self):
        i = self.FPS.index(self.s["fps_target"]) if self.s["fps_target"] in self.FPS else 0
        self.s["fps_target"] = self.FPS[(i + 1) % len(self.FPS)]
        self._apply(True)

    def _fov(self, value):
        self.s["fov"] = float(round(value))
        self.fov_label.setText(f"{self.s['fov']:.0f}°")

    def _volume(self, key, value):
        self.s[key] = round(value, 2)
        self.vol_labels[key].setText(f"{self.s[key] * 100:.0f}%")
        self.app.audio.apply_volumes()

    def _sens(self, value):
        self.s["mouse_sensitivity"] = round(value, 2)
        self.sens_label.setText(f"{self.s['mouse_sensitivity']:.2f}")

    def _start_capture(self, action):
        self.capture_action = action
        self.capture_label.setText(f"Pulsa la nueva tecla para «{self.app.game_config.controls['action_names'][action]}»")
        self.app.buttonThrowers[0].node().setButtonDownEvent("raw-button-down")

    def _captured(self, key):
        if self.capture_action is None:
            return
        if key.startswith("mouse") and key not in ("mouse1", "mouse2", "mouse3"):
            return
        action = self.capture_action
        self.capture_action = None
        self.app.buttonThrowers[0].node().setButtonDownEvent("")
        self.s["bindings"][action] = [key]
        self.capture_label.setText(f"Asignado: {key}")
        self.bind_buttons[action]["text"] = key
        self.app.controller.reload_bindings()

    def _reset_keys(self):
        self.s["bindings"] = copy.deepcopy(self.app.game_config.controls["bindings"])
        self.app.controller.reload_bindings()
        self._apply(True)

    def _back(self):
        self.app.buttonThrowers[0].node().setButtonDownEvent("")
        self.app.apply_settings()
        self.s.save()
        self.back()


# =============================================================================
class PauseScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "pause")
        self.w(DirectFrame(parent=self.root, frameColor=(0, 0, 0, 0.55), frameSize=(-3, 3, -2, 2)))
        self.panel((-0.62, 0.62, -0.62, 0.55))
        self.text("PAUSA", (0, 0.42), 0.08, CYAN, TextNode.ACenter)
        self.button("Reanudar", (0, 0.24), app.toggle_pause, 0.6)
        self.button("Configuración", (0, 0.12), lambda: app.show_settings(app.show_pause), 0.6)
        self.button("Abandonar misión", (0, 0.0), self._abort, 0.6)
        ctrl = ("Ratón: apuntar · Clic izq.: disparar · Clic der.: secundaria · F: especial\n"
                "W/S: acelerar/frenar · A/D: desplazar · Q/E: alabeo · Shift: impulso\n"
                "Espacio: evasión · Tab/T: objetivo · R: cambiar arma · F3: rendimiento")
        self.text(ctrl, (0, -0.16), 0.03, DIM, TextNode.ACenter, wordwrap=40)

    def _abort(self):
        ConfirmDialog(self.app, "¿Abandonar la misión? Conservarás la mitad de lo ganado en combate.",
                      self.app.abort_mission)


class SummaryScreen(Screen):
    def __init__(self, app, result: dict, outcome: dict):
        super().__init__(app, "summary")
        cfg = app.game_config
        success = result["success"]
        self.panel((-1.05, 1.05, -0.82, 0.78))
        if success:
            self.text("MISIÓN CUMPLIDA", (0, 0.62), 0.085, GREEN, TextNode.ACenter)
        else:
            self.text("DERROTA" if result.get("player_died") else "MISIÓN FALLIDA", (0, 0.62), 0.085, RED,
                      TextNode.ACenter)
            self.text(result.get("reason", ""), (0, 0.53), 0.04, ORANGE, TextNode.ACenter)
        self.text(f"{result['galaxy']['name']} · {result['mission']['name']}", (0, 0.45), 0.042, DIM, TextNode.ACenter)
        r = outcome["rewards"]
        lines = [f"Experiencia  +{r['xp']} XP", f"Créditos  +{fmt(r['credits'])} CR"]
        for mat, amount in r["materials"].items():
            lines.append(f"{cfg.material_name(mat)}  +{amount}")
        for bp in r["blueprints"]:
            lines.append(f"Plano de arma: {cfg.weapons[bp]['name']} (desbloquéalo en la Armería)")
        for item in r["items"]:
            lines.append("Componente: " + describe_item(item, cfg))
        lines.append("")
        lines.append(f"Enemigos destruidos: {result['kills']}    Tiempo: {result['time']:.0f} s")
        if not success:
            lines.append("Conservas la mitad de lo ganado en combate.")
        self.text("\n".join(lines), (-0.95, 0.33), 0.038, TEXT, wordwrap=50)
        y = -0.45
        for level in outcome["levels"]:
            self.text(f"¡Nivel de piloto {level} alcanzado!", (0, y), 0.045, GOLD, TextNode.ACenter)
            y -= 0.06
        for evo in outcome.get("evolutions", []):
            self.text(f"¡Tu nave evoluciona a {evo.name}! {evo.summary}", (0, y), 0.038, CYAN, TextNode.ACenter,
                      wordwrap=48)
            y -= 0.1
        events = outcome.get("events", {})
        if events.get("galaxy_unlocked"):
            name = cfg.galaxy(events["galaxy_unlocked"])["name"]
            self.text(f"Nueva galaxia desbloqueada: {name}", (0, y), 0.045, MAGENTA, TextNode.ACenter)
        if events.get("campaign_complete"):
            self.button("Ver el final", (0, -0.72), app.show_victory, 0.6)
        elif success:
            self.button("Continuar", (0, -0.72), lambda: app.show_map(result["galaxy"]["id"]), 0.5)
        else:
            self.button("Reintentar", (-0.3, -0.72), app.start_mission, 0.5,
                        extra=[result["galaxy"]["id"], result["mission"]["id"]])
            self.button("Mapa galáctico", (0.3, -0.72), lambda: app.show_map(result["galaxy"]["id"]), 0.5)


class VictoryScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "victory")
        p = app.profile
        self.panel((-1.2, 1.2, -0.8, 0.8))
        self.text("¡LA GALAXIA ES LIBRE!", (0, 0.6), 0.1, GOLD, TextNode.ACenter)
        story = ("El Soberano del Vacío ha caído y su núcleo se apaga. Las cinco galaxias vuelven a estar "
                 "abiertas al comercio y a la exploración. Tu nombre se recordará en cada estación de la Alianza.")
        self.text(story, (0, 0.42), 0.042, TEXT, TextNode.ACenter, wordwrap=44)
        stats = (f"Piloto {p.name} · Nivel {p.level}\nEnemigos destruidos: {p.stats.get('kills', 0)}\n"
                 f"Jefes derrotados: {p.stats.get('bosses', 0)}\nMisiones completadas: {p.stats.get('missions', 0)}\n"
                 f"Tiempo de vuelo: {p.stats.get('play_time', 0) / 60:.0f} min")
        self.text(stats, (0, 0.05), 0.045, CYAN, TextNode.ACenter)
        self.text("Puedes seguir jugando: repite misiones para mejorar tu nave al máximo.", (0, -0.45), 0.036, DIM,
                  TextNode.ACenter)
        self.button("Volver al mapa", (0, -0.65), lambda: app.show_map(), 0.55)


class LoadingScreen(Screen):
    def __init__(self, app, title: str):
        super().__init__(app, "loading")
        self.text(title, (0, 0.1), 0.07, CYAN, TextNode.ACenter)
        self.step = self.text("", (0, -0.02), 0.04, DIM, TextNode.ACenter)
        self.bar = Bar(self.root, (-0.6, -0.12), 1.2, 0.015, CYAN)
        self.widgets.append(self.bar)

    def set(self, step: str, progress: float) -> None:
        self.step.setText(step)
        self.bar.set(progress)
