"""PadDesk local server — UI + mapper + sequencer on 127.0.0.1 only.

Desenvolvido por Victor Emanuel Lobato.
"""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import gamepad
import injector
from mapper import Mapper
from sequencer import Sequencer

HOST = "127.0.0.1"
PORT = 8765
ROOT = Path(__file__).parent
WEB = ROOT / "web"
CONFIG_PATH = ROOT / "config.json"

DEFAULT_BINDS = {
    "A": {"kind": "mouse", "button": "left"},
    "B": {"kind": "mouse", "button": "right"},
    "X": {"kind": "key", "key": "SPACE"},
    "Y": {"kind": "key", "key": "F"},
    "LB": {"kind": "key", "key": "Q"},
    "RB": {"kind": "key", "key": "E"},
    "LT": {"kind": "mouse", "button": "right"},
    "RT": {"kind": "mouse", "button": "left"},
    "START": {"kind": "key", "key": "ESC"},
    "BACK": {"kind": "none"},
    "LS": {"kind": "none"},
    "RS": {"kind": "none"},
    "DUP": {"kind": "key", "key": "UP"},
    "DDOWN": {"kind": "key", "key": "DOWN"},
    "DLEFT": {"kind": "key", "key": "LEFT"},
    "DRIGHT": {"kind": "key", "key": "RIGHT"},
    "M1": {"kind": "none"},
    "M2": {"kind": "none"},
    "M3": {"kind": "none"},
    "M4": {"kind": "none"},
}

DEFAULT_CONFIG = {
    "mapper": {
        "enabled": False,
        "leftStick": "wasd",
        "rightStick": "mouse",
        "sensitivity": 14,
        "deadzone": 0.14,
        "invertY": False,
        "curve": "quadratic",
        "triggerThreshold": 0.35,
        "paddleMap": {},
        "binds": DEFAULT_BINDS,
    },
    "activeSequenceId": "tpl-mouse",
    "sequences": [
        {
            "id": "tpl-mouse",
            "name": "Exemplo — mover e clicar",
            "repeat": 1,
            "startDelayMs": 1500,
            "steps": [
                {"id": "a", "type": "mouse_move", "x": 400, "y": 300, "ms": 250},
                {"id": "b", "type": "mouse_click", "button": "left", "ms": 40},
                {"id": "c", "type": "wait", "ms": 200},
            ],
        },
        {
            "id": "tpl-keys",
            "name": "Exemplo — teclas em sequência",
            "repeat": 1,
            "startDelayMs": 1500,
            "steps": [
                {"id": "a", "type": "key_tap", "key": "F1", "ms": 80},
                {"id": "b", "type": "wait", "ms": 300},
                {"id": "c", "type": "key_tap", "key": "F2", "ms": 80},
                {"id": "d", "type": "wait", "ms": 300},
                {"id": "e", "type": "key_tap", "key": "F3", "ms": 80},
            ],
        },
        {
            "id": "tpl-mod",
            "name": "Exemplo — tecla com modificador",
            "repeat": 1,
            "startDelayMs": 1500,
            "steps": [
                {"id": "a", "type": "key_down", "key": "CTRL", "ms": 40},
                {"id": "b", "type": "key_tap", "key": "C", "ms": 50},
                {"id": "c", "type": "key_up", "key": "CTRL", "ms": 40},
            ],
        },
    ],
}

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}

lock = threading.Lock()
mapper = Mapper()
sequencer = Sequencer()


def default_config() -> dict:
    return json.loads(json.dumps(DEFAULT_CONFIG))


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            merged = default_config()
            merged.update(data)
            if "mapper" in data:
                merged["mapper"] = {**default_config()["mapper"], **data["mapper"]}
                binds = default_config()["mapper"]["binds"].copy()
                binds.update(data["mapper"].get("binds") or {})
                merged["mapper"]["binds"] = binds
            return merged
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    cfg = default_config()
    save_config(cfg)
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


config = load_config()
mapper.set_config(config["mapper"])
mapper.set_enabled(bool(config["mapper"].get("enabled")))


def persist_mapper_enabled(enabled: bool) -> None:
    with lock:
        config["mapper"]["enabled"] = bool(enabled)
        save_config(config)


mapper.set_on_enabled_change(persist_mapper_enabled)
mapper.start()


def play_from_pad(seq_id: str) -> None:
    with lock:
        if sequencer.status()["playing"]:
            return
        seq = find_sequence(seq_id)
        if not seq:
            return
        copy = json.loads(json.dumps(seq))
        copy["startDelayMs"] = 0
        mapper.set_enabled(False)

        def restore() -> None:
            if not sequencer.status()["playing"]:
                with lock:
                    apply_mapper_from_config()

        sequencer.play(copy, on_change=restore)


mapper.set_on_sequence(play_from_pad)


