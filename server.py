#!/usr/bin/env python3
"""Local demo server for La Campana. NOT for production deployment."""
from __future__ import annotations
import http.cookies
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("PARROCCHIA_DB_PATH", str(ROOT / "content.sqlite3")))
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "4173"))
# DEMO ONLY: replace with an identity provider/Cloudflare Access before deployment.
DEMO_PIN = os.environ.get("PARROCCHIA_DEMO_PIN", "2468")
SESSIONS: dict[str, float] = {}
MAX_BODY = 1_000_000

SEED = {
    "demoMode": True,
    "parishDemo": True,
    "parish": {
        "name": "Parrocchia Santa Maria della Speranza (demo)",
        "tagline": "La comunità si incontra",
        "welcome": "Il bene di trovarsi insieme.",
        "address": "Via della Comunità 12, Roma (indirizzo dimostrativo)",
        "phone": "+39 06 0000 0000 (numero fittizio)",
        "email": "segreteria@example.invalid",
        "mapUrl": "",
        "description": "Una casa aperta nel cuore del quartiere. Testo dimostrativo da sostituire.",
        "privacyText": "Informativa dimostrativa: sostituire prima della pubblicazione.",
        "privacyContact": ""
    },
    "schedules": [
        {"id":"sch-demo-1","activity":"Santa Messa","days":"Domenica","time":"10:30","place":"Chiesa parrocchiale","active":True,"demo":True},
        {"id":"sch-demo-2","activity":"Santa Messa","days":"Giovedì","time":"18:30","place":"Chiesa parrocchiale","active":True,"demo":True},
        {"id":"sch-demo-3","activity":"Adorazione","days":"Primo venerdì","time":"17:30","place":"Cappella","active":True,"demo":True}
    ],
    "events": [
        {"id":"evt-demo-1","day":"DOM","date":"25 ottobre","dateISO":"2026-10-25","title":"Santa Messa","place":"Chiesa parrocchiale","time":"10:30","demo":True,"published":True},
        {"id":"evt-demo-2","day":"MAR","date":"27 ottobre","dateISO":"2026-10-27","title":"Apertura centro di ascolto","place":"Salone parrocchiale","time":"16:00","demo":True,"published":True},
        {"id":"evt-demo-3","day":"GIO","date":"29 ottobre","dateISO":"2026-10-29","title":"Santa Messa","place":"Chiesa parrocchiale","time":"18:00","demo":True,"published":True},
        {"id":"evt-demo-4","day":"SAB","date":"31 ottobre","dateISO":"2026-10-31","title":"Rosario comunitario","place":"Chiesa parrocchiale","time":"17:30","demo":True,"published":True}
    ],
    "notices": [
        {"id":"notice-demo-1","day":"25","month":"OTT","dateISO":"2026-10-25","category":"Comunità","title":"Un caffè dopo la Messa","summary":"Domenica ci fermiamo insieme nel salone parrocchiale.","body":"Dopo la celebrazione delle 10:30, il salone sarà aperto per un caffè e due chiacchiere. Un momento semplice per incontrarsi, dare il benvenuto a chi è nuovo e condividere la vita della comunità. Vi aspettiamo con gioia.","important":False,"published":True,"demo":True},
        {"id":"notice-demo-2","day":"27","month":"OTT","dateISO":"2026-10-27","category":"Carità","title":"Raccolta alimentare","summary":"Un piccolo gesto, una tavola più ricca per tutti.","body":"Per sostenere le famiglie del quartiere raccogliamo pasta, riso, olio, legumi e prodotti a lunga conservazione. È possibile consegnare le donazioni in sacrestia negli orari di apertura. Grazie di cuore per la vostra generosità.","important":True,"published":True,"demo":True},
        {"id":"notice-demo-3","day":"29","month":"OTT","dateISO":"2026-10-29","category":"Orari","title":"Variazione orario della Messa","summary":"Giovedì la celebrazione sarà anticipata alle 18:00.","body":"Per una necessità organizzativa, giovedì la celebrazione feriale sarà anticipata alle ore 18:00. Gli altri orari restano invariati. Ci scusiamo per il cambiamento e vi ringraziamo per la comprensione.","important":True,"published":True,"demo":True}
    ],
    "liturgy": {
        "date":"2026-10-25","season":"Tempo liturgico da verificare","firstReading":"Riferimento da inserire","psalm":"Riferimento da inserire","gospel":"Riferimento da inserire","sourceUrl":"","sourceNote":"Testi non forniti: inserire solo contenuti autorizzati o link a una fonte ufficiale.","demo":True
    },
    "appearance": {"theme":"salvia","heroTitle":"Il bene di trovarsi insieme.","demo":True}
}


