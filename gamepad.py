"""Xbox (XInput) + PlayStation (HID Sony) + generic DirectInput/winmm pads."""

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

FACE = ("A", "B", "X", "Y", "LB", "RB", "BACK", "START", "LS", "RS", "DUP", "DDOWN", "DLEFT", "DRIGHT")

XINPUT_GUIDE = 0x0400
XINPUT_EXTRA = 0x0800
ERROR_SUCCESS = 0
ERROR_DEVICE_NOT_CONNECTED = 1167
JOYERR_NOERROR = 0
JOY_RETURNALL = 0xFF
JOYCAPS_HASZ = 0x0001
JOYCAPS_HASR = 0x0002
JOYCAPS_HASU = 0x0004
JOYCAPS_HASV = 0x0008
JOYCAPS_HASPOV = 0x0010
MAXPNAMELEN = 32
MAX_JOYSTICKOEMVXDNAME = 260

SONY_VID = 0x054C
MS_VID = 0x045E
SONY_NAMES = {
    0x0268: "PlayStation DualShock 3",
    0x05C4: "PlayStation DualShock 4",
    0x09CC: "PlayStation DualShock 4",
    0x0BA0: "PlayStation DualShock 4",
    0x0CE6: "PlayStation DualSense",
    0x0DF2: "PlayStation DualSense Edge",
}
DS4_PIDS = {0x05C4, 0x09CC, 0x0BA0}
DS5_PIDS = {0x0CE6, 0x0DF2}

AUTO_M = {
    "M1": {"winmm": (10, 12), "hid": (11, 13)},
    "M2": {"winmm": (11, 13), "hid": (12, 14)},
    "M3": {"winmm": (14,), "hid": (15,)},
    "M4": {"winmm": (15,), "hid": (16,)},
}

