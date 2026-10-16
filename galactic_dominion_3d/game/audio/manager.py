"""Gestor de audio: efectos con varias voces, sonido posicional y música.

- Volumen general, de música y de efectos se ajustan por separado.
- Audio espacial sencillo: el volumen cae con la distancia al oyente y el
  balance izquierda/derecha sale de la posición relativa a la cámara.
- La música hace fundidos cruzados entre pistas (ambiente, combate, jefe).
"""
from __future__ import annotations

from panda3d.core import AudioSound, ClockObject, Filename, Point3

from game.audio import synth
from game.core.paths import GENERATED_AUDIO_DIR


class AudioManager:
    def __init__(self, base, settings, audio_cfg: dict, progress=None):
        self.base = base
        self.settings = settings
        self.cfg = audio_cfg
        self.voices: dict[str, list] = {}
        self.cursor: dict[str, int] = {}
        self.music_tracks: dict[str, AudioSound] = {}
        self.current_music: str | None = None
        self.fades: list = []
        self.engine = None
        self.listener = None
        self.available = bool(base.sfxManagerList) and base.sfxManagerList[0].isValid()
        if not synth.is_generated(GENERATED_AUDIO_DIR):
            synth.generate_all(GENERATED_AUDIO_DIR, progress)
        self.apply_volumes()
        base.taskMgr.add(self._update, "audio-update", sort=60)

    # --- volúmenes ----------------------------------------------------------
    def apply_volumes(self) -> None:
        master = float(self.settings["master"])
        if self.base.sfxManagerList:
            self.base.sfxManagerList[0].setVolume(master * float(self.settings["sfx"]))
        if self.base.musicManager:
            self.base.musicManager.setVolume(master * float(self.settings["music"]))

    # --- efectos ------------------------------------------------------------
    def _load(self, name: str) -> list:
        if name not in self.voices:
            path = GENERATED_AUDIO_DIR / f"{name}.wav"
            sounds = []
            if path.exists():
                fn = Filename.fromOsSpecific(str(path))
                for _ in range(int(self.cfg.get("voices_per_sound", 4))):
                    snd = self.base.loader.loadSfx(fn)
                    if snd is not None:
                        sounds.append(snd)
            self.voices[name] = sounds
            self.cursor[name] = 0
        return self.voices[name]

    def play(self, name: str, volume: float = 1.0, pos: Point3 | None = None, rate: float = 1.0) -> None:
        if not name:
            return
        voices = self._load(name)
        if not voices:
            return
        balance = 0.0
        if pos is not None and self.listener is not None:
            rel = self.listener.getRelativePoint(self.base.render, pos)
            dist = rel.length()
            hearing = float(self.cfg.get("max_hearing_distance", 1600))
            if dist > hearing:
                return
            volume *= (1 - dist / hearing) ** 1.6
            if dist > 1:
                balance = max(-1.0, min(1.0, rel.x / dist))
            if volume < 0.02:
                return
        index = self.cursor[name]
        self.cursor[name] = (index + 1) % len(voices)
        snd = voices[index]
        snd.stop()
        snd.setVolume(min(1.0, volume))
        snd.setBalance(balance * 0.8)
        snd.setPlayRate(rate)
        snd.play()

    def start_engine(self) -> None:
        if self.engine is None:
            voices = self._load("engine_loop")
            if voices:
                self.engine = voices[0]
                self.engine.setLoop(True)
        if self.engine is not None and self.engine.status() != AudioSound.PLAYING:
            self.engine.setVolume(0.0)
            self.engine.play()

    def set_engine(self, throttle: float, boosting: bool, pitch: float = 1.0, power: float = 1.0) -> None:
        """``pitch`` < 1 da un motor más grave; ``power`` > 1, más fuerte (evolución de la nave)."""
        if self.engine is not None:
            self.engine.setVolume(min(1.0, (0.18 + 0.22 * throttle + (0.25 if boosting else 0.0)) * power))
            self.engine.setPlayRate((0.8 + 0.45 * throttle + (0.3 if boosting else 0.0)) * pitch)

    def stop_engine(self) -> None:
        if self.engine is not None:
            self.engine.stop()

    # --- música -------------------------------------------------------------
    def play_music(self, track: str) -> None:
        if track == self.current_music:
            return
        name = "music_" + track
        if name not in self.music_tracks:
            path = GENERATED_AUDIO_DIR / f"{name}.wav"
            if not path.exists():
                return
            snd = self.base.loader.loadMusic(Filename.fromOsSpecific(str(path)))
            if snd is None:
                return
            snd.setLoop(True)
            self.music_tracks[name] = snd
        new = self.music_tracks[name]
        old = self.music_tracks.get("music_" + self.current_music) if self.current_music else None
        duration = float(self.cfg.get("music_crossfade", 2.0))
        self.fades = [f for f in self.fades if f[0] not in (new, old)]
        new.setVolume(0.0)
        new.play()
        self.fades.append([new, 0.0, 1.0, duration, 0.0])
        if old is not None:
            self.fades.append([old, 1.0, 0.0, duration, 0.0])
        self.current_music = track

    def stop_music(self) -> None:
        for snd in self.music_tracks.values():
            snd.stop()
        self.current_music = None
        self.fades.clear()

    def _update(self, task):
        dt = ClockObject.getGlobalClock().getDt()
        done = []
        for fade in self.fades:
            snd, start, end, duration, elapsed = fade
            fade[4] = elapsed + dt
            k = min(1.0, fade[4] / duration)
            snd.setVolume(start + (end - start) * k)
            if k >= 1.0:
                done.append(fade)
                if end <= 0.0:
                    snd.stop()
        for fade in done:
            self.fades.remove(fade)
        return task.cont
