"""Background Raw Input listener for gamepads, sticks, hats and extra buttons."""

from __future__ import annotations

import ctypes
import threading
from ctypes import POINTER, Structure, Union, byref, c_byte, c_char_p, c_int, c_uint, c_ulong, c_ushort, c_void_p, sizeof
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
hid = ctypes.WinDLL("hid")

WM_INPUT = 0x00FF
WM_DESTROY = 0x0002
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100
RIDI_PREPARSEDDATA = 0x20000005
RIDI_DEVICEINFO = 0x2000000B
RIM_TYPEHID = 2
HIDP_INPUT = 0
HIDP_STATUS_SUCCESS = 0x00110000
HID_USAGE_PAGE_BUTTON = 0x09
HID_USAGE_PAGE_GENERIC = 0x01
WS_POPUP = 0x80000000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
HWND_MESSAGE = wintypes.HWND(-3)

AXIS_USAGES = (0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x39)

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
HWND = wintypes.HWND
UINT = wintypes.UINT
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)


class RAWINPUTDEVICE(Structure):
    _fields_ = [
        ("usUsagePage", c_ushort),
        ("usUsage", c_ushort),
        ("dwFlags", c_uint),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(Structure):
    _fields_ = [
        ("dwType", c_uint),
        ("dwSize", c_uint),
        ("hDevice", c_void_p),
        ("wParam", ctypes.c_size_t),
    ]


class RAWHID(Structure):
    _fields_ = [
        ("dwSizeHid", c_uint),
        ("dwCount", c_uint),
        ("bRawData", c_byte * 1),
    ]


class RAWINPUTUNION(Union):
    _fields_ = [("hid", RAWHID)]


class RAWINPUT(Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("data", RAWINPUTUNION)]


class RID_DEVICE_INFO_HID(Structure):
    _fields_ = [
        ("dwVendorId", c_uint),
        ("dwProductId", c_uint),
        ("dwVersionNumber", c_uint),
        ("usUsagePage", c_ushort),
        ("usUsage", c_ushort),
    ]


class RID_DEVICE_INFO(Structure):
    _fields_ = [
        ("cbSize", c_uint),
        ("dwType", c_uint),
        ("hid", RID_DEVICE_INFO_HID),
    ]


class WNDCLASSW(Structure):
    _fields_ = [
        ("style", c_uint),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", c_int),
        ("cbWndExtra", c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class MSG(Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


user32.RegisterClassW.argtypes = (POINTER(WNDCLASSW),)
user32.CreateWindowExW.restype = HWND
user32.DefWindowProcW.argtypes = (HWND, UINT, WPARAM, LPARAM)
user32.DefWindowProcW.restype = LRESULT
user32.GetRawInputData.argtypes = (c_void_p, c_uint, c_void_p, POINTER(c_uint), c_uint)
user32.GetRawInputDeviceInfoW.argtypes = (c_void_p, c_uint, c_void_p, POINTER(c_uint))
user32.RegisterRawInputDevices.argtypes = (POINTER(RAWINPUTDEVICE), c_uint, c_uint)

hid.HidP_GetUsages.restype = ctypes.c_long
hid.HidP_GetCaps.restype = ctypes.c_long
hid.HidP_GetUsageValue.restype = ctypes.c_long
hid.HidP_GetUsageValue.argtypes = (
    c_int, c_ushort, c_ushort, c_ushort, POINTER(c_ulong), c_void_p, c_char_p, c_ulong,
)

_lock = threading.Lock()
_usages_by_device: dict[int, set[tuple[int, int]]] = {}
_devices: dict[int, dict] = {}
_preparsed: dict[int, ctypes.Array] = {}
_started = False
_wndproc_ref = None


def current_usages() -> list[dict]:
    with _lock:
        merged: set[tuple[int, int]] = set()
        for group in _usages_by_device.values():
            merged |= group
        return [{"page": p, "usage": u} for p, u in sorted(merged)]


def current_devices() -> list[dict]:
    with _lock:
        out = []
        for handle, info in _devices.items():
            out.append({
                "handle": handle,
                "vid": info.get("vid", 0),
                "pid": info.get("pid", 0),
                "usagePage": info.get("usagePage", 0),
                "usage": info.get("usage", 0),
                "report": info.get("report", b""),
                "buttons": [{"page": p, "usage": u} for p, u in sorted(info.get("buttons") or [])],
                "values": dict(info.get("values") or {}),
            })
        return out


def _device_info(hdevice) -> tuple[int, int, int, int]:
    info = RID_DEVICE_INFO()
    info.cbSize = sizeof(RID_DEVICE_INFO)
    size = c_uint(sizeof(RID_DEVICE_INFO))
    if user32.GetRawInputDeviceInfoW(hdevice, RIDI_DEVICEINFO, byref(info), byref(size)) < 0:
        return (0, 0, 0, 0)
    if info.dwType != RIM_TYPEHID:
        return (0, 0, 0, 0)
    return (
        int(info.hid.dwVendorId),
        int(info.hid.dwProductId),
        int(info.hid.usUsagePage),
        int(info.hid.usUsage),
    )


def _get_preparsed(hdevice: int):
    cached = _preparsed.get(hdevice)
    if cached is not None:
        return cached
    size = c_uint(0)
    user32.GetRawInputDeviceInfoW(hdevice, RIDI_PREPARSEDDATA, None, byref(size))
    if size.value == 0:
        return None
    buf = (ctypes.c_ubyte * size.value)()
    if user32.GetRawInputDeviceInfoW(hdevice, RIDI_PREPARSEDDATA, buf, byref(size)) < 0:
        return None
    _preparsed[hdevice] = buf
    return buf


def _usages_from_report(preparsed, report_buf) -> set[tuple[int, int]]:
    found: set[tuple[int, int]] = set()
    usage_list = (c_ushort * 64)()
    count = c_uint(64)
    status = hid.HidP_GetUsages(
        HIDP_INPUT,
        HID_USAGE_PAGE_BUTTON,
        0,
        usage_list,
        byref(count),
        preparsed,
        report_buf,
        len(report_buf),
    )
    if status == HIDP_STATUS_SUCCESS:
        for i in range(count.value):
            found.add((HID_USAGE_PAGE_BUTTON, int(usage_list[i])))
    return found


def _values_from_report(preparsed, report_buf) -> dict[int, int]:
    values: dict[int, int] = {}
    for usage in AXIS_USAGES:
        value = c_ulong(0)
        status = hid.HidP_GetUsageValue(
            HIDP_INPUT,
            HID_USAGE_PAGE_GENERIC,
            0,
            usage,
            byref(value),
            preparsed,
            report_buf,
            len(report_buf),
        )
        if status == HIDP_STATUS_SUCCESS:
            values[usage] = int(value.value)
    return values


def _on_input(hraw) -> None:
    size = c_uint(0)
    user32.GetRawInputData(hraw, RID_INPUT, None, byref(size), sizeof(RAWINPUTHEADER))
    if size.value == 0:
        return
    buf = (ctypes.c_ubyte * size.value)()
    got = c_uint(size.value)
    if user32.GetRawInputData(hraw, RID_INPUT, buf, byref(got), sizeof(RAWINPUTHEADER)) != size.value:
        return
    header = RAWINPUTHEADER.from_buffer(buf)
    if header.dwType != RIM_TYPEHID:
        return
    hid_off = sizeof(RAWINPUTHEADER)
    dw_size_hid = c_uint.from_buffer(buf, hid_off).value
    dw_count = c_uint.from_buffer(buf, hid_off + 4).value
    if dw_size_hid == 0 or dw_count == 0:
        return
    start = hid_off + 8
    report = bytes(buf[start:start + dw_size_hid])
    device = int(header.hDevice) if header.hDevice else 0
    preparsed = _get_preparsed(header.hDevice)
    usages: set[tuple[int, int]] = set()
    values: dict[int, int] = {}
    if preparsed is not None:
        report_buf = ctypes.create_string_buffer(report, len(report))
        usages = _usages_from_report(preparsed, report_buf)
        values = _values_from_report(preparsed, report_buf)
    vid, pid, usage_page, usage = _device_info(header.hDevice)
    with _lock:
        _usages_by_device[device] = usages
        prev = _devices.get(device) or {}
        _devices[device] = {
            "vid": vid or prev.get("vid", 0),
            "pid": pid or prev.get("pid", 0),
            "usagePage": usage_page or prev.get("usagePage", 0),
            "usage": usage or prev.get("usage", 0),
            "report": report,
            "buttons": usages,
            "values": values,
        }


def _wndproc(hwnd, msg, wparam, lparam):
    if msg == WM_INPUT:
        _on_input(lparam)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def _thread_main() -> None:
    global _wndproc_ref
    _wndproc_ref = WNDPROC(_wndproc)
    class_name = "PadDeskRawInput"
    wc = WNDCLASSW()
    wc.lpfnWndProc = _wndproc_ref
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.lpszClassName = class_name
    if not user32.RegisterClassW(byref(wc)):
        pass
    hwnd = user32.CreateWindowExW(
        WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
        class_name,
        "PadDeskRaw",
        WS_POPUP,
        0, 0, 0, 0,
        None, None, wc.hInstance, None,
    )
    if not hwnd:
        return
    devices = (RAWINPUTDEVICE * 3)()
    for i, usage in enumerate((4, 5, 8)):  # joystick, gamepad, multi-axis
        devices[i].usUsagePage = 1
        devices[i].usUsage = usage
        devices[i].dwFlags = RIDEV_INPUTSINK
        devices[i].hwndTarget = hwnd
    user32.RegisterRawInputDevices(devices, 3, sizeof(RAWINPUTDEVICE))
    msg = MSG()
    while user32.GetMessageW(byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(byref(msg))
        user32.DispatchMessageW(byref(msg))


def start() -> None:
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_thread_main, daemon=True).start()
