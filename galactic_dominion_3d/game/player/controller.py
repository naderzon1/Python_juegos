"""Lectura de controles: teclado y ratón configurables, y mando opcional.

Las teclas salen de ``settings["bindings"]`` (editables en el menú o en
``config/controls.json``). El ratón se captura y se recentra cada fotograma
para medir su desplazamiento, que gira la nave (método que funciona en
Windows, donde el modo de ratón relativo de Panda3D no está disponible).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from panda3d.core import ButtonRegistry, ClockObject, InputDevice, WindowProperties

EDGE_ACTIONS = ("evade", "fire_special", "target_next", "target_nearest", "weapon_next", "pause", "toggle_stats")


@dataclass
class InputState:
    yaw: float = 0.0      # grados de giro pedidos en este fotograma (ratón y mando)
    pitch: float = 0.0
    roll: float = 0.0
    thrust: float = 0.0
    strafe: float = 0.0
    boost: bool = False
    fire_primary: bool = False
    fire_secondary: bool = False
    pressed: set = field(default_factory=set)
    from_gamepad: bool = False


class Controller:
    def __init__(self, base, settings):
        self.base = base
        self.settings = settings
        self.captured = False
        self.skip_frames = 0
        self.prev: set = set()
        self.gamepad = None
        self.handles: dict = {}
        self.reload_bindings()
        self._find_gamepad()
        base.accept("connect-device", lambda dev: self._find_gamepad())
        base.accept("disconnect-device", lambda dev: self._find_gamepad())

    def reload_bindings(self) -> None:
        registry = ButtonRegistry.ptr()
        self.handles = {}
        for action, keys in self.settings["bindings"].items():
            handles = []
            for key in keys:
                handle = registry.findButton(key)
                if handle and handle.getName() != "none":
                    handles.append(handle)
            self.handles[action] = handles

    def refresh_gamepad(self) -> None:
        self._find_gamepad()

    def _find_gamepad(self) -> None:
        self.gamepad = None
        if not self.settings["gamepad_enabled"]:
            return
        try:
            pads = self.base.devices.getDevices(InputDevice.DeviceClass.gamepad)
        except Exception:  # noqa: BLE001 - sin soporte de dispositivos
            pads = []
        if pads:
            self.gamepad = pads[0]

    # --- ratón ----------------------------------------------------------------
    def capture(self, enabled: bool) -> None:
        if not self.base.win:
            return
        props = WindowProperties()
        props.setCursorHidden(enabled)
        props.setMouseMode(WindowProperties.M_confined if enabled else WindowProperties.M_absolute)
        self.base.win.requestProperties(props)
        self.captured = enabled
        self.skip_frames = 2
        if enabled:
            self._recenter()

    def _recenter(self) -> None:
        win = self.base.win
        win.movePointer(0, win.getXSize() // 2, win.getYSize() // 2)

    def is_down(self, action: str) -> bool:
        watcher = self.base.mouseWatcherNode
        return any(watcher.isButtonDown(h) for h in self.handles.get(action, ()))

    # --- lectura --------------------------------------------------------------
    def poll(self) -> InputState:
        state = InputState()
        sens = float(self.settings["mouse_sensitivity"]) * 0.085
        if self.captured and self.base.win and self.base.win.getProperties().getForeground():
            pointer = self.base.win.getPointer(0)
            cx, cy = self.base.win.getXSize() // 2, self.base.win.getYSize() // 2
            dx, dy = pointer.getX() - cx, pointer.getY() - cy
            if self.skip_frames > 0:
                self.skip_frames -= 1
                dx = dy = 0
            self._recenter()
            invert = -1.0 if self.settings["invert_y"] else 1.0
            state.yaw = -dx * sens
            state.pitch = -dy * sens * invert
        state.thrust = float(self.is_down("thrust_forward")) - float(self.is_down("thrust_back"))
        state.strafe = float(self.is_down("strafe_right")) - float(self.is_down("strafe_left"))
        state.roll = float(self.is_down("roll_right")) - float(self.is_down("roll_left"))
        state.boost = self.is_down("boost")
        state.fire_primary = self.is_down("fire_primary")
        state.fire_secondary = self.is_down("fire_secondary")
        now = {a for a in EDGE_ACTIONS if self.is_down(a)}
        if self.gamepad is not None:
            self._poll_gamepad(state, now)
        state.pressed = now - self.prev
        self.prev = now
        return state

    def _poll_gamepad(self, state: InputState, now: set) -> None:
        pad = self.gamepad
        dead = 0.18
        try:
            def axis(a):
                v = pad.findAxis(a).value
                return 0.0 if abs(v) < dead else v

            lx, ly = axis(InputDevice.Axis.left_x), axis(InputDevice.Axis.left_y)
            rx, ry = axis(InputDevice.Axis.right_x), axis(InputDevice.Axis.right_y)
            rt, lt = axis(InputDevice.Axis.right_trigger), axis(InputDevice.Axis.left_trigger)
            if lx or ly:
                state.from_gamepad = True
                dt = ClockObject.getGlobalClock().getDt()
                state.yaw += -lx * 120 * dt
                state.pitch += ly * 120 * dt * (-1 if self.settings["invert_y"] else 1)
            state.strafe = state.strafe or rx
            state.thrust = state.thrust or ry
            state.fire_primary = state.fire_primary or rt > 0.4
            state.fire_secondary = state.fire_secondary or lt > 0.4

            def button(name):
                b = pad.findButton(name)
                return bool(b and b.pressed)

            state.boost = state.boost or button("face_a")
            if button("lshoulder"):
                state.roll = -1
            if button("rshoulder"):
                state.roll = 1
            for name, action in (("face_b", "evade"), ("face_x", "fire_special"), ("face_y", "target_next"),
                                 ("dpad_up", "weapon_next"), ("start", "pause")):
                if button(name):
                    now.add(action)
        except Exception:  # noqa: BLE001 - un mando raro no debe tumbar el juego
            self.gamepad = None

    def destroy(self) -> None:
        self.base.ignore("connect-device")
        self.base.ignore("disconnect-device")
        self.capture(False)
