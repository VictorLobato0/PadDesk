"""Windows mouse/keyboard injection via SendInput + SetCursorPos."""

from __future__ import annotations

import ctypes
import time
from ctypes import (
    POINTER,
    Structure,
    Union,
    byref,
    c_long,
    c_ulong,
    c_ulonglong,
    c_ushort,
    c_void_p,
    sizeof,
)
from typing import Callable

user32 = ctypes.WinDLL("user32", use_last_error=True)

ULONG_PTR = c_ulonglong if sizeof(c_void_p) == 8 else c_ulong

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

MAPVK_VK_TO_VSC = 0

MOUSE_FLAGS = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}

EXTENDED_VKS = {
    0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E,  # pg/home/arrows/ins/del
    0xA3, 0xA5,  # RCTRL, RALT
}

KEY_MAP = {
    "NONE": 0,
    "A": 0x41, "B": 0x42, "C": 0x43, "D": 0x44, "E": 0x45, "F": 0x46,
    "G": 0x47, "H": 0x48, "I": 0x49, "J": 0x4A, "K": 0x4B, "L": 0x4C,
    "M": 0x4D, "N": 0x4E, "O": 0x4F, "P": 0x50, "Q": 0x51, "R": 0x52,
    "S": 0x53, "T": 0x54, "U": 0x55, "V": 0x56, "W": 0x57, "X": 0x58,
    "Y": 0x59, "Z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
    "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "SPACE": 0x20, "ENTER": 0x0D, "TAB": 0x09, "ESC": 0x1B, "BACKSPACE": 0x08,
    "SHIFT": 0xA0, "CTRL": 0xA2, "ALT": 0xA4,
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
    "INSERT": 0x2D, "DELETE": 0x2E, "HOME": 0x24, "END": 0x23,
    "PAGEUP": 0x21, "PAGEDOWN": 0x22,
    "NUMPAD0": 0x60, "NUMPAD1": 0x61, "NUMPAD2": 0x62, "NUMPAD3": 0x63,
    "NUMPAD4": 0x64, "NUMPAD5": 0x65, "NUMPAD6": 0x66, "NUMPAD7": 0x67,
    "NUMPAD8": 0x68, "NUMPAD9": 0x69,
}


class MOUSEINPUT(Structure):
    _fields_ = [
        ("dx", c_long),
        ("dy", c_long),
        ("mouseData", c_ulong),
        ("dwFlags", c_ulong),
        ("time", c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(Structure):
    _fields_ = [
        ("wVk", c_ushort),
        ("wScan", c_ushort),
        ("dwFlags", c_ulong),
        ("time", c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(Structure):
    _fields_ = [
        ("uMsg", c_ulong),
        ("wParamL", c_ushort),
        ("wParamH", c_ushort),
    ]


class INPUTUNION(Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(Structure):
    _fields_ = [("type", c_ulong), ("union", INPUTUNION)]


user32.SendInput.argtypes = (c_ulong, POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = c_ulong
user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
user32.SetCursorPos.restype = ctypes.c_int
user32.GetCursorPos.restype = ctypes.c_int
user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
user32.GetSystemMetrics.restype = ctypes.c_int
user32.MapVirtualKeyW.argtypes = (c_ulong, c_ulong)
user32.MapVirtualKeyW.restype = c_ulong
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short


class POINT(Structure):
    _fields_ = [("x", c_long), ("y", c_long)]


def key_names() -> list[str]:
    return list(KEY_MAP.keys())


def resolve_vk(name: str) -> int:
    if not name:
        return 0
    return KEY_MAP.get(str(name).upper(), 0)


def screen_info() -> dict:
    return {
        "x": int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN)),
        "y": int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN)),
        "w": int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)),
        "h": int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)),
    }


def cursor_pos() -> tuple[int, int]:
    pt = POINT()
    user32.GetCursorPos(byref(pt))
    return int(pt.x), int(pt.y)