def apply_mapper_from_config() -> None:
    mapper.set_config(config["mapper"])
    mapper.set_enabled(bool(config["mapper"].get("enabled")))


def find_sequence(seq_id: str) -> dict | None:
    for seq in config.get("sequences") or []:
        if seq.get("id") == seq_id:
            return seq
    return None


def snapshot() -> dict:
    pad = gamepad.poll(paddle_map=config["mapper"].get("paddleMap")) or {
        "connected": False, "buttons": {}, "axes": {}, "debug": {},
    }
    mx, my = injector.cursor_pos()
    return {
        "connected": bool(pad.get("connected")),
        "buttons": pad.get("buttons") or {},
        "axes": pad.get("axes") or {},
        "padName": pad.get("name") or "",
        "padSource": pad.get("source") or "",
        "mouse": {"x": mx, "y": my},
        "screen": injector.screen_info(),
        "mapperEnabled": mapper.enabled(),
        "sequence": sequencer.status(),
        "keys": injector.key_names(),
        "panic": injector.panic_pressed(),
        "debug": pad.get("debug") or {},
        "paddleMap": config["mapper"].get("paddleMap") or {},
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def _json(self, payload, status: int = 200) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/state":
            with lock:
                self._json(snapshot())
            return
        if path == "/api/config":
            with lock:
                self._json(config)
            return
        if path in ("/", "/index.html"):
            self._file(WEB / "index.html")
            return
        rel = path.lstrip("/")
        target = (WEB / rel).resolve()
        if WEB.resolve() not in target.parents and target != WEB.resolve():
            self.send_error(403)
            return
        if target.is_file():
            self._file(target)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._read_json()
        except json.JSONDecodeError:
            self._json({"ok": False, "error": "json invalido"}, 400)
            return

        if path == "/api/learn-paddle":
            name = str(body.get("name") or "M1").upper()
            if name not in ("M1", "M2", "M3", "M4"):
                self._json({"ok": False, "error": "nome invalido"}, 400)
                return
            binding = gamepad.learn_paddle(name)
            if not binding:
                self._json({"ok": False, "error": "nao detectou sinal extra"}, 408)
                return
            with lock:
                config["mapper"].setdefault("paddleMap", {})[name] = binding
                save_config(config)
                apply_mapper_from_config()
            self._json({"ok": True, "binding": binding})
            return
        if path == "/api/capture-mouse":
            delay = int(body.get("delayMs") or 0)
            injector.interruptible_sleep(delay)
            x, y = injector.cursor_pos()
            self._json({"ok": True, "x": x, "y": y})
            return
        if path == "/api/sequence/test-step":
            sequencer.run_one(body.get("step") or {})
            self._json({"ok": True})
            return

        with lock:
            if path == "/api/config":
                incoming = body or {}
                old_paddles = dict((config.get("mapper") or {}).get("paddleMap") or {})
                config.clear()
                config.update(default_config())
                config.update(incoming)
                if "mapper" in incoming:
                    config["mapper"] = {**default_config()["mapper"], **incoming["mapper"]}
                    binds = default_config()["mapper"]["binds"].copy()
                    binds.update(incoming["mapper"].get("binds") or {})
                    config["mapper"]["binds"] = binds
                    paddles = dict(old_paddles)
                    paddles.update(incoming["mapper"].get("paddleMap") or {})
                    config["mapper"]["paddleMap"] = paddles
                save_config(config)
                apply_mapper_from_config()
                self._json({"ok": True, "config": config})
                return
            if path == "/api/mapper":
                config["mapper"]["enabled"] = bool(body.get("enabled"))
                save_config(config)
                apply_mapper_from_config()
                self._json({"ok": True, "enabled": mapper.enabled()})
                return
            if path == "/api/sequence/play":
                if sequencer.status()["playing"]:
                    self._json({"ok": False, "error": "ja esta tocando"}, 409)
                    return
                seq_id = body.get("id") or config.get("activeSequenceId")
                seq = find_sequence(seq_id)
                if not seq:
                    self._json({"ok": False, "error": "sequencia nao encontrada"}, 404)
                    return
                mapper.set_enabled(False)
                copy = json.loads(json.dumps(seq))

                def restore() -> None:
                    if not sequencer.status()["playing"]:
                        with lock:
                            apply_mapper_from_config()

                sequencer.play(copy, on_change=restore)
                self._json({"ok": True})
                return
            if path == "/api/sequence/stop":
                sequencer.stop()
                apply_mapper_from_config()
                self._json({"ok": True})
                return
        self.send_error(404)

    def _file(self, path: Path) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    gamepad.start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"PadDesk em {url}")
    print("F12 = liga/desliga mapeamento  |  F8 = para sequencia")
    threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        mapper.stop()
        sequencer.stop()
        server.server_close()


if __name__ == "__main__":
    main()
