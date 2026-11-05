import http.client
import json
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest

from sartale.lake_requests import RequestStore
from sartale.lakes import Lake
from sartale.requests_server import make_server

ATTABAD = Lake(id="attabad", name="Attabad Lake", lon=74.8, lat=36.3, coord_source="s", outline=None,
               role="watch", downstream=None, downstream_source=None)
ORIGIN = "http://localhost:5173"


def body(i=0, **extra):
    data = {"name": f"Lake {i}", "lat": 35.0 + i * 0.1, "lon": 75.0, "source": "https://example.org/x"}
    data.update(extra)
    return data


def fake_search(lat, lon):
    return {"passes": 3, "tracks": ["a"], "first": "2026-01-01", "last": "2026-02-01"}


class Harness:
    def __init__(self, tmp_path, search, clock, **kw):
        self.store = RequestStore(tmp_path / "r.sqlite")
        self.server = make_server(self.store, [ATTABAD], port=0, search=search, clock=clock, **kw)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def call(self, method, path, data=None, headers=None, raw=None):
        payload = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
        hdrs = {"Content-Type": "application/json"}
        hdrs.update(headers or {})
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=payload, method=method,
                                     headers=hdrs)
        try:
            with urllib.request.urlopen(req) as r:
                text = r.read()
                return r.status, (json.loads(text) if text else None), r.headers
        except urllib.error.HTTPError as e:
            text = e.read()
            return e.code, (json.loads(text) if text else None), e.headers


@pytest.fixture
def make(tmp_path):
    made = []

    def build(search=fake_search, clock=time.time, **kw):
        h = Harness(tmp_path, search, clock, **kw)
        made.append(h)
        return h
    yield build
    for h in made:
        h.server.shutdown()
        h.server.server_close()


def wait_state(h, rid, state):
    row = None
    for _ in range(100):
        rows = h.call("GET", "/api/lake-requests")[1]["requests"]
        row = next(r for r in rows if r["id"] == rid)
        if row["state"] == state:
            return row
        time.sleep(0.05)
    raise AssertionError(f"never reached {state}: {row}")


def test_health(make):
    status, data, headers = make().call("GET", "/api/health")
    assert (status, data) == (200, {"ok": True, "open": 0})
    assert headers["Content-Type"] == "application/json; charset=utf-8"


def test_post_then_list_hides_source(make):
    h = make()
    status, row, _ = h.call("POST", "/api/lake-requests", body())
    assert status == 201 and "source" not in row and row["name"] == "Lake 0"
    listed = h.call("GET", "/api/lake-requests")[1]["requests"]
    assert [r["id"] for r in listed] == [row["id"]] and "source" not in listed[0]


def test_post_returns_400_with_the_message_for_bad_bounds(make):
    status, data, _ = make().call("POST", "/api/lake-requests", body(lat=10))
    assert status == 400 and "34.4–37.6" in data["error"]


def test_huge_integer_is_400_not_500(make):
    raw = ('{"name":"Big","lat":1' + "0" * 400 + ',"lon":75,"source":"abc"}').encode()
    assert make().call("POST", "/api/lake-requests", raw=raw)[0] == 400


def test_nearby_requests_conflict(make):
    h = make()
    h.call("POST", "/api/lake-requests", body())
    status, data, _ = h.call("POST", "/api/lake-requests", body())
    assert status == 409 and data["error"] == "Already requested: Lake 0."
    status, data, _ = h.call("POST", "/api/lake-requests", body(lat=36.3, lon=74.8))
    assert status == 409 and data["error"] == "Already watched: Attabad Lake."


def test_sixth_request_in_an_hour_is_429(make):
    now = [1000.0]
    h = make(clock=lambda: now[0])
    for i in range(5):
        assert h.call("POST", "/api/lake-requests", body(i))[0] == 201
    status, data, _ = h.call("POST", "/api/lake-requests", body(5))
    assert status == 429 and data["error"] == "Too many requests from this address; try again in an hour."
    now[0] += 3601
    assert h.call("POST", "/api/lake-requests", body(5))[0] == 201


def test_open_cap_is_503(make, monkeypatch):
    import sartale.requests_server as rs
    monkeypatch.setattr(rs, "MAX_OPEN", 2)
    h = make()
    for i in range(2):
        assert h.call("POST", "/api/lake-requests", body(i))[0] == 201
    status, data, _ = h.call("POST", "/api/lake-requests", body(2))
    assert status == 503 and data["error"] == "The request list is full; try again later."


def test_search_runs_in_the_background_and_marks_searched(make):
    h = make()
    rid = h.call("POST", "/api/lake-requests", body())[1]["id"]
    row = wait_state(h, rid, "searched")
    assert row["passes"] == 3


def test_a_failing_search_marks_search_failed_and_the_server_still_answers(make):
    def boom(lat, lon):
        raise ConnectionError("CMR down")
    h = make(search=boom)
    rid = h.call("POST", "/api/lake-requests", body())[1]["id"]
    row = wait_state(h, rid, "search_failed")
    assert row["reason"] == "NASA's catalogue did not answer; the team will retry."
    assert "detail" not in row and "CMR down" not in json.dumps(row)
    assert "detail" not in json.dumps(h.call("GET", "/api/lake-requests")[1])
    assert h.store.get(rid)["detail"] == "ConnectionError: CMR down"
    assert h.call("GET", "/api/health")[0] == 200