HAT_MAP = {
    0: ("DUP",),
    1: ("DUP", "DRIGHT"),
    2: ("DRIGHT",),
    3: ("DDOWN", "DRIGHT"),
    4: ("DDOWN",),
    5: ("DDOWN", "DLEFT"),
    6: ("DLEFT",),
    7: ("DUP", "DLEFT"),
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
        ("wRmin", c_uint),
        ("wRmax", c_uint),
        ("wUmin", c_uint),
        ("wUmax", c_uint),
        ("wVmin", c_uint),
        ("wVmax", c_uint),
        ("wNumButtons", c_uint),
        ("wPeriodMin", c_uint),
        ("wPeriodMax", c_uint),
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


def _u8_stick(value: int, invert: bool = False) -> float:
    centered = (value - 128) / 127.0 if value >= 128 else (value - 128) / 128.0
    if invert:
        centered = -centered
    return max(-1.0, min(1.0, centered))


def _empty_buttons() -> dict[str, bool]:
    return {name: False for name in FACE}


def _hat_buttons(hat: int) -> dict[str, bool]:
    out = {"DUP": False, "DDOWN": False, "DLEFT": False, "DRIGHT": False}
    for name in HAT_MAP.get(int(hat), ()):
        out[name] = True
    return out


def _pov_buttons(pov: int) -> dict[str, bool]:
    if pov in (0xFFFF, 0xFFFFFFFF) or pov > 35900:
        return _hat_buttons(8)
    return _hat_buttons(int(round(pov / 4500.0)) % 8)


def _norm_axis(value: int) -> float:
    if value < 0:
        return max(-1.0, min(1.0, value / 32767.0))
    if value <= 255:
        return max(-1.0, min(1.0, (value - 127.5) / 127.5))
    if value <= 4095:
        return max(-1.0, min(1.0, (value - 2047.5) / 2047.5))
    return max(-1.0, min(1.0, (value - 32767.5) / 32767.5))


def _norm_trigger(value: int) -> float:
    if value <= 0:
        return 0.0
    if value <= 255:
        return min(1.0, value / 255.0)
    if value <= 1023:
        return min(1.0, value / 1023.0)
    return min(1.0, value / 65535.0)


def _joy_axis(pos: int, lo: int, hi: int) -> float:
    if hi <= lo:
        return 0.0
    mid = (lo + hi) / 2.0
    span = (hi - lo) / 2.0
    return max(-1.0, min(1.0, (pos - mid) / span))


def _sony_name(pid: int) -> str:
    return SONY_NAMES.get(pid, "PlayStation")


def _parse_sony_face(btn0: int, btn1: int) -> dict[str, bool]:
    pressed = _empty_buttons()
    pressed.update(_hat_buttons(btn0 & 0x0F))
    pressed["X"] = bool(btn0 & 0x10)       # Square
    pressed["A"] = bool(btn0 & 0x20)       # Cross
    pressed["B"] = bool(btn0 & 0x40)       # Circle
    pressed["Y"] = bool(btn0 & 0x80)       # Triangle
    pressed["LB"] = bool(btn1 & 0x01)      # L1
    pressed["RB"] = bool(btn1 & 0x02)      # R1
    pressed["BACK"] = bool(btn1 & 0x10)    # Share / Create
    pressed["START"] = bool(btn1 & 0x20)   # Options
    pressed["LS"] = bool(btn1 & 0x40)
    pressed["RS"] = bool(btn1 & 0x80)
    return pressed


def _pack_sony(name: str, pressed: dict, lx, ly, rx, ry, lt, rt, report: bytes) -> dict:
    return {
        "connected": True,
        "packet": 0,
        "name": name,
        "source": "sony-hid",
        "xinput": 0,
        "standard": pressed,
        "axes": {
            "lx": _u8_stick(lx),
            "ly": _u8_stick(ly),
            "rx": _u8_stick(rx),
            "ry": _u8_stick(ry),
            "lt": lt / 255.0,
            "rt": rt / 255.0,
        },
        "winmm": [],
        "hid": hid_raw.current_usages(),
        "debug": {"source": "sony-hid", "name": name, "hid": [f"len:{len(report)}"]},
    }


def _parse_ds4(report: bytes, pid: int) -> dict | None:
    if report[0] == 0x11 and len(report) >= 14:
        r = report[3:] if len(report) > 14 and report[2] == 0x01 else report[2:]
        if len(r) < 10:
            return None
        return _pack_sony(_sony_name(pid), _parse_sony_face(r[5], r[6]), r[1], r[2], r[3], r[4], r[8], r[9], report)
    if report[0] == 0x01 and len(report) >= 10:
        r = report
        return _pack_sony(_sony_name(pid), _parse_sony_face(r[5], r[6]), r[1], r[2], r[3], r[4], r[8], r[9], report)
    if len(report) >= 9:
        r = report
        return _pack_sony(_sony_name(pid), _parse_sony_face(r[4], r[5]), r[0], r[1], r[2], r[3], r[7], r[8], report)
    return None


def _parse_dualsense(report: bytes, pid: int) -> dict | None:
    if len(report) < 12:
        return None
    if report[0] == 0x31 and len(report) >= 16:
        r = report[1:]
        return _pack_sony(_sony_name(pid), _parse_sony_face(r[8], r[9]), r[1], r[2], r[3], r[4], r[5], r[6], report)
    r = report
    if report[0] == 0x01:
        return _pack_sony(_sony_name(pid), _parse_sony_face(r[8], r[9]), r[1], r[2], r[3], r[4], r[5], r[6], report)
    if len(report) >= 10:
        return _pack_sony(_sony_name(pid), _parse_sony_face(r[7], r[8]), r[0], r[1], r[2], r[3], r[4], r[5], report)
    return None


def _parse_ds3(report: bytes, pid: int) -> dict | None:
    if len(report) < 10:
        return None
    off = 0
    if report[0] in (0x01, 0x00) and len(report) > 20:
        off = 0
    b2 = report[2 + off] if len(report) > 4 else 0
    b3 = report[3 + off] if len(report) > 4 else 0
    pressed = _empty_buttons()
    pressed["BACK"] = bool(b2 & 0x01)
    pressed["LS"] = bool(b2 & 0x02)
    pressed["RS"] = bool(b2 & 0x04)
    pressed["START"] = bool(b2 & 0x08)
    pressed["DUP"] = bool(b2 & 0x10)
    pressed["DRIGHT"] = bool(b2 & 0x20)
    pressed["DDOWN"] = bool(b2 & 0x40)
    pressed["DLEFT"] = bool(b2 & 0x80)
    pressed["LB"] = bool(b3 & 0x04)
    pressed["RB"] = bool(b3 & 0x08)
    pressed["Y"] = bool(b3 & 0x10)
    pressed["B"] = bool(b3 & 0x20)
    pressed["A"] = bool(b3 & 0x40)
    pressed["X"] = bool(b3 & 0x80)
    lx, ly, rx, ry = report[6], report[7], report[8], report[9]
    lt = report[18] if len(report) > 18 else (255 if b3 & 0x01 else 0)
    rt = report[19] if len(report) > 19 else (255 if b3 & 0x02 else 0)
    return _pack_sony(_sony_name(pid), pressed, lx, ly, rx, ry, lt, rt, report)


def _parse_sony_report(vid: int, pid: int, report: bytes) -> dict | None:
    if vid != SONY_VID or not report:
        return None
    if pid == 0x0268:
        return _parse_ds3(report, pid)
    if pid in DS5_PIDS:
        return _parse_dualsense(report, pid) or _parse_ds4(report, pid)
    if pid in DS4_PIDS:
        return _parse_ds4(report, pid) or _parse_dualsense(report, pid)
    return _parse_dualsense(report, pid) or _parse_ds4(report, pid) or _parse_ds3(report, pid)


def _generic_hid_pad(dev: dict) -> dict | None:
    report = dev.get("report") or b""
    values = dev.get("values") or {}
    buttons = {(b["page"], b["usage"]) for b in (dev.get("buttons") or [])}
    if not report and not values and not buttons:
        return None
    pressed = _empty_buttons()
    generic = {
        1: "A", 2: "B", 3: "X", 4: "Y",
        5: "LB", 6: "RB", 7: "BACK", 8: "START",
        9: "LS", 10: "RS",
    }
    for page, usage in buttons:
        if page == 9 and usage in generic:
            pressed[generic[usage]] = True
    if 0x39 in values:
        pressed.update(_hat_buttons(values[0x39]))
    lx = _norm_axis(values.get(0x30, 128))
    ly = _norm_axis(values.get(0x31, 128))
    if 0x33 in values or 0x34 in values:
        rx = _norm_axis(values.get(0x33, 128))
        ry = _norm_axis(values.get(0x34, 128))
        lt = _norm_trigger(values.get(0x32, 0))
        rt = _norm_trigger(values.get(0x35, 0))
    else:
        rx = _norm_axis(values.get(0x32, 128))
        ry = _norm_axis(values.get(0x35, 128))
        lt = _norm_trigger(values.get(0x36, 0))
        rt = 0.0
    vid, pid = int(dev.get("vid") or 0), int(dev.get("pid") or 0)
    if vid == MS_VID:
        name = "Xbox"
    elif vid == SONY_VID:
        name = _sony_name(pid)
    else:
        name = "Controle HID"
    return {
        "connected": True,
        "packet": 0,
        "name": name,
        "source": "hid",
        "xinput": 0,
        "standard": pressed,
        "axes": {"lx": lx, "ly": ly, "rx": rx, "ry": ry, "lt": lt, "rt": rt},
        "winmm": [],
        "hid": hid_raw.current_usages(),
        "debug": {
            "source": "hid",
            "name": name,
            "hid": [f"{p}:{u}" for p, u in sorted(buttons)],
        },
    }


def _poll_hid() -> dict | None:
    devices = hid_raw.current_devices()
    sony = [d for d in devices if int(d.get("vid") or 0) == SONY_VID and d.get("report")]
    for dev in sony:
        parsed = _parse_sony_report(int(dev["vid"]), int(dev["pid"]), dev.get("report") or b"")
        if parsed:
            parsed["hid"] = hid_raw.current_usages()
            return parsed
    for dev in devices:
        if not (dev.get("values") or dev.get("buttons")):
            continue
        parsed = _generic_hid_pad(dev)
        if parsed:
            return parsed
    return None


def _xinput_snapshot(user_index: int) -> dict | None:
    if _xinput is None:
        return None
    state = XINPUT_STATE()
    getter = _get_state_ex or _xinput.XInputGetState
    result = getter(user_index, byref(state))
    if result not in (ERROR_SUCCESS, ERROR_DEVICE_NOT_CONNECTED) and _get_state_ex is not None:
        result = _xinput.XInputGetState(user_index, byref(state))
    if result != ERROR_SUCCESS:
        return None
    pad = state.Gamepad
    return {
        "connected": True,
        "packet": int(state.dwPacketNumber),
        "name": "Xbox",
        "source": "xinput",
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
        "winmm": [],
        "hid": [],
        "debug": {"source": "xinput", "xinput": f"0x{pad.wButtons:04X}", "slot": user_index},
    }


def _poll_xinput() -> dict | None:
    for index in range(4):
        snap = _xinput_snapshot(index)
        if snap:
            return snap
    return None


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


def _poll_winmm() -> dict | None:
    info = JOYINFOEX()
    caps = JOYCAPS()
    for index in range(16):
        info.dwSize = sizeof(JOYINFOEX)
        info.dwFlags = JOY_RETURNALL
        if _winmm.joyGetPosEx(index, byref(info)) != JOYERR_NOERROR:
            continue
        if _winmm.joyGetDevCapsA(index, byref(caps), sizeof(JOYCAPS)) != JOYERR_NOERROR:
            continue
        mid = int(caps.wMid)
        pid = int(caps.wPid)
        bits = int(info.dwButtons)
        pressed = _empty_buttons()
        if mid == SONY_VID:
            # DirectInput order used by Windows for DualShock / DualSense.
            mapping = {
                0: "X", 1: "A", 2: "B", 3: "Y",
                4: "LB", 5: "RB", 8: "BACK", 9: "START",
                10: "LS", 11: "RS",
            }
            name = _sony_name(pid)
            source = "winmm-sony"
            lt = 1.0 if bits & (1 << 6) else 0.0
            rt = 1.0 if bits & (1 << 7) else 0.0
        else:
            mapping = {
                0: "A", 1: "B", 2: "X", 3: "Y",
                4: "LB", 5: "RB", 6: "BACK", 7: "START",
                8: "LS", 9: "RS",
            }
            raw_name = caps.szPname.split(b"\0", 1)[0].decode("latin-1", errors="ignore").strip()
            name = raw_name or ("Xbox" if mid == MS_VID else "Controle")
            source = "winmm"
            lt = 0.0
            rt = 0.0
        for bit, face in mapping.items():
            if bits & (1 << bit):
                pressed[face] = True
        if caps.wCaps & JOYCAPS_HASPOV:
            pressed.update(_pov_buttons(int(info.dwPOV)))
        lx = _joy_axis(int(info.dwXpos), caps.wXmin, caps.wXmax)
        ly = _joy_axis(int(info.dwYpos), caps.wYmin, caps.wYmax)
        if caps.wCaps & JOYCAPS_HASZ and caps.wCaps & JOYCAPS_HASR:
            rx = _joy_axis(int(info.dwZpos), caps.wZmin, caps.wZmax)
            ry = _joy_axis(int(info.dwRpos), caps.wRmin, caps.wRmax)
        else:
            rx = ry = 0.0
        if caps.wCaps & JOYCAPS_HASU:
            lt = _joy_axis(int(info.dwUpos), caps.wUmin, caps.wUmax)
            lt = max(0.0, lt)
        if caps.wCaps & JOYCAPS_HASV:
            rt = _joy_axis(int(info.dwVpos), caps.wVmin, caps.wVmax)
            rt = max(0.0, rt)
        return {
            "connected": True,
            "packet": 0,
            "name": name,
            "source": source,
            "xinput": 0,
            "standard": pressed,
            "axes": {"lx": lx, "ly": ly, "rx": rx, "ry": ry, "lt": lt, "rt": rt},
            "winmm": [{"id": index, "buttons": bits, "pressed": [b for b in range(32) if bits & (1 << b)]}],
            "hid": hid_raw.current_usages(),
            "debug": {"source": source, "name": name, "winmmExtra": [b for b in range(32) if bits & (1 << b) and b >= 8]},
        }
    return None


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
    """Any connected pad: XInput first, then Sony HID, generic HID, then winmm."""
    xinput = _xinput_snapshot(user_index) if user_index else None
    if user_index == 0:
        xinput = _poll_xinput()
    hid_pad = _poll_hid()
    winmm = _winmm_joys()
    hid_usages = hid_raw.current_usages()

    snap = xinput or hid_pad or _poll_winmm()
    if not snap:
        return None
    snap = dict(snap)
    snap["winmm"] = winmm or snap.get("winmm") or []
    snap["hid"] = hid_usages
    extra_hid = [h for h in hid_usages if h["usage"] >= 11 or h["page"] != 9]
    extra_winmm = []
    for joy in snap["winmm"]:
        extra_winmm.extend(b for b in joy["pressed"] if b >= 8)
    debug = dict(snap.get("debug") or {})
    debug.update({
        "winmmExtra": extra_winmm,
        "hid": [f"{h['page']}:{h['usage']}" for h in extra_hid] or debug.get("hid") or [],
        "xinput": debug.get("xinput", "0x0000"),
        "source": snap.get("source", debug.get("source", "")),
        "name": snap.get("name", ""),
    })
    snap["debug"] = debug
    return snap


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
        "name": snap.get("name") or "Controle",
        "source": snap.get("source") or "",
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
