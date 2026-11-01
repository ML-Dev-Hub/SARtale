"""Download tests use a fake session. Nothing here touches the network or ~/.netrc."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import pytest
import requests

from sartale.download import BASE_URL, download, download_file, granule_url
from sartale.run_pipeline import main

NAME = "NISAR_L2_PR_GCOV_026_084_A_019_4005_DHDH_A_20260726T002237_20260726T002312_P05023_N_F_J_001"
BODY = bytes(range(256)) * 40  # 10240 bytes
MD5 = hashlib.md5(BODY).hexdigest()


class FakeResponse:
    def __init__(self, status, body=b"", fail_after=None):
        self.status_code, self.body, self.fail_after = status, body, fail_after

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_content(self, size):
        for i in range(0, len(self.body), 1000):
            if self.fail_after is not None and i >= self.fail_after:
                raise requests.ConnectionError("dropped")
            yield self.body[i:i + 1000]


class FakeSession:
    """Serves BODY. Records every request. `script` lets a test override the next responses."""

    def __init__(self, body=BODY, script=None, honour_range=True):
        self.body, self.script, self.honour_range = body, list(script or []), honour_range
        self.requests = []

    def get(self, url, headers=None, stream=False, timeout=None):
        self.requests.append((url, dict(headers or {})))
        if self.script:
            nxt = self.script.pop(0)
            if nxt is not None:
                return nxt
        rng = (headers or {}).get("Range")
        if rng and self.honour_range:
            start = int(rng.split("=")[1].rstrip("-"))
            return FakeResponse(206, self.body[start:])
        return FakeResponse(200, self.body)


def run(session, tmp_path, **kw):
    return download_file(session, NAME, len(BODY), MD5, tmp_path, sleep=lambda s: None, log=lambda m: None, **kw)


def test_url_pattern():
    assert granule_url(NAME) == f"{BASE_URL}/{NAME}/{NAME}.h5"
    assert granule_url(NAME) == (
        f"https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/{NAME}/{NAME}.h5")


def test_downloads_verifies_and_renames(tmp_path):
    session = FakeSession()
    path = run(session, tmp_path)
    assert path == tmp_path / f"{NAME}.h5" and path.read_bytes() == BODY
    assert not (tmp_path / f"{NAME}.h5.part").exists()
    assert session.requests[0][0] == granule_url(NAME)


def test_resumes_a_part_file_with_a_range_request(tmp_path):
    (tmp_path / f"{NAME}.h5.part").write_bytes(BODY[:4000])
    session = FakeSession()
    path = run(session, tmp_path)
    assert session.requests[0][1] == {"Range": "bytes=4000-"}
    assert path.read_bytes() == BODY


def test_resumes_after_a_dropped_connection(tmp_path):
    session = FakeSession(script=[FakeResponse(200, BODY, fail_after=3000)])
    path = run(session, tmp_path)
    assert path.read_bytes() == BODY
    assert session.requests[1][1] == {"Range": "bytes=3000-"}


def test_restarts_when_the_server_ignores_range(tmp_path):
    (tmp_path / f"{NAME}.h5.part").write_bytes(BODY[:4000])
    session = FakeSession(honour_range=False)
    assert run(session, tmp_path).read_bytes() == BODY


def test_md5_mismatch_deletes_the_part_and_never_renames(tmp_path):
    session = FakeSession(body=b"\x00" * len(BODY))
    with pytest.raises(ValueError, match="MD5"):
        run(session, tmp_path)
    assert not (tmp_path / f"{NAME}.h5").exists()
    assert not (tmp_path / f"{NAME}.h5.part").exists()


def test_a_short_file_is_not_renamed(tmp_path):
    session = FakeSession(body=BODY[:5000])
    with pytest.raises(ValueError, match="5000 of 10240"):
        run(session, tmp_path, retries=2)
    assert not (tmp_path / f"{NAME}.h5").exists()
    assert (tmp_path / f"{NAME}.h5.part").stat().st_size == 5000  # kept so the next run can resume


def test_a_verified_file_is_not_downloaded_again(tmp_path):
    (tmp_path / f"{NAME}.h5").write_bytes(BODY)
    session = FakeSession()
    run(session, tmp_path)
    assert session.requests == []


def test_an_existing_file_that_does_not_match_is_never_overwritten(tmp_path):
    (tmp_path / f"{NAME}.h5").write_bytes(b"other")
    with pytest.raises(ValueError, match="does not match"):
        run(FakeSession(), tmp_path)
    assert (tmp_path / f"{NAME}.h5").read_bytes() == b"other"


def test_a_refused_login_stops_at_once_and_names_no_credentials(tmp_path):
    session = FakeSession(script=[FakeResponse(401)])
    with pytest.raises(ValueError, match="401") as err:
        run(session, tmp_path)
    assert len(session.requests) == 1
    assert "Authorization" not in str(err.value) and "password" not in str(err.value).lower()


def test_a_server_error_is_retried(tmp_path):
    session = FakeSession(script=[FakeResponse(503), FakeResponse(503)])
    assert run(session, tmp_path).read_bytes() == BODY
    assert len(session.requests) == 3


def _manifest(tmp_path, **extra):
    entry = {"name": NAME, "start": "2026-07-26T00:22:37+00:00", "crid": "P05023", "accuracy": "N",
             "coverage": "F", "cycle": 26, **extra}
    path = tmp_path / "search.json"
    path.write_text(json.dumps({"searched": "x", "granules": [entry]}), encoding="utf-8")
    return path


def test_download_reads_size_and_md5_from_the_manifest(tmp_path):
    out = tmp_path / "gcov"
    paths = download(_manifest(tmp_path, size=len(BODY), md5=MD5), ["2026-07-26"], out,
                     session=FakeSession(), sleep=lambda s: None, log=lambda m: None)
    assert paths == [out / f"{NAME}.h5"] and paths[0].read_bytes() == BODY


def test_download_needs_size_and_md5_in_the_manifest(tmp_path):
    with pytest.raises(ValueError, match="search"):
        download(_manifest(tmp_path), ["2026-07-26"], tmp_path / "gcov", session=FakeSession())


def test_download_rejects_a_date_not_in_the_manifest(tmp_path):
    with pytest.raises(ValueError, match="2026-08-19"):
        download(_manifest(tmp_path, size=1, md5="x"), ["2026-08-19"], tmp_path / "gcov", session=FakeSession())


def test_cli_download_command(tmp_path, monkeypatch, capsys):
    import sartale.download as dl

    monkeypatch.setattr(dl.requests, "Session", lambda: FakeSession())
    out = tmp_path / "gcov"
    main(["download", "--manifest", str(_manifest(tmp_path, size=len(BODY), md5=MD5)),
          "--dates", "2026-07-26", "--out", str(out)])
    assert (out / f"{NAME}.h5").read_bytes() == BODY
    assert "1 files" in capsys.readouterr().out
