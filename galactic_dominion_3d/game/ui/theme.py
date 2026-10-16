"""Estilo visual de la interfaz (colores, fuentes y piezas de DirectGUI).

La fuente se busca en ``assets/fonts`` y, si no hay ninguna, en las fuentes
del sistema (Bahnschrift o Segoe UI en Windows, DejaVu Sans en Linux). Si
no se encuentra ninguna se usa la fuente interna de Panda3D.
"""
from __future__ import annotations

from pathlib import Path

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectSlider
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import Filename, TextNode

from game.core.paths import FONTS_DIR

CYAN = (0.35, 0.85, 1.0, 1)
CYAN_DIM = (0.2, 0.5, 0.7, 1)
ORANGE = (1.0, 0.62, 0.22, 1)
RED = (1.0, 0.32, 0.3, 1)
GREEN = (0.45, 1.0, 0.55, 1)
GOLD = (1.0, 0.82, 0.3, 1)
MAGENTA = (1.0, 0.35, 0.8, 1)
TEXT = (0.86, 0.93, 1.0, 1)
DIM = (0.55, 0.65, 0.76, 1)
PANEL = (0.015, 0.035, 0.07, 0.86)
PANEL_LIGHT = (0.04, 0.09, 0.16, 0.92)
EDGE = (0.25, 0.65, 0.95, 0.55)

FONT_CANDIDATES = ["C:/Windows/Fonts/bahnschrift.ttf", "C:/Windows/Fonts/segoeui.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]

_font = None
_font_searched = False


def load_font(loader):
    global _font, _font_searched
    if _font_searched:
        return _font
    _font_searched = True
    candidates = [str(p) for p in sorted(FONTS_DIR.glob("*.ttf"))] + FONT_CANDIDATES
    for path in candidates:
        if Path(path).exists():
            font = loader.loadFont(Filename.fromOsSpecific(path).getFullpath())
            if font is not None and font.isValid():
                font.setPixelsPerUnit(72)
                _font = font
                return font
    return None  # sin fuente del sistema: DirectGUI usa la fuente interna de Panda3D


def font():
    return _font


def text(parent, value: str, pos, scale: float = 0.05, color=TEXT, align=TextNode.ALeft, shadow=True,
         wordwrap=None) -> OnscreenText:
    return OnscreenText(parent=parent, text=value, pos=pos, scale=scale, fg=color, align=align, font=_font,
                        mayChange=True, shadow=(0, 0, 0, 0.7) if shadow else None, wordwrap=wordwrap)


def panel(parent, frame, color=PANEL, edge=EDGE, pos=(0, 0)) -> DirectFrame:
    l, r, b, t = frame
    border = DirectFrame(parent=parent, frameColor=edge, frameSize=(l - 0.004, r + 0.004, b - 0.004, t + 0.004),
                         pos=(pos[0], 0, pos[1]))
    DirectFrame(parent=border, frameColor=color, frameSize=frame)
    return border


def button(parent, label: str, pos, command, width: float = 0.5, height: float = 0.075, scale: float = 0.045,
           enabled: bool = True, color=None, extra=None, sound=None) -> DirectButton:
    base = color or (0.06, 0.16, 0.26, 0.95)
    colors = (base, (0.3, 0.75, 1.0, 1), (0.12, 0.34, 0.52, 1), (0.05, 0.07, 0.1, 0.8))

    def run(*args):
        if sound:
            sound()
        command(*args)

    btn = DirectButton(parent=parent, text=label, text_font=_font, text_scale=scale, text_fg=TEXT,
                       text_pos=(0, -scale * 0.35), frameColor=colors, relief=DGG.FLAT,
                       frameSize=(-width / 2, width / 2, -height / 2, height / 2), pos=(pos[0], 0, pos[1]),
                       command=run, extraArgs=extra or [], pressEffect=1, rolloverSound=None, clickSound=None,
                       state=DGG.NORMAL if enabled else DGG.DISABLED)
    if not enabled:
        btn["text_fg"] = (0.45, 0.5, 0.55, 1)
    return btn


def slider(parent, pos, value: float, command, width: float = 0.5, value_range=(0, 1)) -> DirectSlider:
    return DirectSlider(parent=parent, range=value_range, value=value, pageSize=(value_range[1] - value_range[0]) / 20,
                        command=command, pos=(pos[0], 0, pos[1]), scale=width / 2,
                        frameColor=(0.08, 0.2, 0.3, 1), thumb_frameColor=CYAN, thumb_relief=DGG.FLAT,
                        frameSize=(-1, 1, -0.04, 0.04), thumb_frameSize=(-0.04, 0.04, -0.08, 0.08))


class Bar:
    """Barra de progreso horizontal (vida, escudo, energía, experiencia...)."""

    def __init__(self, parent, pos, width: float, height: float, color, back=(0.05, 0.08, 0.12, 0.85)):
        self.width = width
        self.frame = DirectFrame(parent=parent, frameColor=back, frameSize=(0, width, 0, height),
                                 pos=(pos[0], 0, pos[1]))
        self.fill = DirectFrame(parent=self.frame, frameColor=color, frameSize=(0, width, 0, height))
        self.value = 1.0

    def set(self, value: float) -> None:
        value = max(0.0, min(1.0, value))
        if abs(value - self.value) > 1e-3:
            self.value = value
            self.fill.setSx(max(1e-4, value))

    def color(self, color) -> None:
        self.fill["frameColor"] = color

    def destroy(self) -> None:
        self.frame.destroy()
