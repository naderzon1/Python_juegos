"""Síntesis de efectos de sonido y música originales con NumPy.

El juego no incluye grabaciones de terceros: la primera vez que se ejecuta,
genera todos los WAV en ``assets/audio/generated``. Son sonidos de
síntesis sencillos (osciladores, ruido filtrado y envolventes), pensados como
recursos provisionales de calidad aceptable que se pueden sustituir por
grabaciones profesionales con el mismo nombre de archivo.

Los filtros se aplican en el dominio de la frecuencia (FFT), que además es
circular: las pistas de música en bucle no tienen saltos al repetirse.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 22050
GEN_VERSION = "4"


# --- utilidades -----------------------------------------------------------------
def t_axis(duration: float) -> np.ndarray:
    return np.arange(int(duration * SR)) / SR


def env(duration: float, attack: float = 0.005, decay_pow: float = 2.0) -> np.ndarray:
    t = t_axis(duration)
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    d = (1 - t / duration) ** decay_pow
    return a * d


def sweep(f0: float, f1: float, duration: float, shape: str = "sine", curve: float = 1.0) -> np.ndarray:
    t = t_axis(duration)
    k = (t / duration) ** curve
    freq = f0 + (f1 - f0) * k
    phase = 2 * np.pi * np.cumsum(freq) / SR
    if shape == "square":
        return np.sign(np.sin(phase)) * 0.6
    if shape == "saw":
        return 2 * ((phase / (2 * np.pi)) % 1.0) - 1
    if shape == "tri":
        return 2 * np.abs(2 * ((phase / (2 * np.pi)) % 1.0) - 1) - 1
    return np.sin(phase)


def noise(duration: float, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).uniform(-1, 1, int(duration * SR))


def band(signal: np.ndarray, low: float = 0.0, high: float = 20000.0) -> np.ndarray:
    spec = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(len(signal), 1 / SR)
    mask = np.clip((freqs - low) / max(low * 0.3, 1), 0, 1) if low > 0 else np.ones_like(freqs)
    mask *= np.clip((high - freqs) / max(high * 0.3, 1) + 1, 0, 1)
    return np.fft.irfft(spec * mask, n=len(signal))


def norm(signal: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = np.max(np.abs(signal)) or 1.0
    return signal / m * peak


def mix(*parts) -> np.ndarray:
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[: len(p)] += p
    return out


def write_wav(path: Path, signal: np.ndarray) -> None:
    data = (np.clip(signal, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes(data.tobytes())


def note(n: float) -> float:
    """Frecuencia de la nota MIDI ``n``."""
    return 440.0 * 2 ** ((n - 69) / 12)


# --- efectos --------------------------------------------------------------------
def sfx_defs() -> dict:
    d = {}
    d["shot_energy"] = lambda: norm(mix(sweep(1100, 380, .14, "square", .5) * env(.14, .002, 2.5),
                                        band(noise(.06, 1), 2000) * env(.06) * .3), .55)
    d["shot_laser"] = lambda: norm(mix(sweep(2400, 1300, .2, "saw", .6) * env(.2, .002, 1.6) * .6,
                                       sweep(1200, 650, .2) * env(.2, .002, 1.5)), .6)
    d["shot_plasma"] = lambda: norm(mix(band(sweep(320, 70, .42, "saw", .4), 0, 1800) * env(.42, .004, 1.5),
                                        band(noise(.3, 2), 100, 1500) * env(.3, .002, 3) * .6), .75)
    d["shot_scatter"] = lambda: norm(mix(band(noise(.25, 3), 400, 5000) * env(.25, .001, 3),
                                         sweep(180, 60, .2) * env(.2, .002, 2)), .7)
    d["shot_enemy"] = lambda: norm(sweep(700, 240, .14, "square", .5) * env(.14, .002, 2.5), .45)
    d["shot_heavy"] = lambda: norm(mix(band(sweep(380, 110, .28, "saw", .5), 0, 2000) * env(.28, .003, 2),
                                       band(noise(.2, 4), 80, 900) * env(.2) * .5), .6)
    d["shot_alien"] = lambda: norm(sweep(520, 300, .3) * (0.6 + 0.4 * np.sin(2 * np.pi * 34 * t_axis(.3)))
                                   * env(.3, .01, 1.5), .5)
    d["shot_void"] = lambda: norm(sweep(1500, 280, .24, "saw", .6) * np.sin(2 * np.pi * 90 * t_axis(.24))
                                  * env(.24, .002, 1.8), .55)
    d["missile_launch"] = lambda: norm(mix(band(noise(.7, 5), 300, 3500) * env(.7, .05, 1.4),
                                           sweep(120, 380, .7) * env(.7, .02, 1.2) * .4), .65)
    d["torpedo"] = lambda: norm(mix(sweep(60, 180, 1.1, "saw", .8) * env(1.1, .05, 1.0) * .7,
                                    band(noise(1.1, 6), 80, 1200) * env(1.1, .1, 1.2)), .8)
    d["drone_deploy"] = lambda: norm(np.concatenate([sweep(f, f, .07, "tri") * env(.07, .002, 1)
                                                     for f in (660, 880, 990, 1320)]), .45)
    d["pulse"] = lambda: norm(mix(sweep(55, 35, 1.0) * env(1.0, .01, 1.4), sweep(200, 2400, .5, "saw", 2) *
                                  env(.5, .01, 1.0) * .25, band(noise(.9, 7), 60, 900) * env(.9, .005, 2) * .7), .9)
    d["explosion_small"] = lambda: norm(mix(band(noise(.8, 8), 40, 2200) * env(.8, .002, 2.6),
                                            sweep(90, 35, .5) * env(.5, .002, 2)), .8)
    d["explosion_big"] = lambda: norm(mix(band(noise(2.0, 9), 25, 1400) * env(2.0, .004, 2.2),
                                          sweep(70, 25, 1.4) * env(1.4, .003, 1.6),
                                          band(noise(.3, 10), 1000, 6000) * env(.3, .001, 3) * .5), .95)
    d["impact"] = lambda: norm(band(noise(.09, 11), 600, 6000) * env(.09, .001, 3), .5)
    d["shield_hit"] = lambda: norm(mix(sweep(1500, 900, .28) * np.sin(2 * np.pi * 47 * t_axis(.28)),
                                       band(noise(.28, 12), 2500, 9000) * .3) * env(.28, .003, 1.8), .5)
    d["shield_down"] = lambda: norm(sweep(900, 180, .6, "saw", .8) * env(.6, .01, 1.2), .55)
    d["alarm"] = lambda: norm(np.concatenate([sweep(f, f, .16, "square") * env(.16, .005, .4)
                                              for f in (880, 660, 880, 660)]), .45)
    d["lock_beep"] = lambda: norm(sweep(1600, 1600, .06) * env(.06, .002, .5), .35)
    d["lock_done"] = lambda: norm(mix(sweep(1800, 1800, .25) * env(.25, .003, .6),
                                      sweep(2700, 2700, .25) * env(.25, .003, .6) * .5), .4)
    d["ui_click"] = lambda: norm(sweep(1200, 900, .045, "tri") * env(.045, .001, 2), .35)
    d["ui_confirm"] = lambda: norm(np.concatenate([sweep(880, 880, .08, "tri") * env(.08, .002, 1),
                                                   sweep(1320, 1320, .14, "tri") * env(.14, .002, 1.5)]), .4)
    d["ui_error"] = lambda: norm(sweep(180, 140, .22, "square") * env(.22, .005, 1), .35)
    d["level_up"] = lambda: norm(np.concatenate([sweep(note(n), note(n), .12, "tri") * env(.12, .003, .8)
                                                 for n in (72, 76, 79, 84, 88)]), .45)
    d["pickup"] = lambda: norm(mix(sweep(1320, 1320, .25) * env(.25, .002, 1.2),
                                   sweep(1980, 1980, .25) * env(.25, .05, 1.2) * .6), .4)
    d["jump"] = lambda: norm(mix(sweep(60, 1800, 2.2, "saw", 2.2) * env(2.2, .4, .6) * .4,
                                 band(noise(2.2, 13), 200, 4000) * env(2.2, .8, .4)), .8)
    d["boost"] = lambda: norm(band(noise(.6, 14), 150, 2500) * env(.6, .05, 1.5), .5)
    d["evade"] = lambda: norm(band(noise(.35, 15), 500, 5000) * env(.35, .02, 2) +
                              sweep(300, 900, .35) * env(.35, .02, 2) * .3, .5)
    d["boss_alert"] = lambda: norm(mix(sweep(note(38), note(38), 1.6, "saw") * env(1.6, .2, .8),
                                       sweep(note(45), note(45), 1.6, "saw") * env(1.6, .2, .8) * .7), .7)
    d["beam_charge"] = lambda: norm(sweep(200, 1600, 1.4, "saw", 1.5) * env(1.4, 1.2, .2) * .6, .55)
    d["victory"] = lambda: norm(np.concatenate([chord([60, 64, 67], .35), chord([62, 65, 69], .35),
                                                chord([64, 67, 72], .35), chord([65, 69, 72, 77], 1.6)]), .6)
    d["defeat"] = lambda: norm(np.concatenate([chord([57, 60, 64], .5), chord([55, 58, 62], .5),
                                               chord([53, 56, 60], .5), chord([45, 52, 57], 1.6)]), .55)
    d["shot_layer"] = lambda: norm(mix(sweep(120, 45, .22) * env(.22, .002, 2.2),
                                       band(noise(.12, 30), 200, 1800) * env(.12, .001, 3) * .35), .6)
    d["engine_loop"] = engine_loop
    return d


def chord(notes, duration: float, shape: str = "tri") -> np.ndarray:
    t = t_axis(duration)
    out = sum(sweep(note(n), note(n), duration, shape) for n in notes) / len(notes)
    return out * np.clip(t / 0.01, 0, 1) * np.clip((duration - t) / 0.15, 0, 1)


def engine_loop() -> np.ndarray:
    duration = 2.0
    t = t_axis(duration)
    hum = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((55, 1.0), (110, .5), (165, .25), (220, .12)))
    rumble = band(noise(duration, 16), 40, 400)
    hiss = band(noise(duration, 17), 1500, 5000) * .15
    return norm(hum * .6 + rumble * 2.5 + hiss, .5)


# --- música --------------------------------------------------------------------
MUSIC = {
    # nombre: (nota raíz, acordes en grados relativos, tempo de cambio, brillo)
    "ambient_orion": (50, [[0, 7, 14, 16], [-3, 4, 12, 16], [5, 12, 16, 21], [3, 10, 15, 19]], 8.0, 3200),
    "ambient_crimson": (45, [[0, 7, 12, 15], [1, 8, 13, 17], [-2, 5, 10, 15], [0, 7, 15, 19]], 8.0, 2400),
    "ambient_iron": (43, [[0, 7, 12, 15], [0, 5, 10, 15], [-4, 3, 8, 12], [-2, 5, 10, 14]], 8.0, 2000),
    "ambient_abyss": (41, [[0, 6, 12, 17], [1, 7, 13, 18], [-1, 6, 11, 16], [0, 7, 13, 19]], 8.0, 2600),
    "ambient_void": (38, [[0, 3, 10, 15], [-1, 3, 8, 14], [0, 6, 12, 15], [-5, 2, 7, 14]], 8.0, 1900),
}


def pad(freqs, duration: float, seed: int, bright: float) -> np.ndarray:
    t = t_axis(duration)
    rng = np.random.default_rng(seed)
    out = np.zeros_like(t)
    for f in freqs:
        for detune in (-0.12, 0.0, 0.11):
            ff = f * 2 ** (detune / 12)
            phase = rng.uniform(0, 2 * np.pi)
            out += 2 * (((ff * t + phase / (2 * np.pi)) % 1.0)) - 1
    out = band(out, 0, bright)
    fade = np.clip(t / 1.8, 0, 1) * np.clip((duration - t) / 1.8, 0, 1)
    return out * fade


def ambient_track(name: str) -> np.ndarray:
    root, chords, step, bright = MUSIC[name]
    total = step * len(chords)
    t = t_axis(total)
    out = np.zeros_like(t)
    overlap = 1.8
    for i, ch in enumerate(chords):
        seg = pad([note(root + n) for n in ch], step + overlap, i, bright)
        start = int(i * step * SR)
        end = start + len(seg)
        if end <= len(out):
            out[start:end] += seg
        else:
            cut = len(out) - start
            out[start:] += seg[:cut]
            out[: end - len(out)] += seg[cut:]
    sub = np.sin(2 * np.pi * note(root - 12) * t) * 0.35 * (0.75 + 0.25 * np.sin(2 * np.pi * t / total))
    rng = np.random.default_rng(len(name))
    bells = np.zeros_like(t)
    for k in range(int(total / 1.0)):
        if rng.random() < 0.45:
            ch = chords[int(k * 1.0 / step) % len(chords)]
            f = note(root + 24 + rng.choice(ch))
            start = int(k * SR + rng.uniform(0, .5) * SR)
            dur = 2.5
            seg = np.sin(2 * np.pi * f * t_axis(dur)) * env(dur, .01, 3) * 0.18
            idx = (np.arange(len(seg)) + start) % len(out)
            bells[idx] += seg
    return norm(out * 0.5 + sub + bells, 0.7)


def drum_track(bpm: float, root: int, progression, bars: int, heavy: bool) -> np.ndarray:
    beat = 60.0 / bpm
    total = beat * 4 * bars
    t = t_axis(total)
    out = np.zeros_like(t)

    def place(sample, at):
        start = int(at * SR) % len(out)
        idx = (np.arange(len(sample)) + start) % len(out)
        out[idx] += sample

    kick = sweep(140, 42, .3) * env(.3, .001, 2.5)
    snare = mix(band(noise(.22, 20), 900, 7000) * env(.22, .001, 2.2) * .6, sweep(220, 160, .12) * env(.12) * .4)
    hat = band(noise(.05, 21), 6000, 11000) * env(.05, .001, 2) * .25
    for b in range(bars * 4):
        at = b * beat
        place(kick, at)
        if heavy and b % 2 == 1:
            place(kick * .7, at + beat * .5)
        if b % 2 == 1:
            place(snare, at)
        for k in range(2 if not heavy else 4):
            place(hat, at + k * beat / (2 if not heavy else 4))
    for bar in range(bars):
        deg = progression[bar % len(progression)]
        for k in range(8):
            f = note(root + deg - 12)
            seg = band(sweep(f, f, beat / 2, "saw"), 0, 900 if not heavy else 1400) * env(beat / 2, .005, 1.2)
            place(seg * .55, bar * beat * 4 + k * beat / 2)
        lead_f = [note(root + deg + 12 + n) for n in (0, 3, 7, 10)]
        seg = pad(lead_f[:3], beat * 4, bar, 1800) * .18
        place(seg, bar * beat * 4)
    return norm(out, .75)


def music_defs() -> dict:
    d = {name: (lambda n=name: ambient_track(n)) for name in MUSIC}
    d["combat"] = lambda: drum_track(122, 45, [0, 0, -4, -2], 8, heavy=False)
    d["boss"] = lambda: drum_track(140, 40, [0, 1, -2, -1], 8, heavy=True)
    return d


def generate_all(out_dir: Path, progress=None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = list(sfx_defs().items()) + [("music_" + k, v) for k, v in music_defs().items()]
    for i, (name, fn) in enumerate(jobs):
        write_wav(out_dir / f"{name}.wav", fn())
        if progress:
            progress(i + 1, len(jobs), name)
    (out_dir / "VERSION").write_text(GEN_VERSION, encoding="utf-8")


def is_generated(out_dir: Path) -> bool:
    marker = out_dir / "VERSION"
    if not marker.exists() or marker.read_text(encoding="utf-8").strip() != GEN_VERSION:
        return False
    names = list(sfx_defs()) + ["music_" + k for k in music_defs()]
    return all((out_dir / f"{n}.wav").exists() for n in names)
