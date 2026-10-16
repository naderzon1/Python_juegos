"""Prueba automática del juego real (ventana, render, audio y lógica completos).

Un piloto automático juega las misiones indicadas; además se recorren los
menús. Las partidas se guardan en una carpeta temporal, nunca en ``saves/``.

    python tools/smoke_test.py                       # recorrido rápido
    python tools/smoke_test.py --all                 # todas las misiones de la campaña
    python tools/smoke_test.py --shots carpeta       # guarda capturas de pantalla
    python tools/smoke_test.py --plan orion_boss     # solo las misiones indicadas
    python tools/smoke_test.py --plan orion_patrol --level 16   # con la nave en etapa Mk V
    python tools/smoke_test.py --plan orion_tutorial --size 1024x768 --shots c   # otra pantalla
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["GD_SAVES_DIR"] = tempfile.mkdtemp(prefix="gd_smoke_")

from panda3d.core import ClockObject, Filename  # noqa: E402

from game.core.app import GameApp  # noqa: E402
from game.player.controller import InputState  # noqa: E402


class Autopilot:
    def __init__(self, app):
        self.app = app
        self.t = 0.0
        self.retarget = 0.0

    def poll(self) -> InputState:
        inp = InputState()
        s = self.app.session
        if s is None or s.player is None or not s.player.alive:
            return inp
        self.t += 1 / 30
        p = s.player
        self.retarget -= 1 / 30
        if self.retarget <= 0:
            inp.pressed.add("target_nearest")
            self.retarget = 1.5
        goal = None
        if s.target is not None and s.target.alive:
            goal = s.target.pos + (s.target.velocity - p.velocity) * ((s.target.pos - p.pos).length() / 950)
        if s.pods and (goal is None or (goal - p.pos).length() > 500 or int(self.t / 8) % 2 == 0):
            goal = min(s.pods, key=lambda pod: (pod.pos - p.pos).length()).pos
        if goal is None and s.allies:
            goal = s.allies[0].pos
        if goal is None:
            inp.thrust = 0.3
            return inp
        local = p.node.getRelativePoint(s.world.render, goal)
        dist = local.length()
        yaw = math.degrees(math.atan2(-local.x, local.y))
        pitch = math.degrees(math.atan2(local.z, math.hypot(local.x, local.y)))
        inp.yaw = max(-6, min(6, yaw * 0.4))
        inp.pitch = max(-6, min(6, pitch * 0.4))
        aligned = abs(yaw) < 7 and abs(pitch) < 7
        chasing_pod = bool(s.pods) and goal == min(s.pods, key=lambda pod: (pod.pos - p.pos).length()).pos
        inp.thrust = 1.0 if (dist > 450 or chasing_pod) else (-1.0 if p.throttle > 0.35 else 0.0)
        inp.fire_primary = aligned and dist < 1500 and s.target is not None
        inp.fire_secondary = p.locked and int(self.t) % 3 == 0
        if s.projectiles.incoming_missiles(p) and int(self.t * 2) % 4 == 0:
            inp.pressed.add("evade")
        if s.target is not None and s.target.boss and int(self.t) % 9 == 0:
            inp.pressed.add("fire_special")
        return inp


def frames(app, n: int, shot_dir: Path | None = None, shot_name: str | None = None, shot_every: int = 0):
    for i in range(n):
        app.taskMgr.step()
        if shot_dir and shot_every and i % shot_every == shot_every - 1:
            save_shot(app, shot_dir, f"{shot_name}_{i // shot_every}")


def save_shot(app, folder: Path, name: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    app.win.saveScreenshot(Filename.fromOsSpecific(str(folder / f"{name}.png")))


def run_mission(app, galaxy_id: str, mission_id: str, seconds: float, shots: Path | None, godmode: bool) -> dict:
    app.start_mission(galaxy_id, mission_id)
    loading_frames = 0
    while app.loader_task is not None and loading_frames < 400:
        app.taskMgr.step()
        loading_frames += 1
    s = app.session
    assert s is not None and s.state == "combat", "la misión no llegó a cargar"
    if godmode:
        s.player.durability.invulnerable = True
    real0 = time.perf_counter()
    count = 0
    limit = int(seconds * 30)
    shot_every = max(1, limit // 3)
    while app.session is s and count < limit:
        if godmode and s.player.alive:
            s.player.durability.invulnerable = True
            s.player.energy = s.player.stats.max_energy
        app.taskMgr.step()
        count += 1
        if shots and count % shot_every == 0 and app.session is s:
            save_shot(app, shots, f"{mission_id}_{count // shot_every}")
    real = time.perf_counter() - real0
    info = {"mission": mission_id, "state": s.mission.state, "kills": s.kills, "sim_s": round(count / 30, 1),
            "fps": round(count / max(real, 1e-3), 1), "loading_frames": loading_frames,
            "ended": app.session is not s, "boss": bool(s.boss)}
    if app.session is s:  # no terminó en el tiempo dado: abandonamos para seguir
        app.abort_mission()
    frames(app, 3)
    if shots:
        save_shot(app, shots, f"{mission_id}_summary")
    return info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--shots", default="")
    parser.add_argument("--seconds", type=float, default=150)
    parser.add_argument("--plan", default="", help="misiones separadas por comas, p. ej. orion_boss,void_boss")
    parser.add_argument("--level", type=int, default=0, help="nivel inicial del piloto (prueba la evolución Mk)")
    parser.add_argument("--size", default="", help="resolución de la ventana, p. ej. 1024x768 o 2560x1080")
    args = parser.parse_args()
    shots = Path(args.shots) if args.shots else None
    log_file = Path(os.environ["GD_SAVES_DIR"]) / "game.log"
    if args.size:
        w, h = (int(v) for v in args.size.lower().split("x"))
        (Path(os.environ["GD_SAVES_DIR"]) / "settings.json").write_text(
            json.dumps({"width": w, "height": h}), encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_file, encoding="utf-8")])
    app = GameApp()
    clock = ClockObject.getGlobalClock()
    clock.setMode(ClockObject.MNonRealTime)  # paso fijo: la simulación no depende de la velocidad real
    clock.setFrameRate(30)
    auto = Autopilot(app)
    app.controller.poll = auto.poll
    report = []
    try:
        frames(app, 40)
        if shots:
            save_shot(app, shots, "menu_main")
        app.new_game(1, "Piloto automático")
        if args.level:
            app.profile.level = args.level
        frames(app, 30)
        if shots:
            save_shot(app, shots, "menu_map")
        for tab in ("ships", "weapons", "workshop", "inventory"):
            app.profile.flags["workshop_unlocked"] = True
            app.show_hangar(tab)
            frames(app, 5)
            if shots:
                save_shot(app, shots, f"menu_hangar_{tab}")
        app.show_settings(app.show_map)
        frames(app, 5)
        if shots:
            save_shot(app, shots, "menu_settings")
        app.show_map()
        frames(app, 5)
        if args.plan:
            plan = [(app.game_config.mission(m)[0]["id"], m) for m in args.plan.split(",")]
        elif args.all:
            plan = [(g["id"], m["id"]) for g in app.game_config.galaxies for m in g["missions"]]
        else:
            plan = [("orion", "orion_tutorial"), ("orion", "orion_patrol"), ("orion", "orion_boss"),
                    ("crimson", "crimson_recover"), ("iron", "iron_escort"), ("abyss", "abyss_swarm"),
                    ("void", "void_boss")]
        app.profile.flags["tutorial_done"] = True
        for galaxy_id, mission_id in plan:
            if galaxy_id not in app.profile.unlocked_galaxies:
                app.profile.unlocked_galaxies.append(galaxy_id)
            info = run_mission(app, galaxy_id, mission_id, args.seconds, shots, godmode=True)
            report.append(info)
            print("MISIÓN", info, flush=True)
        # derrota: el jugador sin invulnerabilidad y con 1 punto de casco
        app.start_mission("orion", "orion_patrol")
        while app.loader_task is not None:
            app.taskMgr.step()
        s = app.session
        s.player.durability.hull = 1
        s.player.durability.shield = 0
        n = 0
        while app.session is s and n < 3000:
            app.taskMgr.step()
            n += 1
        print("DERROTA", {"terminó": app.session is not s, "estado": s.mission.state, "razón": s.mission.fail_reason,
                          "pantalla": type(app.screen).__name__}, flush=True)
        if shots:
            save_shot(app, shots, "defeat_screen")
        print("PERFIL", {"nivel": app.profile.level, "créditos": app.profile.credits,
                         "misiones": app.profile.completed_missions, "galaxias": app.profile.unlocked_galaxies},
              flush=True)
        loaded, warnings = app.saves.load(1)
        print("GUARDADO", {"cargado": loaded is not None, "nivel": loaded.level if loaded else None,
                           "avisos": warnings}, flush=True)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1
    finally:
        log = Path(os.environ["GD_SAVES_DIR"]) / "game.log"
        if log.exists():
            errors = [line for line in log.read_text(encoding="utf-8").splitlines() if "ERROR" in line]
            print("ERRORES EN EL REGISTRO:", len(errors), flush=True)
    return 0


if __name__ == "__main__":
    code = main()
    os._exit(code)
