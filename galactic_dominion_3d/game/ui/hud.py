"""HUD de combate.

Muestra: mira (en el punto real de puntería), retícula y anillo de fijación
del objetivo, indicador de anticipación de tiro, marcas sobre enemigos y
flechas en el borde de la pantalla para lo que está fuera de vista, barras de
casco/escudo/energía, velocidad y acelerador, armas con recarga y munición,
nivel, experiencia y créditos, radar 3D simplificado, alertas de amenaza,
barra del jefe, estado de la misión, mensajes y estadísticas de rendimiento.
"""
from __future__ import annotations

import math

from direct.gui.DirectGui import DirectFrame
from panda3d.core import ClockObject, LineSegs, NodePath, Point2, Point3, TextNode, Vec3

from game.progression.leveling import level_progress
from game.ui import theme
from game.ui.theme import CYAN, DIM, GOLD, GREEN, MAGENTA, ORANGE, RED, TEXT, Bar


def lines_node(points_list, color, thickness=1.5, name="hud-lines") -> NodePath:
    ls = LineSegs(name)
    ls.setThickness(thickness)
    ls.setColor(*color)
    for pts in points_list:
        ls.moveTo(pts[0][0], 0, pts[0][1])
        for x, y in pts[1:]:
            ls.drawTo(x, 0, y)
    return NodePath(ls.create())


def circle_pts(r, n=40, start=0.0, end=math.tau):
    return [(math.cos(start + (end - start) * i / n) * r, math.sin(start + (end - start) * i / n) * r)
            for i in range(n + 1)]


class Marker:
    """Marca reutilizable sobre la pantalla (corchetes, flecha o rombo)."""

    def __init__(self, parent, kind: str, color):
        if kind == "bracket":
            c = 0.32
            pts = []
            for sx in (-1, 1):
                for sy in (-1, 1):
                    pts.append([(sx * 1, sy * (1 - c)), (sx * 1, sy * 1), (sx * (1 - c), sy * 1)])
            self.node = lines_node(pts, color, 1.6)
        elif kind == "arrow":
            self.node = lines_node([[(-0.6, -0.5), (0, 0.6), (0.6, -0.5), (0, -0.2), (-0.6, -0.5)]], color, 2.0)
        else:
            self.node = lines_node([[(0, 1), (1, 0), (0, -1), (-1, 0), (0, 1)]], color, 1.8)
        self.node.reparentTo(parent)
        self.node.hide()


