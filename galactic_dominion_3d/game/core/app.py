"""Aplicación principal: ventana, estados del juego y transiciones.

Estados: menú principal → selección de ranura → mapa galáctico ⇄ hangar →
misión (carga con salto hiperespacial) → resumen → mapa... El progreso se
guarda automáticamente al terminar cada misión y tras cada compra.
"""
from __future__ import annotations

import logging
import math
import random
import traceback

from direct.showbase.ShowBase import ShowBase
from panda3d.core import ClockObject, Point3, WindowProperties, loadPrcFileData

from game.audio.manager import AudioManager
from game.core.config import GameConfig
from game.core.flight import FlightSession
from game.core.paths import saves_dir
from game.core.settings import Settings
from game.galaxies.scene import GalaxyScene
from game.graphics import models
from game.graphics.overlay import Overlays
from game.graphics.postfx import PostFX
from game.missions.mission import apply_rewards, complete_mission, empty_rewards, merge_rewards, mission_rewards
from game.persistence.save_manager import SaveManager
from game.player.controller import Controller
from game.progression.evolution import tier_changes, tier_for_level
from game.progression.profile import PlayerProfile
from game.ui import menus, theme

log = logging.getLogger("galactic_dominion")


def configure_window(settings: Settings) -> None:
    quality = settings.quality()
    lines = [
        "window-title GALACTIC DOMINION 3D",
        f"win-size {settings['width']} {settings['height']}",
        f"fullscreen {'#t' if settings['fullscreen'] else '#f'}",
        "win-origin -2 -2",
        "win-fixed-size #f",
        f"sync-video {'#t' if settings['vsync'] else '#f'}",
        "textures-power-2 none",
        "show-frame-rate-meter #f",
        "audio-library-name p3openal_audio",
        "notify-level warning",
        "default-directnotify-level warning",
        "model-cache-dir",
    ]
    if quality["msaa"] and not quality["bloom"]:
        lines += ["framebuffer-multisample #t", f"multisamples {int(quality['msaa'])}"]
    loadPrcFileData("galactic-dominion", "\n".join(lines))


class MenuBackdrop:
    """Escena 3D detrás de los menús: la galaxia actual y la nave del jugador."""

    def __init__(self, app, galaxy_id: str, ship_id: str, tier: int = 1):
        self.app = app
        quality = dict(app.settings.quality())
        quality["shadows"] = False
        self.scene = GalaxyScene(app, app.game_config.galaxy(galaxy_id), quality, {"type": "menu"}, seed=7)
        self.steps = self.scene.build_steps()
        self.ready = False
        self.ship = models.build_player_ship(app.game_config.ships[ship_id]["model"], tier=tier).root
        self.ship.reparentTo(app.render)
        self.ship.setPos(0, 0, 0)
        self.time = random.uniform(0, 10)

    def update(self, dt: float) -> None:
        if not self.ready:
            try:
                next(self.steps)
            except StopIteration:
                self.ready = True
            return
        self.time += dt
        a = self.time * 0.08
        cam = self.app.camera
        cam.setPos(math.cos(a) * 26, math.sin(a) * 26 - 4, 6 + math.sin(self.time * 0.2) * 2)
        cam.lookAt(Point3(0, 0, 0))
        cam.setH(cam, 24)  # desplaza la vista: la nave queda a la derecha del menú
        self.ship.setHpr(self.time * 4, math.sin(self.time * 0.5) * 5, math.sin(self.time * 0.3) * 8)
        self.scene.update(dt, cam.getPos(self.app.render), Point3(0, 0, 0))

    def destroy(self) -> None:
        self.ship.removeNode()
        self.scene.destroy()


