"""Timed playback of mouse/keyboard sequences."""

from __future__ import annotations

import threading
from typing import Callable

import injector


class Sequencer:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._playing = False
        self._index = -1
        self._name = ""
        self._repeat_left = 0
        self._on_change: Callable[[], None] | None = None

    def status(self) -> dict:
        return {
            "playing": self._playing,
            "index": self._index,
            "name": self._name,
            "repeatLeft": self._repeat_left,
        }

    def play(self, sequence: dict, on_change: Callable[[], None] | None = None) -> bool:
        if self._playing:
            return False
        self._on_change = on_change
        self._stop.clear()
        self._playing = True
        self._name = sequence.get("name", "")
        self._thread = threading.Thread(target=self._run, args=(sequence,), daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()

    def _should_stop(self) -> bool:
        return self._stop.is_set() or injector.panic_pressed()

    def _run(self, sequence: dict) -> None:
        try:
            repeats = max(1, int(sequence.get("repeat", 1)))
            self._repeat_left = repeats
            start_delay = int(sequence.get("startDelayMs", 1000))
            if not injector.interruptible_sleep(start_delay, self._should_stop):
                return
            for remaining in range(repeats, 0, -1):
                if self._should_stop():
                    return
                self._repeat_left = remaining
                steps = list(sequence.get("steps") or [])
                for i, step in enumerate(steps):
                    if self._should_stop():
                        return
                    self._index = i
                    if self._on_change:
                        self._on_change()
                    if not self._run_step(step):
                        return
        finally:
            self._playing = False
            self._index = -1
            self._repeat_left = 0
            if self._on_change:
                self._on_change()

    def _run_step(self, step: dict) -> bool:
        kind = step.get("type", "wait")
        ms = max(0, int(step.get("ms") or 0))
        if kind == "wait":
            return injector.interruptible_sleep(ms, self._should_stop)
        if kind == "mouse_move":
            return injector.move_absolute_smooth(
                int(step.get("x", 0)),
                int(step.get("y", 0)),
                ms,
                self._should_stop,
            )
        if kind == "mouse_click":
            return injector.click(step.get("button", "left"), ms, self._should_stop)
        if kind == "mouse_down":
            injector.mouse_down(step.get("button", "left"))
            return injector.interruptible_sleep(ms, self._should_stop)
        if kind == "mouse_up":
            injector.mouse_up(step.get("button", "left"))
            return injector.interruptible_sleep(ms, self._should_stop)
        if kind == "key_tap":
            vk = injector.resolve_vk(step.get("key", ""))
            if not vk:
                return injector.interruptible_sleep(ms, self._should_stop)
            return injector.tap_key(vk, ms, self._should_stop)
        if kind == "key_down":
            injector.key_down(injector.resolve_vk(step.get("key", "")))
            return injector.interruptible_sleep(ms, self._should_stop)
        if kind == "key_up":
            injector.key_up(injector.resolve_vk(step.get("key", "")))
            return injector.interruptible_sleep(ms, self._should_stop)
        if kind == "wheel":
            injector.mouse_wheel(int(step.get("delta", 120)))
            return injector.interruptible_sleep(ms, self._should_stop)
        return True

    def run_one(self, step: dict) -> None:
        if self._playing:
            return
        self._stop.clear()
        if not injector.interruptible_sleep(400, self._should_stop):
            return
        self._run_step(step)
