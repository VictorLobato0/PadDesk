"""XInput + winmm + HID raw input, with teachable M1–M4 paddle mapping."""

from __future__ import annotations

import time
import ctypes
from ctypes import POINTER, Structure, byref, c_char, c_short, c_ubyte, c_uint, c_ushort, c_ulong, sizeof

import hid_raw

BUTTONS = [
    ("DUP", 0x0001),
    ("DDOWN", 0x0002),
    ("DLEFT", 0x0004),
    ("DRIGHT", 0x0008),
    ("START", 0x0010),
    ("BACK", 0x0020),
    ("LS", 0x0040),
    ("RS", 0x0080),
    ("LB", 0x0100),
    ("RB", 0x0200),
    ("A", 0x1000),
    ("B", 0x2000),
    ("X", 0x4000),
    ("Y", 0x8000),
]

XINPUT_GUIDE = 0x0400
XINPUT_EXTRA = 0x0800
ERROR_SUCCESS = 0
ERROR_DEVICE_NOT_CONNECTED = 1167
JOYERR_NOERROR = 0
JOY_RETURNALL = 0xFF
MAXPNAMELEN = 32
MAX_JOYSTICKOEMVXDNAME = 260

# Common extra-button slots used by 8BitDo / generic pads.
AUTO_M = {
    "M1": {"winmm": (10, 12), "hid": (11, 13)},
    "M2": {"winmm": (11, 13), "hid": (12, 14)},
    "M3": {"winmm": (14,), "hid": (15,)},
    "M4": {"winmm": (15,), "hid": (16,)},
}


class XINPUT_GAMEPAD(Structure):
    _fields_ = [
        ("wButtons", c_ushort),
        ("bLeftTrigger", c_ubyte),
        ("bRightTrigger", c_ubyte),
        ("sThumbLX", c_short),
        ("sThumbLY", c_short),
        ("sThumbRX", c_short),
        ("sThumbRY", c_short),
    ]


class XINPUT_STATE(Structure):
    _fields_ = [("dwPacketNumber", c_ulong), ("Gamepad", XINPUT_GAMEPAD)]


class JOYINFOEX(Structure):
    _fields_ = [
        ("dwSize", c_ulong),
        ("dwFlags", c_ulong),
        ("dwXpos", c_ulong),
        ("dwYpos", c_ulong),
        ("dwZpos", c_ulong),
        ("dwRpos", c_ulong),
        ("dwUpos", c_ulong),
        ("dwVpos", c_ulong),
        ("dwButtons", c_ulong),
        ("dwButtonNumber", c_ulong),
        ("dwPOV", c_ulong),
        ("dwReserved1", c_ulong),
        ("dwReserved2", c_ulong),
    ]


class JOYCAPS(Structure):
    _fields_ = [
        ("wMid", c_ushort),
        ("wPid", c_ushort),
        ("szPname", c_char * MAXPNAMELEN),
        ("wXmin", c_uint),
        ("wXmax", c_uint),
        ("wYmin", c_uint),
        ("wYmax", c_uint),
        ("wZmin", c_uint),
        ("wZmax", c_uint),
        ("wNumButtons", c_uint),
        ("wPeriodMin", c_uint),
        ("wPeriodMax", c_uint),
        ("wRmin", c_uint),
        ("wRmax", c_uint),
        ("wUmin", c_uint),
        ("wUmax", c_uint),
        ("wVmin", c_uint),
        ("wVmax", c_uint),
        ("wCaps", c_uint),
        ("wMaxAxes", c_uint),
        ("wNumAxes", c_uint),
        ("wMaxButtons", c_uint),
        ("szRegKey", c_char * MAXPNAMELEN),
        ("szOEMVxD", c_char * MAX_JOYSTICKOEMVXDNAME),
    ]


def _load_xinput():
    for name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
        try:
            return ctypes.WinDLL(name)
        except OSError:
            continue
    return None


_xinput = _load_xinput()
_get_state_ex = None
if _xinput is not None:
    _xinput.XInputGetState.argtypes = (c_ulong, POINTER(XINPUT_STATE))
    _xinput.XInputGetState.restype = c_ulong
    try:
        proto = ctypes.WINFUNCTYPE(c_ulong, c_ulong, POINTER(XINPUT_STATE))
        _get_state_ex = proto((100, _xinput))
    except Exception:
        _get_state_ex = None

_winmm = ctypes.WinDLL("winmm")
_winmm.joyGetPosEx.argtypes = (c_uint, POINTER(JOYINFOEX))
_winmm.joyGetPosEx.restype = c_uint
_winmm.joyGetDevCapsA.argtypes = (c_uint, POINTER(JOYCAPS), c_uint)
_winmm.joyGetDevCapsA.restype = c_uint


def start() -> None:
    hid_raw.start()


def _axis(value: int) -> float:
    if value == -32768:
        return -1.0
    return max(-1.0, min(1.0, value / 32767.0))


def _winmm_joys() -> list[dict]:
    out = []
    info = JOYINFOEX()
    for index in range(16):
        info.dwSize = sizeof(JOYINFOEX)
        info.dwFlags = JOY_RETURNALL
        if _winmm.joyGetPosEx(index, byref(info)) != JOYERR_NOERROR:
            continue
        bits = int(info.dwButtons)
        extra = [b for b in range(32) if bits & (1 << b)]
        out.append({"id": index, "buttons": bits, "pressed": extra})
    return out