_f12_was_down = False


def panic_pressed() -> bool:
    return bool(user32.GetAsyncKeyState(0x7A) & 0x8000)  # F11 stops sequences


def mapping_toggle_edge() -> bool:
    """F12 rising edge — liga/desliga o mapeamento."""
    global _f12_was_down
    down = bool(user32.GetAsyncKeyState(0x7B) & 0x8000)
    edge = down and not _f12_was_down
    _f12_was_down = down
    return edge


def _send(inputs: list[INPUT]) -> None:
    if not inputs:
        return
    arr = (INPUT * len(inputs))(*inputs)
    sent = user32.SendInput(len(inputs), arr, sizeof(INPUT))
    if sent != len(inputs):
        raise OSError(ctypes.get_last_error(), "SendInput failed")


def _mouse(flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> INPUT:
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi.dx = int(dx)
    inp.union.mi.dy = int(dy)
    inp.union.mi.mouseData = data
    inp.union.mi.dwFlags = flags
    return inp


def _key(vk: int, up: bool) -> INPUT:
    scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    flags = KEYEVENTF_SCANCODE
    if vk in EXTENDED_VKS:
        flags |= KEYEVENTF_EXTENDEDKEY
    if up:
        flags |= KEYEVENTF_KEYUP
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki.wVk = 0
    inp.union.ki.wScan = scan
    inp.union.ki.dwFlags = flags
    return inp


def move_relative(dx: int, dy: int) -> None:
    if dx == 0 and dy == 0:
        return
    _send([_mouse(MOUSEEVENTF_MOVE, dx, dy)])


def move_absolute(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def mouse_down(button: str) -> None:
    down, _ = MOUSE_FLAGS.get(button, MOUSE_FLAGS["left"])
    _send([_mouse(down)])


def mouse_up(button: str) -> None:
    _, up = MOUSE_FLAGS.get(button, MOUSE_FLAGS["left"])
    _send([_mouse(up)])


def mouse_wheel(delta: int) -> None:
    _send([_mouse(MOUSEEVENTF_WHEEL, data=int(delta))])


def key_down(vk: int) -> None:
    if vk:
        _send([_key(vk, up=False)])


def key_up(vk: int) -> None:
    if vk:
        _send([_key(vk, up=True)])


def interruptible_sleep(ms: int, should_stop: Callable[[], bool] | None = None) -> bool:
    if ms <= 0:
        return not (should_stop and should_stop())
    deadline = time.perf_counter() + (ms / 1000.0)
    while time.perf_counter() < deadline:
        if should_stop and should_stop():
            return False
        remaining = deadline - time.perf_counter()
        time.sleep(min(0.01, max(0.0, remaining)))
    return True


def move_absolute_smooth(
    x: int,
    y: int,
    duration_ms: int,
    should_stop: Callable[[], bool] | None = None,
) -> bool:
    x0, y0 = cursor_pos()
    if duration_ms <= 0:
        move_absolute(x, y)
        return True
    steps = max(1, int(duration_ms / 8))
    for i in range(1, steps + 1):
        if should_stop and should_stop():
            return False
        t = i / steps
        move_absolute(int(x0 + (x - x0) * t), int(y0 + (y - y0) * t))
        if not interruptible_sleep(duration_ms / steps, should_stop):
            return False
    move_absolute(x, y)
    return True


def click(button: str, hold_ms: int, should_stop: Callable[[], bool] | None = None) -> bool:
    mouse_down(button)
    if not interruptible_sleep(max(hold_ms, 20), should_stop):
        mouse_up(button)
        return False
    mouse_up(button)
    return True


def tap_key(vk: int, hold_ms: int, should_stop: Callable[[], bool] | None = None) -> bool:
    key_down(vk)
    if not interruptible_sleep(max(hold_ms, 20), should_stop):
        key_up(vk)
        return False
    key_up(vk)
    return True