class HUD:
    def __init__(self, base, session):
        self.base = base
        self.s = session
        self.root = base.aspect2d.attachNewNode("hud")
        self.anchor = {k: getattr(base, k).attachNewNode("hud-" + k) for k in
                       ("a2dTopLeft", "a2dTopRight", "a2dBottomLeft", "a2dBottomRight", "a2dTopCenter",
                        "a2dBottomCenter")}
        self.texts: dict[str, str] = {}
        self._build()
        self.messages: list = []
        self.banner_ttl = 0.0
        self.alert_time = 0.0
        self.hit_marker = 0.0
        self.crit_marker = 0.0
        self.show_stats = bool(session.app.settings["show_fps"])
        self.stats_timer = 0.0

    # --- construcción -------------------------------------------------------
    def _build(self) -> None:
        r = self.root
        self.crosshair = lines_node([circle_pts(0.032, 32), [(-0.055, 0), (-0.04, 0)], [(0.04, 0), (0.055, 0)],
                                     [(0, 0.04), (0, 0.055)], [(0, -0.04), (0, -0.055)]], CYAN, 1.6)
        self.crosshair.reparentTo(r)
        dot = lines_node([circle_pts(0.004, 8)], CYAN, 2.5)
        dot.reparentTo(self.crosshair)
        self.hitmark = lines_node([[(-0.03, 0.03), (-0.015, 0.015)], [(0.03, 0.03), (0.015, 0.015)],
                                   [(-0.03, -0.03), (-0.015, -0.015)], [(0.03, -0.03), (0.015, -0.015)]],
                                  (1, 1, 1, 1), 2.2)
        self.hitmark.reparentTo(self.crosshair)
        self.hitmark.hide()
        self.target_box = Marker(r, "bracket", ORANGE)
        self.lock_ring = lines_node([circle_pts(1.0, 48)], RED, 2.2)
        self.lock_ring.reparentTo(r)
        self.lock_ring.hide()
        self.lead = Marker(r, "diamond", ORANGE)
        self.target_arrow = Marker(r, "arrow", ORANGE)
        self.target_dist = theme.text(r, "", (0, 0), 0.032, ORANGE, TextNode.ACenter)
        self.markers = [Marker(r, "bracket", RED) for _ in range(24)]
        self.arrows = [Marker(r, "arrow", RED) for _ in range(12)]
        self.obj_markers = [Marker(r, "diamond", GREEN) for _ in range(8)]

        bl = self.anchor["a2dBottomLeft"]
        theme.panel(bl, (0, 0.62, 0, 0.3), pos=(0.03, 0.03))
        self.hull_bar = Bar(bl, (0.18, 0.25), 0.3, 0.022, (0.95, 0.75, 0.3, 1))
        self.shield_bar = Bar(bl, (0.18, 0.19), 0.3, 0.022, CYAN)
        self.energy_bar = Bar(bl, (0.18, 0.13), 0.3, 0.022, (0.55, 0.45, 1.0, 1))
        for y, label in ((0.25, "CASCO"), (0.19, "ESCUDO"), (0.13, "ENERGÍA")):
            theme.text(bl, label, (0.05, y + 0.003), 0.03, DIM)
        self.t_hull = theme.text(bl, "", (0.635, 0.253), 0.028, TEXT, TextNode.ARight)
        self.t_shield = theme.text(bl, "", (0.635, 0.193), 0.028, TEXT, TextNode.ARight)
        self.t_energy = theme.text(bl, "", (0.635, 0.133), 0.028, TEXT, TextNode.ARight)
        self.t_speed = theme.text(bl, "", (0.05, 0.065), 0.034, TEXT)
        self.throttle_bar = Bar(bl, (0.4, 0.065), 0.22, 0.016, (0.5, 0.8, 1.0, 0.9))

        br = self.anchor["a2dBottomRight"]
        theme.panel(br, (-0.72, 0, 0, 0.3), pos=(-0.03, 0.03))
        self.t_weapons = [theme.text(br, "", (-0.72, 0.265 - i * 0.055), 0.032, TEXT) for i in range(4)]
        self.weapon_bars = [Bar(br, (-0.3, 0.255 - i * 0.055), 0.24, 0.014, CYAN) for i in range(4)]

        tl = self.anchor["a2dTopLeft"]
        theme.panel(tl, (0, 0.78, -0.3, 0), pos=(0.03, -0.03))
        self.t_mission = theme.text(tl, "", (0.06, -0.085), 0.04, GOLD)
        self.t_objective = theme.text(tl, "", (0.06, -0.14), 0.034, TEXT, wordwrap=21)
        self.t_pilot = theme.text(tl, "", (0.06, -0.255), 0.03, DIM)
        self.xp_bar = Bar(tl, (0.06, -0.3), 0.7, 0.012, (0.4, 1.0, 0.6, 1))

        tr = self.anchor["a2dTopRight"]
        self.target_panel = theme.panel(tr, (-0.62, 0, -0.2, 0), pos=(-0.03, -0.03))
        self.t_target = theme.text(self.target_panel, "", (-0.6, -0.05), 0.036, ORANGE)
        self.t_target_info = theme.text(self.target_panel, "", (-0.6, -0.17), 0.028, DIM)
        self.target_hull = Bar(self.target_panel, (-0.6, -0.11), 0.56, 0.018, (0.95, 0.75, 0.3, 1))
        self.target_shield = Bar(self.target_panel, (-0.6, -0.135), 0.56, 0.012, CYAN)
        self.t_stats = theme.text(tr, "", (-0.05, -0.3), 0.028, GREEN, TextNode.ARight)
        self.t_feed = [theme.text(tr, "", (-0.05, -0.38 - i * 0.045), 0.032, TEXT, TextNode.ARight) for i in range(6)]

        tc = self.anchor["a2dTopCenter"]
        self.boss_root = tc.attachNewNode("boss-bar")
        theme.panel(self.boss_root, (-0.62, 0.62, -0.13, 0), pos=(0, -0.03))
        self.t_boss = theme.text(self.boss_root, "", (0, -0.075), 0.04, MAGENTA, TextNode.ACenter)
        self.boss_hull = Bar(self.boss_root, (-0.58, -0.12), 1.16, 0.022, MAGENTA)
        self.boss_shield = Bar(self.boss_root, (-0.58, -0.137), 1.16, 0.01, CYAN)
        self.boss_root.hide()
        self.t_alert = theme.text(tc, "", (0, -0.24), 0.048, RED, TextNode.ACenter)
        self.t_tutorial = theme.text(tc, "", (0, -0.33), 0.04, GOLD, TextNode.ACenter, wordwrap=34)
        self.t_banner = theme.text(self.root, "", (0, 0.3), 0.075, TEXT, TextNode.ACenter)
        self.t_sub = theme.text(self.root, "", (0, 0.22), 0.042, DIM, TextNode.ACenter)

        self.radar_root = br.attachNewNode("radar")
        self.radar_root.setPos(-0.23, 0, 0.53)
        DirectFrame(parent=self.radar_root, frameColor=(0.02, 0.06, 0.1, 0.6), frameSize=(-0.17, 0.17, -0.17, 0.17))
        grid = lines_node([circle_pts(0.165, 48), circle_pts(0.11, 40), circle_pts(0.055, 30),
                           [(-0.165, 0), (0.165, 0)], [(0, -0.165), (0, 0.165)],
                           [(0, 0), (-0.09, 0.14)], [(0, 0), (0.09, 0.14)]], (0.25, 0.6, 0.85, 0.6), 1.0)
        grid.reparentTo(self.radar_root)
        self.radar_dots = []
        for _ in range(40):
            dot = DirectFrame(parent=self.radar_root, frameColor=RED, frameSize=(-0.008, 0.008, -0.008, 0.008))
            stem = DirectFrame(parent=dot, frameColor=(1, 1, 1, 0.35), frameSize=(-0.001, 0.001, 0, 0.01))
            dot.hide()
            self.radar_dots.append((dot, stem))

    # --- utilidades ---------------------------------------------------------
    def set_text(self, node, value: str) -> None:
        key = id(node)
        if self.texts.get(key) != value:
            self.texts[key] = value
            node.setText(value)

    def project(self, world_point: Point3):
        cam_p = self.base.cam.getRelativePoint(self.base.render, world_point)
        aspect = self.base.getAspectRatio()
        if cam_p.y > 0.5:
            p2 = Point2()
            if self.base.camLens.project(cam_p, p2) and abs(p2.x) <= 1 and abs(p2.y) <= 1:
                return p2.x * aspect, p2.y, True, cam_p
        return 0.0, 0.0, False, cam_p

    def edge_point(self, cam_p: Vec3):
        aspect = self.base.getAspectRatio()
        dx, dy = cam_p.x, cam_p.z
        if abs(dx) < 1e-4 and abs(dy) < 1e-4:
            dy = -1
        ang = math.atan2(dy, dx)
        limit_x, limit_y = aspect * 0.9, 0.85
        k = min(limit_x / max(abs(math.cos(ang)), 1e-4), limit_y / max(abs(math.sin(ang)), 1e-4))
        return math.cos(ang) * k, math.sin(ang) * k, math.degrees(ang)

    def message(self, value: str, color=TEXT, ttl: float = 4.0) -> None:
        self.messages.insert(0, [value, color, ttl])
        del self.messages[len(self.t_feed):]

    def banner(self, title: str, subtitle: str = "", color=TEXT, ttl: float = 3.0) -> None:
        self.t_banner.setText(title)
        self.t_banner["fg"] = color
        self.t_sub.setText(subtitle)
        self.banner_ttl = ttl

    def tutorial(self, value: str) -> None:
        self.set_text(self.t_tutorial, value)

    def hit(self, crit: bool) -> None:
        self.hit_marker = 0.12
        if crit:
            self.crit_marker = 0.25

    # --- actualización ------------------------------------------------------
    def update(self, dt: float) -> None:
        s = self.s
        p = s.player
        if p is None:
            return
        fwd = s.world.render.getRelativeVector(p.node, Vec3(0, 1, 0))
        aim = p.pos + fwd * 500
        x, y, on, _ = self.project(aim)
        self.crosshair.setPos(x, 0, y)
        self.crosshair.show() if on and p.alive else self.crosshair.hide()
        self.hit_marker -= dt
        self.crit_marker -= dt
        if self.hit_marker > 0:
            self.hitmark.show()
            self.hitmark.setColorScale((1, 0.8, 0.2, 1) if self.crit_marker > 0 else (1, 1, 1, 1))
        else:
            self.hitmark.hide()
        self._update_target(dt)
        self._update_markers()
        self._update_bars()
        self._update_weapons()
        self._update_mission()
        self._update_radar()
        self._update_alerts(dt)
        self._update_feed(dt)
        self._update_boss()
        self._update_stats(dt)

    def _update_target(self, dt: float) -> None:
        s, p = self.s, self.s.player
        t = s.target
        for item in (self.target_box, self.lead, self.target_arrow):
            item.node.hide()
        self.lock_ring.hide()
        if t is None or not t.alive:
            self.target_panel.hide()
            self.set_text(self.target_dist, "")
            return
        self.target_panel.show()
        dist = (t.pos - p.pos).length()
        x, y, on, cam_p = self.project(t.pos)
        color = MAGENTA if t.boss else (GOLD if t.elite else ORANGE)
        if on:
            size = max(0.035, min(0.22, t.bound_radius * 1.6 / max(cam_p.y, 1) * 1.6))
            self.target_box.node.show()
            self.target_box.node.setPos(x, 0, y)
            self.target_box.node.setScale(size)
            self.target_box.node.setColorScale(*color)
            self.target_dist.setPos(x, y - size - 0.04)
            self.set_text(self.target_dist, f"{dist:,.0f} m".replace(",", "."))
            if p.lock_progress > 0:
                self.lock_ring.show()
                self.lock_ring.setPos(x, 0, y)
                self.lock_ring.setScale(size * (2.6 - 1.4 * p.lock_progress))
                self.lock_ring.setColorScale(*(RED if p.locked else (1, 0.7, 0.3, 0.8)))
            wd = p.primary.d
            if wd.projectile_speed > 0:
                t_hit = dist / wd.projectile_speed
                lx, ly, lon, _ = self.project(t.pos + (t.velocity - p.velocity) * t_hit)
                if lon:
                    self.lead.node.show()
                    self.lead.node.setPos(lx, 0, ly)
                    self.lead.node.setScale(0.014)
        else:
            ex, ey, ang = self.edge_point(cam_p)
            self.target_arrow.node.show()
            self.target_arrow.node.setPos(ex, 0, ey)
            self.target_arrow.node.setR(90 - ang)
            self.target_arrow.node.setScale(0.03)
            self.target_dist.setPos(ex, ey - 0.06)
            self.set_text(self.target_dist, f"{dist:,.0f} m".replace(",", "."))
        name = t.name + ("  [BLOQUEADO]" if p.locked else "")
        self.set_text(self.t_target, name)
        self.t_target["fg"] = color
        self.target_hull.set(t.durability.hull_ratio)
        self.target_shield.set(t.durability.shield_ratio)
        self.set_text(self.t_target_info, f"Distancia {dist:,.0f} m   Casco {t.durability.hull:,.0f}".replace(",", "."))

    def _update_markers(self) -> None:
        s, p = self.s, self.s.player
        enemies = [e for e in s.world.hostiles_of("player") if e is not s.target and e.kind != "weak_point"]
        enemies.sort(key=lambda e: (e.pos - p.pos).length())
        mi = ai = 0
        for e in enemies:
            x, y, on, cam_p = self.project(e.pos)
            color = MAGENTA if e.boss else (GOLD if e.elite else RED)
            if on and mi < len(self.markers):
                m = self.markers[mi]
                mi += 1
                size = max(0.02, min(0.15, e.bound_radius * 1.4 / max(cam_p.y, 1) * 1.6))
                m.node.show()
                m.node.setPos(x, 0, y)
                m.node.setScale(size)
                m.node.setColorScale(*color)
            elif not on and ai < len(self.arrows) and (e.pos - p.pos).length() < 2200:
                a = self.arrows[ai]
                ai += 1
                ex, ey, ang = self.edge_point(cam_p)
                a.node.show()
                a.node.setPos(ex, 0, ey)
                a.node.setR(90 - ang)
                a.node.setScale(0.02)
                a.node.setColorScale(*color)
        for m in self.markers[mi:]:
            m.node.hide()
        for a in self.arrows[ai:]:
            a.node.hide()
        oi = 0
        for point in s.objective_points():
            if oi >= len(self.obj_markers):
                break
            m = self.obj_markers[oi]
            oi += 1
            x, y, on, cam_p = self.project(point)
            if not on:
                x, y, _ = self.edge_point(cam_p)
            m.node.show()
            m.node.setPos(x, 0, y)
            m.node.setScale(0.018)
        for m in self.obj_markers[oi:]:
            m.node.hide()

    def _update_bars(self) -> None:
        p = self.s.player
        d = p.durability
        self.hull_bar.set(d.hull_ratio)
        self.hull_bar.color(RED if d.hull_ratio < 0.3 else (0.95, 0.75, 0.3, 1))
        self.shield_bar.set(d.shield_ratio)
        self.energy_bar.set(p.energy / max(1.0, p.stats.max_energy))
        self.set_text(self.t_hull, f"{d.hull:.0f}/{d.max_hull:.0f}")
        self.set_text(self.t_shield, f"{d.shield:.0f}/{d.max_shield:.0f}")
        self.set_text(self.t_energy, f"{p.energy:.0f}/{p.stats.max_energy:.0f}")
        boost = "  IMPULSO" if p.boosting else ""
        self.set_text(self.t_speed, f"VEL {p.speed:5.0f} m/s{boost}")
        self.throttle_bar.set(max(0.0, p.throttle))

    def _update_weapons(self) -> None:
        p = self.s.player
        rows = []
        pr = p.primary
        rows.append((f"» {pr.d.name}", 1 - pr.cooldown_ratio, CYAN))
        sec = p.secondary
        if sec is not None:
            extra = f" {sec.ammo}/{p.stats.missile_capacity}" if sec.d.uses_ammo else ""
            if sec.d.kind == "drones" and p.drones:
                extra = f" activos ({p.drones[0].life:.0f} s)"
            rows.append((f"[Der] {sec.d.name}{extra}", 1 - sec.cooldown_ratio, ORANGE))
        spec = p.special
        if spec is not None:
            state = "LISTO" if spec.ready else f"{spec.timer:.0f} s"
            rows.append((f"[F] {spec.d.name}: {state}", 1 - spec.cooldown_ratio, MAGENTA))
        rows.append(("[Espacio] Evasión: " + ("LISTA" if p.evade_cd <= 0 else f"{p.evade_cd:.1f} s"),
                     1 - p.evade_cd / 2.8, GREEN))
        for i, node in enumerate(self.t_weapons):
            if i < len(rows):
                label, ratio, color = rows[i]
                self.set_text(node, label)
                node["fg"] = color
                self.weapon_bars[i].frame.show()
                self.weapon_bars[i].set(ratio)
                self.weapon_bars[i].color(color)
            else:
                self.set_text(node, "")
                self.weapon_bars[i].frame.hide()

    def _update_mission(self) -> None:
        s = self.s
        self.set_text(self.t_mission, f"{s.galaxy['name']} · {s.mission_cfg['name']}")
        self.set_text(self.t_objective, s.mission.objective_text())
        prof = s.app.profile
        self.set_text(self.t_pilot, f"Piloto nivel {prof.level} · Nave {s.player.evo.name}    Créditos {prof.credits + s.earned['credits']:,}"
                      .replace(",", ".") + f"   (+{s.earned['xp']} XP en misión)")
        self.xp_bar.set(level_progress(prof, s.app.game_config))

    def _update_radar(self) -> None:
        s, p = self.s, self.s.player
        rng = 2000.0
        i = 0
        items = [(e, MAGENTA if e.boss else (GOLD if e.elite else RED)) for e in s.world.hostiles_of("player")
                 if e.kind != "weak_point"]
        items += [(a, GREEN) for a in s.world.allies_of("player") if a is not p]
        for entity, color in items:
            if i >= len(self.radar_dots):
                break
            local = p.node.getRelativePoint(s.world.render, entity.pos)
            dist = local.length()
            if dist > rng:
                continue
            dot, stem = self.radar_dots[i]
            i += 1
            dot.show()
            dot.setPos(local.x / rng * 0.16, 0, local.y / rng * 0.16)
            dot["frameColor"] = color if entity is not s.target else (1, 1, 1, 1)
            height = max(-0.05, min(0.05, local.z / rng * 0.4))
            stem.setSz(max(0.01, abs(height) / 0.01))
            stem.setPos(0, 0, 0 if height >= 0 else height)
        for dot, _ in self.radar_dots[i:]:
            dot.hide()

    def _update_alerts(self, dt: float) -> None:
        s, p = self.s, self.s.player
        alert = ""
        if s.hazard_alert:
            alert = s.hazard_alert
        if s.projectiles.incoming_missiles(p):
            alert = "¡MISIL ENTRANTE! (Espacio para evadir)"
        if p.durability.hull_ratio < 0.3:
            alert = "¡CASCO CRÍTICO!"
        elif p.durability.shield <= 0 and p.durability.max_shield > 0 and not alert:
            alert = "ESCUDOS CAÍDOS"
        if s.out_of_bounds:
            alert = "FUERA DE LA ZONA DE COMBATE: regresa"
        if s.boss is not None and s.boss.beam is not None and s.boss.beam[0] == "charge":
            alert = "¡RAYO DEL JEFE CARGANDO!"
        self.alert_time += dt
        visible = alert and (self.alert_time % 0.7) < 0.5
        self.set_text(self.t_alert, alert if visible else "")
        if self.banner_ttl > 0:
            self.banner_ttl -= dt
            alpha = min(1.0, self.banner_ttl * 2)
            self.t_banner.setAlphaScale(alpha)
            self.t_sub.setAlphaScale(alpha)
            if self.banner_ttl <= 0:
                self.t_banner.setText("")
                self.t_sub.setText("")

    def _update_feed(self, dt: float) -> None:
        for m in self.messages:
            m[2] -= dt
        self.messages = [m for m in self.messages if m[2] > 0]
        for i, node in enumerate(self.t_feed):
            if i < len(self.messages):
                value, color, ttl = self.messages[i]
                self.set_text(node, value)
                node["fg"] = (color[0], color[1], color[2], min(1.0, ttl))
            else:
                self.set_text(node, "")

    def _update_boss(self) -> None:
        b = self.s.boss
        if b is None or not b.alive:
            self.boss_root.hide()
            return
        self.boss_root.show()
        armor = " · NÚCLEO BLINDADO" if b.weak_alive else " · NÚCLEO VULNERABLE"
        self.set_text(self.t_boss, f"{b.name} — Fase {b.phase_index + 1}/{len(b.cfg['phases'])} · "
                                   f"Generadores {b.weak_alive}{armor}")
        self.boss_hull.set(b.durability.hull_ratio)
        self.boss_shield.set(b.durability.shield_ratio)

    def _update_stats(self, dt: float) -> None:
        if "toggle_stats" in self.s.last_input.pressed:
            self.show_stats = not self.show_stats
        if not self.show_stats:
            self.set_text(self.t_stats, "")
            return
        self.stats_timer -= dt
        if self.stats_timer > 0:
            return
        self.stats_timer = 0.25
        fps = ClockObject.getGlobalClock().getAverageFrameRate()
        s = self.s
        self.set_text(self.t_stats, f"{fps:5.1f} FPS  {1000 / max(fps, 1):4.1f} ms\n"
                                    f"Entidades {len(s.world.entities)}  Proyectiles {s.projectiles.count()}\n"
                                    f"Partículas {s.effects.count()}")

    # --- limpieza -----------------------------------------------------------
    def destroy(self) -> None:
        self.root.removeNode()
        for node in self.anchor.values():
            node.removeNode()
