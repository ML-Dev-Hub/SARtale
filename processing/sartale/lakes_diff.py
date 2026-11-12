"""Compare two lakes.json builds pass by pass, so a rebuild cannot lose published passes without saying so."""
from __future__ import annotations

MAX_DROPPED_SHARE = 0.25  # more than this share of the previously published passes dropped fails the rebuild


def _passes(doc: dict | None) -> dict[str, dict[str, str]]:
    """lake id -> {"<date> <track>": crid or ""} for every pass in each lake's series."""
    out: dict[str, dict[str, str]] = {}
    for lk in (doc or {}).get("lakes", []):
        out[lk["id"]] = {f"{p['date']} {p['track']}": p.get("crid") or "" for p in lk.get("series", [])}
    return out


def _latest(doc: dict | None) -> dict[str, str | None]:
    return {lk["id"]: (lk.get("status") or {}).get("latest_date") for lk in (doc or {}).get("lakes", [])}


def _freeze(doc: dict | None) -> dict[str, str | None]:
    """lake id -> freeze state (None without one). A pass that turns frozen, or back, is the same pass: the comparison
    keys passes by date and track only, so freeze changes are reported here and never as dropped or added passes."""
    return {lk["id"]: (lk.get("freeze") or {}).get("state") for lk in (doc or {}).get("lakes", [])}


def diff_lakes(old: dict | None, new: dict) -> dict:
    """Per lake: added, dropped and reprocessed passes, the latest date and the freeze state before and after.

    `backwards` lists lakes whose status latest date moved earlier (or vanished). `fail` is set, with a reason,
    when more than MAX_DROPPED_SHARE of the previously published passes would be dropped.
    """
    before, after = _passes(old), _passes(new)
    latest_before, latest_after = _latest(old), _latest(new)
    freeze_before, freeze_after = _freeze(old), _freeze(new)
    lakes = []
    for lid in list(after) + [k for k in before if k not in after]:
        b, a = before.get(lid, {}), after.get(lid, {})
        lakes.append({
            "id": lid,
            "added": sorted(set(a) - set(b)),
            "dropped": sorted(set(b) - set(a)),
            "reprocessed": sorted(f"{k} {b[k]} -> {a[k]}" for k in set(a) & set(b) if b[k] and a[k] and b[k] != a[k]),
            "latest_before": latest_before.get(lid), "latest_after": latest_after.get(lid),
            "freeze_before": freeze_before.get(lid), "freeze_after": freeze_after.get(lid),
        })
    backwards = [r["id"] for r in lakes
                 if r["latest_before"] and (not r["latest_after"] or r["latest_after"] < r["latest_before"])]
    total_before = sum(len(v) for v in before.values())
    dropped = sum(len(r["dropped"]) for r in lakes)
    fail = None
    if total_before and dropped > MAX_DROPPED_SHARE * total_before:
        fail = (f"{dropped} of {total_before} previously published passes would be dropped "
                f"(more than {MAX_DROPPED_SHARE:.0%})")
    return {"lakes": lakes, "backwards": backwards, "total_before": total_before,
            "total_after": sum(len(v) for v in after.values()), "dropped": dropped,
            "added": sum(len(r["added"]) for r in lakes), "fail": fail}


def warnings(result: dict) -> list[str]:
    """One GitHub `::warning::` line per dropped pass and per lake whose latest date moved backwards."""
    out = []
    for r in result["lakes"]:
        for p in r["dropped"]:
            out.append(f"::warning::{r['id']}: pass {p} was published before and is gone from this build")
    for lid in result["backwards"]:
        r = next(x for x in result["lakes"] if x["id"] == lid)
        out.append(f"::warning::{lid}: latest date moved backwards, {r['latest_before']} -> {r['latest_after']}")
    return out


def summary_markdown(result: dict) -> str:
    """The comparison as Markdown for the job summary."""
    lines = ["## Lake passes compared with the last published build", "",
             f"{result['total_before']} passes before, {result['total_after']} after: "
             f"{result['added']} added, {result['dropped']} dropped.", "",
             "| Lake | Added | Dropped | Reprocessed | Latest before | Latest after | Freeze before | Freeze after |",
             "|---|---|---|---|---|---|---|---|"]
    for r in result["lakes"]:
        lines.append(f"| {r['id']} | {', '.join(r['added']) or '-'} | {', '.join(r['dropped']) or '-'} | "
                     f"{', '.join(r['reprocessed']) or '-'} | {r['latest_before'] or '-'} | {r['latest_after'] or '-'} | "
                     f"{r.get('freeze_before') or '-'} | {r.get('freeze_after') or '-'} |")
    if result["backwards"]:
        lines += ["", f"Latest date moved backwards: {', '.join(result['backwards'])}."]
    if result["fail"]:
        lines += ["", f"**Rebuild stopped:** {result['fail']}."]
    return "\n".join(lines) + "\n"


def text_report(result: dict) -> str:
    """The comparison as plain lines for the log."""
    lines = []
    for r in result["lakes"]:
        freeze = ""
        if r.get("freeze_before") != r.get("freeze_after"):
            freeze = f"; freeze {r.get('freeze_before') or '-'} -> {r.get('freeze_after') or '-'}"
        lines.append(f"{r['id']}: latest {r['latest_before'] or '-'} -> {r['latest_after'] or '-'}; "
                     f"added {len(r['added'])}, dropped {len(r['dropped'])}{freeze}")
        lines += [f"  + {p}" for p in r["added"]]
        lines += [f"  - {p}" for p in r["dropped"]]
        lines += [f"  ~ {p}" for p in r["reprocessed"]]
    lines.append(f"total: {result['total_before']} passes before, {result['total_after']} after, "
                 f"{result['added']} added, {result['dropped']} dropped")
    if result["fail"]:
        lines.append(f"FAIL: {result['fail']}")
    return "\n".join(lines)