def db_connect():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db_connect() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE IF NOT EXISTS app_state (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        row = con.execute("SELECT body FROM app_state WHERE id=1").fetchone()
        if row is None:
            con.execute("INSERT INTO app_state(id, body) VALUES(1, ?)", (json.dumps(SEED, ensure_ascii=False),))


def read_state():
    with db_connect() as con:
        row = con.execute("SELECT body FROM app_state WHERE id=1").fetchone()
    return json.loads(row["body"])


def write_state(state):
    encoded = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_BODY:
        raise ValueError("Contenuto troppo grande")
    with db_connect() as con:
        con.execute("UPDATE app_state SET body=?, updated_at=CURRENT_TIMESTAMP WHERE id=1", (encoded,))


def public_state(state):
    out = dict(state)
    out["notices"] = [x for x in state.get("notices", []) if x.get("published", True)]
    out["events"] = [x for x in state.get("events", []) if x.get("published", True)]
    return out


def valid_state(obj):
    if not isinstance(obj, dict):
        return False
    for key in ("parish", "schedules", "events", "notices", "liturgy", "appearance"):
        if key not in obj:
            return False
    if not isinstance(obj["parish"], dict):
        return False
    for key in ("schedules", "events", "notices"):
        if not isinstance(obj[key], list) or len(obj[key]) > 1000:
            return False
    return True


class Handler(BaseHTTPRequestHandler):
    server_version = "LaCampanaDemo/0.2"

    def log_message(self, fmt, *args):
        # Avoid logging request bodies or query strings in this demo.
        super().log_message(fmt, *args)

    def _headers(self, status=200, content_type="application/json; charset=utf-8", extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        if extra:
            for key, value in extra.items():
                self.send_header(key, value)
        self.end_headers()

    def _json(self, data, status=200, extra=None):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._headers(status, extra=extra)
        self.wfile.write(raw)

    def _body(self):
        size = int(self.headers.get("Content-Length", "0"))
        if size < 0 or size > MAX_BODY:
            raise ValueError("Richiesta troppo grande")
        return json.loads(self.rfile.read(size).decode("utf-8"))

    def _session_ok(self):
        cookie = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie.get("lc_session")
        if not token:
            return False
        expires = SESSIONS.get(token.value, 0)
        if expires < time.time():
            SESSIONS.pop(token.value, None)
            return False
        return True

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            return self._json({"ok": True, "mode": "demo"})
        if path == "/api/public":
            return self._json(public_state(read_state()))
        if path == "/api/admin/data":
            if not self._session_ok():
                return self._json({"error": "Accesso richiesto"}, 401)
            return self._json(read_state())
        if path.startswith("/api/"):
            return self._json({"error": "Endpoint non trovato"}, 404)
        relative = unquote(path).lstrip("/") or "index.html"
        file_path = (ROOT / relative).resolve()
        if ROOT not in file_path.parents and file_path != ROOT:
            return self._json({"error": "Percorso non consentito"}, 403)
        if not file_path.is_file():
            file_path = ROOT / "index.html"
        try:
            data = file_path.read_bytes()
        except OSError:
            return self._json({"error": "File non trovato"}, 404)
        ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._headers(200, ctype)
        self.wfile.write(data)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self._body()
        except Exception:
            return self._json({"error": "Richiesta non valida"}, 400)
        if path == "/api/admin/login":
            pin = str(payload.get("pin", ""))
            if not hmac.compare_digest(pin, DEMO_PIN):
                return self._json({"error": "Codice non corretto"}, 401)
            token = secrets.token_urlsafe(32)
            SESSIONS[token] = time.time() + 8 * 60 * 60
            secure = "; Secure" if self.headers.get("X-Forwarded-Proto", "").lower() == "https" else ""
            cookie = f"lc_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800{secure}"
            return self._json({"ok": True}, extra={"Set-Cookie": cookie})
        if path.startswith("/api/admin/") and not self._session_ok():
            return self._json({"error": "Accesso richiesto"}, 401)
        if path == "/api/admin/save":
            state = payload.get("state")
            if not valid_state(state):
                return self._json({"error": "Struttura dei contenuti non valida"}, 400)
            write_state(state)
            return self._json({"ok": True, "state": read_state()})
        if path == "/api/admin/purge-demo":
            state = read_state()
            for key in ("notices", "events", "schedules"):
                state[key] = [item for item in state.get(key, []) if not item.get("demo")]
            if state.get("parishDemo", False):
                state["parish"] = {key: "" for key in state.get("parish", {})}
                state["parishDemo"] = False
            if state.get("liturgy", {}).get("demo", False):
                state["liturgy"] = {key: "" for key in state.get("liturgy", {})}
            if state.get("appearance", {}).get("demo", False):
                state["appearance"] = {"theme": "salvia", "heroTitle": ""}
            state["demoMode"] = False
            write_state(state)
            return self._json({"ok": True, "state": state})
        if path == "/api/admin/logout":
            cookie = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
            if cookie.get("lc_session"):
                SESSIONS.pop(cookie["lc_session"].value, None)
            return self._json({"ok": True}, extra={"Set-Cookie": "lc_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})
        return self._json({"error": "Endpoint non trovato"}, 404)

    def do_OPTIONS(self):
        return self._json({"error": "Metodo non supportato"}, 405)


def main():
    init_db()
    print(f"La Campana demo server on http://{HOST}:{PORT}")
    print("DEMO ONLY — PIN predefinito 2468; non usare per dati reali o deploy pubblico.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