def test_an_unexpected_search_error_gets_the_generic_public_reason(make):
    def odd(lat, lon):
        raise KeyError("secret internals " + "x" * 500)
    h = make(search=odd)
    rid = h.call("POST", "/api/lake-requests", body())[1]["id"]
    row = wait_state(h, rid, "search_failed")
    assert row["reason"] == "NASA's catalogue gave an unexpected reply."
    assert "secret" in h.store.get(rid)["detail"]


def test_a_failing_search_prints_one_stderr_line(make, capsys):
    def boom(lat, lon):
        raise ConnectionError("CMR down")
    h = make(search=boom)
    rid = h.call("POST", "/api/lake-requests", body())[1]["id"]
    wait_state(h, rid, "search_failed")
    err = capsys.readouterr().err.strip().splitlines()
    assert len(err) == 1 and "CMR down" in err[0]


def test_an_accepted_request_still_blocks_a_nearby_duplicate(make):
    h = make()
    rid = h.call("POST", "/api/lake-requests", body())[1]["id"]
    h.store.set_state(rid, "accepted")
    status, data, _ = h.call("POST", "/api/lake-requests", body(0, lat=35.0005))
    assert status == 409 and "Already requested" in data["error"]


def test_body_over_4kb_is_413(make):
    status, data, _ = make().call("POST", "/api/lake-requests", body(source="x" * 5000))
    assert status == 413 and "error" in data


def test_bad_json_and_non_object_are_400(make):
    h = make()
    assert h.call("POST", "/api/lake-requests", raw=b"{nope")[0] == 400
    assert h.call("POST", "/api/lake-requests", raw=b"[1,2]")[0] == 400
    assert h.call("POST", "/api/lake-requests", raw=b"\xff\xfe")[0] == 400


def test_unknown_path_and_wrong_method(make):
    h = make()
    assert h.call("GET", "/nope")[0] == 404
    assert h.call("DELETE", "/api/lake-requests")[0] == 405
    assert h.call("POST", "/api/health", {})[0] == 405


def test_missing_or_invalid_content_length(make):
    h = make()
    for header, want in ((None, 411), ("abc", 400), ("-5", 400)):
        c = http.client.HTTPConnection("127.0.0.1", h.port)
        c.putrequest("POST", "/api/lake-requests")
        if header is not None:
            c.putheader("Content-Length", header)
        c.endheaders()
        r = c.getresponse()
        assert r.status == want
        assert "error" in json.loads(r.read())
        c.close()


def test_cors_header_only_for_the_allowed_origin(make):
    h = make()
    _, _, ok = h.call("GET", "/api/health", headers={"Origin": ORIGIN})
    _, _, other = h.call("GET", "/api/health", headers={"Origin": "http://evil.example"})
    assert ok["Access-Control-Allow-Origin"] == ORIGIN
    assert other["Access-Control-Allow-Origin"] is None
    status, _, headers = h.call("OPTIONS", "/api/lake-requests", headers={"Origin": ORIGIN})
    assert status == 204 and headers["Access-Control-Allow-Origin"] == ORIGIN


def test_concurrent_posts_cannot_exceed_the_rate_limit(make):
    h = make()
    results = []

    def go(i):
        results.append(h.call("POST", "/api/lake-requests", body(i))[0])
    threads = [threading.Thread(target=go, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(201) == 5 and results.count(429) == 7


def closed_within(sock, seconds):
    sock.settimeout(seconds)
    try:
        return sock.recv(1) == b""
    except socket.timeout:
        return False
    except ConnectionError:
        return True


def test_a_silent_connection_is_closed_after_the_timeout(make):
    h = make(timeout=0.5)
    s = socket.create_connection(("127.0.0.1", h.port))
    try:
        assert closed_within(s, 3)
    finally:
        s.close()
    assert h.call("GET", "/api/health")[0] == 200


def test_a_stalled_body_is_closed_after_the_timeout(make):
    h = make(timeout=0.5)
    s = socket.create_connection(("127.0.0.1", h.port))
    try:
        s.sendall(b"POST /api/lake-requests HTTP/1.1\r\nContent-Length: 4000\r\n\r\n{")
        s.settimeout(3)
        data = b""
        try:
            while chunk := s.recv(4096):
                data += chunk
        except ConnectionError:
            pass
        assert b"200" not in data[:20]
    finally:
        s.close()
    assert h.call("GET", "/api/health")[0] == 200


def test_connections_beyond_the_cap_are_closed(make):
    h = make(timeout=5, max_connections=2)
    held = [socket.create_connection(("127.0.0.1", h.port)) for _ in range(2)]
    time.sleep(0.3)
    extra = socket.create_connection(("127.0.0.1", h.port))
    try:
        assert closed_within(extra, 2)
    finally:
        extra.close()
        for s in held:
            s.close()


def test_post_from_another_site_is_refused(make):
    h = make()
    status, resp, _ = h.call("POST", "/api/lake-requests", body(), headers={"Origin": "http://evil.example"})
    assert status == 403 and "error" in resp
    assert h.store.open_count() == 0
    status, _, _ = h.call("POST", "/api/lake-requests", body(), headers={"Origin": ORIGIN})
    assert status == 201


def test_post_must_be_json(make):
    h = make()
    status, resp, _ = h.call("POST", "/api/lake-requests", body(), headers={"Content-Type": "text/plain"})
    assert status == 415 and "error" in resp
    assert h.store.open_count() == 0


def test_configured_origin_with_a_trailing_slash_still_matches(make):
    h = make(allowed_origin=ORIGIN + "/")
    status, _, headers = h.call("POST", "/api/lake-requests", body(), headers={"Origin": ORIGIN})
    assert status == 201 and headers["Access-Control-Allow-Origin"] == ORIGIN
