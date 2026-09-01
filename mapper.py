"""Translate live gamepad state into mouse/keyboard events."""

from __future__ import annotations

import math
import threading
import time

import gamepad
import injector

WASD = {"up": "W", "down": "S", "left": "A", "right": "D"}
ARROWS = {"up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT"}


def _deadzone(value: float, zone: float) -> float:
    mag = abs(value)
    if mag <= zone:
        return 0.0
    scaled = (mag - zone) / (1.0 - zone)
    return math.copysign(scaled, value)


def _curve(value: float, mode: str) -> float:
    if mode == "quadratic":
        return math.copysign(value * value, value)
    if mode == "cubic":
        return value * value * value
    return value


class Mapper:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._config: dict = {}
        self._enabled = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._held_keys: set[int] = set()
        self._stick_keys: set[int] = set()
        self._held_mouse: set[str] = set()
        self._prev_buttons: dict[str, bool] = {}
        self._prev_triggers = {"LT": False, "RT": False}
        self._on_enabled_change = None
        self._on_sequence = None

    def set_on_enabled_change(self, callback) -> None:
        self._on_enabled_change = callback

    def set_on_sequence(self, callback) -> None:
        self._on_sequence = callback

    def set_config(self, config: dict) -> None:
        with self._lock:
            self._config = config

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if not enabled:
            self._release_all()

    def enabled(self) -> bool:
        return self._enabled

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._release_all()

    def _loop(self) -> None:
        last = time.perf_counter()
        while not self._stop.is_set():
            now = time.perf_counter()
            dt = now - last
            last = now
            if injector.mapping_toggle_edge():
                self.set_enabled(not self._enabled)
                if self._on_enabled_change:
                    self._on_enabled_change(self._enabled)
            if self._enabled:
                self._tick(dt)
            time.sleep(0.008)

    def _tick(self, dt: float) -> None:
        with self._lock:
            cfg = dict(self._config)
        pad = gamepad.poll(paddle_map=cfg.get("paddleMap"))
        if not pad:
            self._release_all()
            return

        dz = float(cfg.get("deadzone", 0.12))
        curve = str(cfg.get("curve", "quadratic"))
        sensitivity = float(cfg.get("sensitivity", 12.0))
        invert_y = bool(cfg.get("invertY", False))
        trigger_th = float(cfg.get("triggerThreshold", 0.35))

        axes = pad["axes"]
        used_digital = False
        for stick_key, axis_x, axis_y in (
            ("leftStick", "lx", "ly"),
            ("rightStick", "rx", "ry"),
        ):
            mode = cfg.get(stick_key, "off")
            x = _curve(_deadzone(axes[axis_x], dz), curve)
            y = _curve(_deadzone(axes[axis_y], dz), curve)
            if mode == "mouse":
                my = -y if invert_y else y
                injector.move_relative(
                    int(round(x * sensitivity * dt * 125)),
                    int(round(my * sensitivity * dt * 125)),
                )
            elif mode in ("wasd", "arrows"):
                used_digital = True
                layout = WASD if mode == "wasd" else ARROWS
                self._digital_stick(x, y, layout)
        if not used_digital:
            for vk in list(self._stick_keys):
                injector.key_up(vk)
                self._stick_keys.discard(vk)

        binds = cfg.get("binds", {})
        buttons = pad["buttons"]
        for name, down in buttons.items():
            prev = self._prev_buttons.get(name, False)
            if down == prev:
                continue
            bind = binds.get(name) or {"kind": "none"}
            if down:
                self._apply_bind(bind, True)
            else:
                self._apply_bind(bind, False)
        self._prev_buttons = dict(buttons)

        for trig, axis in (("LT", "lt"), ("RT", "rt")):
            down = axes[axis] >= trigger_th
            prev = self._prev_triggers.get(trig, False)
            if down != prev:
                bind = binds.get(trig) or {"kind": "none"}
                self._apply_bind(bind, down)
            self._prev_triggers[trig] = down

    def _digital_stick(self, x: float, y: float, layout: dict[str, str]) -> None:
        threshold = 0.4
        wanted = {
            layout["right"]: x > threshold,
            layout["left"]: x < -threshold,
            layout["down"]: y > threshold,
            layout["up"]: y < -threshold,
        }
        for key_name, down in wanted.items():
            vk = injector.resolve_vk(key_name)
            if down and vk not in self._stick_keys:
                injector.key_down(vk)
                self._stick_keys.add(vk)
            elif not down and vk in self._stick_keys:
                injector.key_up(vk)
                self._stick_keys.discard(vk)

    def _apply_bind(self, bind: dict, down: bool) -> None:
        kind = (bind or {}).get("kind", "none")
        if kind == "key":
            vk = injector.resolve_vk(bind.get("key", ""))
            if not vk:
                return
            if down and vk not in self._held_keys:
                injector.key_down(vk)
                self._held_keys.add(vk)
            elif not down and vk in self._held_keys:
                injector.key_up(vk)
                self._held_keys.discard(vk)
        elif kind == "mouse":
            button = bind.get("button", "left")
            if down and button not in self._held_mouse:
                injector.mouse_down(button)
                self._held_mouse.add(button)
            elif not down and button in self._held_mouse:
                injector.mouse_up(button)
                self._held_mouse.discard(button)
        elif kind == "sequence" and down and self._on_sequence:
            seq_id = bind.get("sequenceId")
            if seq_id:
                self._on_sequence(seq_id)

    def _release_all(self) -> None:
        for vk in list(self._held_keys | self._stick_keys):
            injector.key_up(vk)
        self._held_keys.clear()
        self._stick_keys.clear()
        for button in list(self._held_mouse):
            injector.mouse_up(button)
        self._held_mouse.clear()
        self._prev_buttons.clear()
        self._prev_triggers = {"LT": False, "RT": False}