class GameApp(ShowBase):
    def __init__(self):
        self.game_config = GameConfig()
        self.saves_path = saves_dir()
        self.settings = Settings(self.game_config, self.saves_path / "settings.json")
        configure_window(self.settings)
        super().__init__()
        self.disableMouse()
        self.render.setShaderAuto()
        self.setBackgroundColor(0.01, 0.01, 0.02, 1)
        self.warnings: list[str] = [self.settings.warning] if self.settings.warning else []
        theme.load_font(self.loader)
        loading = menus.LoadingScreen(self, "GALACTIC DOMINION 3D")
        loading.set("Generando sonidos y música (solo la primera vez)...", 0.1)
        self.graphicsEngine.renderFrame()
        self.graphicsEngine.renderFrame()
        self.audio = AudioManager(self, self.settings, self.game_config.audio)
        loading.destroy()
        self.saves = SaveManager(self.saves_path, self.game_config)
        self.controller = Controller(self, self.settings)
        self.overlays = Overlays(self)
        self.postfx = None
        self.profile: PlayerProfile | None = None
        self.slot: int | None = None
        self.screen = None
        self.session: FlightSession | None = None
        self.loader_task = None
        self.backdrop: MenuBackdrop | None = None
        self.backdrop_key = None
        self.jump_fade = 0.0
        self.layout_key = None
        self.apply_settings()
        self.exitFunc = self._on_exit
        self.taskMgr.add(self._update, "game-update", sort=10)
        self.show_main_menu()

    # --- ajustes ------------------------------------------------------------
    def apply_settings(self) -> None:
        s = self.settings
        self.audio.apply_volumes()
        clock = ClockObject.getGlobalClock()
        clock.setMode(ClockObject.MLimited)
        clock.setFrameRate(int(s["fps_target"]))
        quality = s.quality()
        wanted = bool(quality["bloom"])
        if self.postfx is None or self.postfx.enabled != wanted:
            if self.postfx is not None:
                self.postfx.cleanup()
            self.postfx = PostFX(self, int(quality["msaa"]), wanted)
            if wanted and not self.postfx.enabled:
                self.warnings.append(f"El bloom/HDR no está disponible en esta tarjeta gráfica: {self.postfx.error}")
                log.warning("PostFX desactivado: %s", self.postfx.error)
        props = WindowProperties()
        props.setFullscreen(bool(s["fullscreen"]))
        if s["fullscreen"]:
            props.setSize(self.pipe.getDisplayWidth(), self.pipe.getDisplayHeight())
        else:
            props.setSize(int(s["width"]), int(s["height"]))
        if self.win:
            # solo se fuerza el tamaño si cambió en el menú: si el jugador arrastró el borde, se respeta
            wanted_size = (int(s["width"]), int(s["height"]))
            size_changed = not s["fullscreen"] and wanted_size != getattr(self, "applied_size", wanted_size)
            if self.win.getProperties().getFullscreen() != bool(s["fullscreen"]) or size_changed:
                self.win.requestProperties(props)
            self.applied_size = wanted_size
        self.controller.reload_bindings()
        self.controller.refresh_gamepad()
        self.camLens.setFov(float(s["fov"]))

    # --- adaptación a la pantalla --------------------------------------------
    def ui_factor(self) -> float:
        """Escala de la interfaz: los menús se diseñaron para 16:9; en pantallas más estrechas
        (4:3, 16:10, teléfonos en vertical) se reducen para que nada quede fuera."""
        aspect = self.getAspectRatio() if self.win else 16 / 9
        return float(self.settings["ui_scale"]) * min(1.0, aspect / (16 / 9))

    def _check_layout(self) -> None:
        if not self.win:
            return
        key = (self.win.getXSize(), self.win.getYSize(), float(self.settings["ui_scale"]))
        if key == self.layout_key:
            return
        self.layout_key = key
        factor = self.ui_factor()
        if self.screen is not None:
            self.screen.root.setScale(factor)
        if self.session is not None and getattr(self.session, "hud", None) is not None:
            self.session.hud.set_scale(factor)

    # --- pantallas ----------------------------------------------------------
    def _set_screen(self, screen) -> None:
        if self.screen is not None:
            self.screen.destroy()
        self.screen = screen

    def _ensure_backdrop(self) -> None:
        galaxy = self.profile.current_galaxy if self.profile else self.game_config.galaxies[0]["id"]
        ship = self.profile.ship if self.profile else self.game_config.start_ship
        tier = tier_for_level(self.profile.level, self.game_config) if self.profile else 1
        key = (galaxy, ship, tier)
        if self.backdrop is not None and self.backdrop_key == key:
            return
        if self.backdrop is not None:
            self.backdrop.destroy()
        self.backdrop = MenuBackdrop(self, galaxy, ship, tier)
        self.backdrop_key = key

    def _drop_backdrop(self) -> None:
        if self.backdrop is not None:
            self.backdrop.destroy()
            self.backdrop = None
            self.backdrop_key = None

    def show_main_menu(self) -> None:
        self.autosave()
        self.profile = None
        self.slot = None
        self._ensure_backdrop()
        self.audio.play_music("ambient_orion")
        self._set_screen(menus.MainMenu(self, self.warnings))

    def show_credits(self) -> None:
        self._set_screen(menus.CreditsScreen(self))

    def show_slots(self, mode: str) -> None:
        self._set_screen(menus.SlotScreen(self, mode))

    def show_map(self, galaxy_id: str | None = None) -> None:
        if galaxy_id and galaxy_id in self.profile.unlocked_galaxies:
            self.profile.current_galaxy = galaxy_id
        self._ensure_backdrop()
        self.audio.play_music(self.game_config.galaxy(self.profile.current_galaxy)["music"])
        self._set_screen(menus.GalaxyMap(self, self.profile.current_galaxy))

    def show_hangar(self, tab: str = "ships", message: str | None = None, ok: bool = True) -> None:
        self._ensure_backdrop()
        screen = menus.HangarScreen(self, tab)
        self._set_screen(screen)
        if message:
            screen.say(message, ok)

    def show_settings(self, back) -> None:
        self._set_screen(menus.SettingsScreen(self, back))

    def show_victory(self) -> None:
        self._set_screen(menus.VictoryScreen(self))

    # --- partidas -----------------------------------------------------------
    def new_game(self, slot: int, name: str) -> None:
        self.profile = PlayerProfile.new(self.game_config, name[:24])
        self.slot = slot
        self.saves.save(slot, self.profile)
        log.info("Nueva partida en la ranura %s", slot)
        self.show_map()

    def load_game(self, slot: int | None) -> None:
        if slot is None:
            return
        profile, warnings = self.saves.load(slot)
        self.warnings += warnings
        if profile is None:
            self.warnings.append(f"No se pudo cargar la ranura {slot}.")
            self.show_main_menu()
            return
        self.profile, self.slot = profile, slot
        self.show_map()

    def save_game(self) -> None:
        self.autosave()
        if isinstance(self.screen, menus.GalaxyMap):
            self.screen.flash(f"Partida guardada en la ranura {self.slot}")
        self.audio.play("ui_confirm", 0.5)

    def autosave(self) -> None:
        if self.profile is not None and self.slot is not None:
            try:
                self.saves.save(self.slot, self.profile)
            except OSError as exc:
                log.error("No se pudo guardar: %s", exc)
                self.warnings.append(f"No se pudo guardar la partida: {exc}")

    # --- misiones -----------------------------------------------------------
    def start_mission(self, galaxy_id: str, mission_id: str) -> None:
        self._set_screen(None)
        self._drop_backdrop()
        self.profile.current_galaxy = galaxy_id
        galaxy = self.game_config.galaxy(galaxy_id)
        self.audio.play("jump", 0.8)
        self.audio.stop_music()
        self.session = FlightSession(self, galaxy_id, mission_id)
        screen = menus.LoadingScreen(self, f"Saltando a {galaxy['name']}")
        self._set_screen(screen)
        self.loader_task = {"steps": self.session.build_steps(), "count": 0, "total": 12 + len(
            galaxy["environment"].get("planets", [])), "screen": screen, "galaxy": galaxy}
        self.overlays.set_jump(1.0, galaxy["environment"]["nebula_colors"][0])

    def _step_loading(self) -> None:
        task = self.loader_task
        try:
            label = next(task["steps"])
            task["count"] += 1
            task["screen"].set(label, task["count"] / task["total"])
        except StopIteration:
            self.loader_task = None
            self._set_screen(None)
            self.jump_fade = 1.0

    def toggle_pause(self) -> None:
        s = self.session
        if s is None or s.state not in ("combat",):
            return
        s.paused = not s.paused
        if s.paused:
            self.controller.capture(False)
            self.audio.stop_engine()
            self._set_screen(menus.PauseScreen(self))
        else:
            self._set_screen(None)
            self.controller.capture(True)
            self.audio.start_engine()

    def show_pause(self) -> None:
        self._set_screen(menus.PauseScreen(self))

    def abort_mission(self) -> None:
        if self.session is None:
            return
        self.session.mission.fail("Misión abandonada")
        result = self.session._result()
        self.on_mission_end(result)

    def on_mission_end(self, result: dict) -> None:
        session, self.session = self.session, None
        if session is not None:
            session.destroy()
        self._set_screen(None)
        profile = self.profile
        galaxy, mission = result["galaxy"], result["mission"]
        rng = random.Random()
        events = {}
        if result["success"]:
            first = mission["id"] not in profile.completed_missions
            total = merge_rewards(empty_rewards(), result["earned"])
            merge_rewards(total, mission_rewards(galaxy, mission, rng, self.game_config, first_time=first))
            events = complete_mission(profile, galaxy, mission, self.game_config)
        else:
            earned = result["earned"]
            total = {"xp": earned["xp"] // 2, "credits": earned["credits"] // 2,
                     "materials": {k: v // 2 for k, v in earned["materials"].items()},
                     "blueprints": [], "items": list(earned["items"])}
            if result.get("player_died"):
                profile.stats["deaths"] = profile.stats.get("deaths", 0) + 1
        old_level = profile.level
        applied = apply_rewards(profile, total, self.game_config)
        evolutions = tier_changes(old_level, profile.level, self.game_config)
        profile.stats["kills"] = profile.stats.get("kills", 0) + int(result["kills"])
        profile.stats["play_time"] = profile.stats.get("play_time", 0.0) + float(result["time"])
        if events.get("galaxy_unlocked"):
            profile.current_galaxy = events["galaxy_unlocked"]
        self.autosave()
        if applied["levels"]:
            self.audio.play("level_up", 0.7)
        if evolutions:
            self.audio.play("lock_done", 0.7)
        log.info("Fin de misión %s: %s", mission["id"], "éxito" if result["success"] else "fallo")
        self._ensure_backdrop()
        self.audio.play_music(galaxy["music"])
        self._set_screen(menus.SummaryScreen(self, result, {"rewards": total, "levels": applied["levels"],
                                                             "events": events, "evolutions": evolutions}))

    # --- bucle --------------------------------------------------------------
    def _update(self, task):
        dt = ClockObject.getGlobalClock().getDt()
        self._check_layout()
        try:
            if self.loader_task is not None:
                self._step_loading()
            elif self.session is not None:
                if self.jump_fade > 0:
                    self.jump_fade = max(0.0, self.jump_fade - dt * 1.2)
                    self.overlays.set_jump(self.jump_fade)
                self.session.update(dt)
            if self.backdrop is not None:
                self.backdrop.update(dt)
        except Exception:  # noqa: BLE001 - un error en mitad de la partida no debe cerrar el juego
            log.error("Error durante la partida:\n%s", traceback.format_exc())
            self.warnings.append("Se produjo un error interno; se guardó el detalle en saves/game.log.")
            self._recover()
        return task.cont

    def _recover(self) -> None:
        session, self.session = self.session, None
        self.loader_task = None
        if session is not None:
            try:
                session.destroy()
            except Exception:  # noqa: BLE001
                log.error("Error al limpiar la sesión:\n%s", traceback.format_exc())
        if self.profile is not None:
            self.show_map()
        else:
            self.show_main_menu()

    def quit_game(self) -> None:
        self.userExit()

    def _on_exit(self) -> None:
        self.autosave()
        if self.win and not self.settings["fullscreen"]:  # recuerda el tamaño elegido arrastrando el borde
            self.settings["width"], self.settings["height"] = self.win.getXSize(), self.win.getYSize()
        try:
            self.settings.save()
        except OSError:
            pass
        log.info("Juego cerrado")
