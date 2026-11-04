"""A small public HTTP API for lake requests: check, store, and search for NISAR coverage."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sartale.lake_requests import MAX_OPEN, RATE_PER_HOUR, RequestError, RequestStore, coverage, validate
from sartale.lakes import Lake

MAX_BODY = 4096
HOUR = 3600
LIST_PATH = "/api/lake-requests"
HEALTH_PATH = "/api/health"


def _public(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "source"}


def _search_in_background(server, rid: int, lat: float, lon: float) -> None:
    try:
        found = server.search(lat, lon)
        server.store.set_searched(rid, found["passes"], found["tracks"], found["first"], found["last"])
    except Exception as exc:  # the worker must never take the server down
        try:
            server.store.set_failed(rid, str(exc) or type(exc).__name__)
        except Exception:
            pass


class Handler(BaseHTTPRequestHandler):
    server_version = "SARtaleRequests"

    def log_message(self, format, *args):  # keep stderr quiet
        pass

    # -- helpers
    def _send(self, status: int, payload=None) -> None:
        data = b"" if payload is None else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        if payload is not None:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        origin = self.headers.get("Origin")
        if origin and origin == self.server.allowed_origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            if self.command == "OPTIONS":
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        if data and self.command != "HEAD":
            self.wfile.write(data)

    def _error(self, status: int, message: str) -> None:
        self._send(status, {"error": message})

    def _path(self) -> str:
        return self.path.split("?", 1)[0]

    def _read_object(self):
        """Return the JSON object in the body, or None after sending an error."""
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            self.close_connection = True
            self._error(411, "Content-Length is required.")
            return None
        try:
            length = int(raw_length.strip())
            if length < 0:
                raise ValueError
        except ValueError:
            self.close_connection = True
            self._error(400, "Content-Length is invalid.")
            return None
        if length > MAX_BODY:
            self.close_connection = True
            self._error(413, f"The request body must be at most {MAX_BODY} bytes.")
            return None
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, RecursionError):
            self._error(400, "The body must be valid JSON.")
            return None
        if not isinstance(payload, dict):
            self._error(400, "The body must be a JSON object.")
            return None
        return payload

    # -- routes
    def do_GET(self):
        path = self._path()
        if path == HEALTH_PATH:
            self._send(200, {"ok": True, "open": self.server.store.open_count()})
        elif path == LIST_PATH:
            self._send(200, {"requests": [_public(r) for r in self.server.store.list_open()]})
        else:
            self._error(404, "Not found.")

    def do_POST(self):
        path = self._path()
        if path == HEALTH_PATH:
            return self._error(405, "Method not allowed.")
        if path != LIST_PATH:
            return self._error(404, "Not found.")
        payload = self._read_object()
        if payload is None:
            return
        srv = self.server
        addr = self.client_address[0]
        try:
            with srv.write_lock:  # check-then-add must be atomic across requests
                now = srv.clock()
                if srv.store.recent_count(addr, now - HOUR) >= RATE_PER_HOUR:
                    raise RequestError("Too many requests from this address; try again in an hour.", 429)
                clean = validate(payload, srv.watched, srv.store.list_open())
                if srv.store.open_count() >= MAX_OPEN:
                    raise RequestError("The request list is full; try again later.", 503)
                row = srv.store.add(clean, addr, now)
        except RequestError as e:
            return self._error(e.status, str(e))
        threading.Thread(target=_search_in_background, args=(srv, row["id"], row["lat"], row["lon"]),
                         daemon=True).start()
        self._send(201, _public(row))

    def do_OPTIONS(self):
        self._send(204)

    def _not_allowed(self):
        path = self._path()
        if path in (LIST_PATH, HEALTH_PATH):
            self._error(405, "Method not allowed.")
        else:
            self._error(404, "Not found.")

    do_PUT = do_DELETE = do_PATCH = _not_allowed


def make_server(store: RequestStore, watched: list[Lake], host: str = "127.0.0.1", port: int = 8787,
                allowed_origin: str = "http://localhost:5173", search=coverage,
                clock=time.time) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.store = store
    server.watched = watched
    server.allowed_origin = allowed_origin
    server.search = search
    server.clock = clock
    server.write_lock = threading.Lock()
    return server