def _signal_set(snap: dict) -> set[str]:
    keys: set[str] = set()
    xib = int(snap.get("xinput") or 0)
    if xib & XINPUT_GUIDE:
        keys.add("xinput:guide")
    if xib & XINPUT_EXTRA:
        keys.add("xinput:extra")
    for joy in snap.get("winmm") or []:
        for bit in joy.get("pressed") or []:
            if bit >= 8:
                keys.add(f"winmm:{joy['id']}:{bit}")
    for hid in snap.get("hid") or []:
        keys.add(f"hid:{hid['page']}:{hid['usage']}")
    return keys


def parse_signal(sig: str) -> dict:
    parts = sig.split(":")
    if parts[0] == "xinput":
        return {"src": "xinput", "bit": parts[1]}
    if parts[0] == "winmm":
        return {"src": "winmm", "joy": int(parts[1]), "bit": int(parts[2])}
    return {"src": "hid", "page": int(parts[1]), "usage": int(parts[2])}


def signal_down(spec: dict, snap: dict) -> bool:
    src = spec.get("src")
    if src == "xinput":
        xib = int(snap.get("xinput") or 0)
        if spec.get("bit") == "guide":
            return bool(xib & XINPUT_GUIDE)
        return bool(xib & XINPUT_EXTRA)
    if src == "winmm":
        joy_id = int(spec.get("joy", 0))
        bit = int(spec.get("bit", 0))
        for joy in snap.get("winmm") or []:
            if joy["id"] == joy_id and joy["buttons"] & (1 << bit):
                return True
        return False
    if src == "hid":
        page = int(spec.get("page", 9))
        usage = int(spec.get("usage", 0))
        return any(h["page"] == page and h["usage"] == usage for h in (snap.get("hid") or []))
    return False


def raw_snapshot(user_index: int = 0) -> dict | None:
    if _xinput is None:
        return None
    state = XINPUT_STATE()
    getter = _get_state_ex or _xinput.XInputGetState
    result = getter(user_index, byref(state))
    if result not in (ERROR_SUCCESS, ERROR_DEVICE_NOT_CONNECTED) and _get_state_ex is not None:
        result = _xinput.XInputGetState(user_index, byref(state))
    if result == ERROR_DEVICE_NOT_CONNECTED:
        return None
    if result != ERROR_SUCCESS:
        return None
    pad = state.Gamepad
    hid = hid_raw.current_usages()
    winmm = _winmm_joys()
    extra_hid = [h for h in hid if h["usage"] >= 11 or h["page"] != 9]
    extra_winmm = []
    for joy in winmm:
        extra_winmm.extend(b for b in joy["pressed"] if b >= 8)
    return {
        "connected": True,
        "packet": int(state.dwPacketNumber),
        "xinput": int(pad.wButtons),
        "standard": {name: bool(pad.wButtons & mask) for name, mask in BUTTONS},
        "axes": {
            "lx": _axis(pad.sThumbLX),
            "ly": -_axis(pad.sThumbLY),
            "rx": _axis(pad.sThumbRX),
            "ry": -_axis(pad.sThumbRY),
            "lt": pad.bLeftTrigger / 255.0,
            "rt": pad.bRightTrigger / 255.0,
        },
        "winmm": winmm,
        "hid": hid,
        "debug": {
            "xinput": f"0x{pad.wButtons:04X}",
            "winmmExtra": extra_winmm,
            "hid": [f"{h['page']}:{h['usage']}" for h in extra_hid] or [f"{h['page']}:{h['usage']}" for h in hid if h["usage"] >= 11],
        },
    }


def _auto_paddles(snap: dict) -> dict[str, bool]:
    hid_usages = {(h["page"], h["usage"]) for h in (snap.get("hid") or [])}
    winmm_bits = set()
    for joy in snap.get("winmm") or []:
        winmm_bits.update(joy.get("pressed") or [])
    xib = int(snap.get("xinput") or 0)
    out = {}
    for name, slots in AUTO_M.items():
        hid_hit = any((9, u) in hid_usages for u in slots["hid"])
        win_hit = any(b in winmm_bits for b in slots["winmm"])
        out[name] = hid_hit or win_hit
    out["M1"] = out["M1"] or bool(xib & XINPUT_GUIDE)
    out["M2"] = out["M2"] or bool(xib & XINPUT_EXTRA)
    return out


def poll(user_index: int = 0, paddle_map: dict | None = None) -> dict | None:
    snap = raw_snapshot(user_index)
    if not snap:
        return None
    pressed = dict(snap["standard"])
    auto = _auto_paddles(snap)
    for name in ("M1", "M2", "M3", "M4"):
        spec = (paddle_map or {}).get(name)
        pressed[name] = signal_down(spec, snap) if spec else auto[name]
    return {
        "connected": True,
        "packet": snap["packet"],
        "buttons": pressed,
        "axes": snap["axes"],
        "debug": snap["debug"],
        "paddleMap": paddle_map or {},
    }


def learn_paddle(name: str, timeout_s: float = 6.0) -> dict | None:
    snap = raw_snapshot()
    if not snap:
        return None
    baseline = _signal_set(snap)
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        snap = raw_snapshot()
        if not snap:
            time.sleep(0.02)
            continue
        new = _signal_set(snap) - baseline
        if new:
            sig = sorted(new)[0]
            return parse_signal(sig)
        time.sleep(0.02)
    return None
