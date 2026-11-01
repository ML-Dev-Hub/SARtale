"""The numbers behind the step layer: what choosing the best split inflates, the rule, and what it flags.

Prints: how much the best of several splits inflates a shuffled step; the limits from controls and shuffles; how the
ways of combining HH and HV compare on shuffled ground with synthetic steps added; false alarms under two kinds of
shuffle; flagged share by region at the rule and two other limits; what combining HH and HV does on the real data; step
dates; second steps a single split misses; whether a step survives dropping any one date or a further 1 dB on 14 July;
and whether a line fits better than a step. Run from the repository root, after `run_pipeline change`:
    conda run -n sartale python processing/checks/step_evidence.py
"""
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "processing"))
import numpy as np
from pyproj import Transformer

from sartale import config
from sartale.change import (
    STEP_CONTROL_RADIUS_M,
    _box_mask,
    _read_stack,
    _split_terms,
    best_split,
    looked_stack,
    shuffle_dates,
    step_flags,
    step_rule,
    step_stability,
    step_strength,
)
from sartale.sites import RADIUS_M, _footprint

warnings.simplefilter("ignore", RuntimeWarning)
COG = ROOT / "data" / "cog"
FARM_13KM = (71.925, 34.275, 6500.0)  # centre lon, lat and half width of the box tried in the first prototype
FARM_6KM = (71.925, 34.275, 3000.0)  # what that prototype's code actually read
TARBELA_BOX = (72.60, 34.00, 72.90, 34.30)
ATTOCK_BOX = (72.15, 33.87, 72.32, 33.96)
OCT6_PATCH = (71.82, 34.29, 72.15, 34.46)
OTHER_LIMITS = ((2.5, 3.0), (3.5, 4.0))

manifest = json.loads((ROOT / "app" / "public" / "data" / "manifest.json").read_text(encoding="utf-8"))
change, rule = manifest["change"], manifest["change"]["step"]
dates = rule["dates"]
limits = (rule["min_step_db"], rule["min_stability"])
sites = {s["id"]: s for s in json.loads((ROOT / "processing" / "sites_in.json").read_text(encoding="utf-8"))}
curves = {s["id"]: s for s in json.loads((ROOT / "app" / "public" / "data" / "sites.json").read_text(encoding="utf-8"))}
offsets = np.array([[change["removed_offsets_db"][d][p] for p in ("HH", "HV")] for d in dates], dtype=np.float32)
stack30, grid = _read_stack(COG, dates)
stack, layer = looked_stack(stack30 - offsets[:, :, None, None], grid)
del stack30
has_data = np.isfinite(stack).all(axis=(0, 1))
rng = np.random.default_rng(7)
to_utm = Transformer.from_crs(4326, layer.epsg, always_xy=True)


def disc(site: str, radius: float) -> np.ndarray:
    return _footprint(layer, sites[site]["lon"], sites[site]["lat"], radius)


def square(lon: float, lat: float, half: float) -> np.ndarray:
    x, y = to_utm.transform(lon, lat)
    return np.outer(np.abs(layer.y - y) <= half, np.abs(layer.x - x) <= half)


def pixels(mask: np.ndarray, limit: int = 150_000) -> np.ndarray:
    index = np.flatnonzero((mask & has_data).ravel())
    if index.size > limit:
        index = rng.choice(index, limit, replace=False)
    return stack[:, :, *np.unravel_index(index, has_data.shape)]


step, split = best_split(stack)
stability = step_stability(stack, split)
size, strength = step_strength(step, stability)
flags = step_flags(size, strength, *limits)
scored = np.isfinite(size)

spread = np.nanmedian(np.abs(stack - np.nanmedian(stack, axis=0)), axis=0)
cut = [np.quantile(spread[p][has_data], 0.25) for p in range(2)]
stable_ground = has_data & (spread[0] <= cut[0]) & (spread[1] <= cut[1])
plain = _box_mask(layer, config.PLAIN_BOX)
regions = {
    f"Peshawar, {STEP_CONTROL_RADIUS_M:.0f} m": disc("peshawar-city", STEP_CONTROL_RADIUS_M),
    f"Hazro, {STEP_CONTROL_RADIUS_M:.0f} m": disc("hazro-built-up", STEP_CONTROL_RADIUS_M),
    "Tarbela pool, 1 km (water)": disc("tarbela-pool", 1000),
    "Tarbela shore, 150 m": disc("tarbela-shore", RADIUS_M),
    "Tarbela shore, 450 m": disc("tarbela-shore", 450),
    "Attock, 150 m": disc("indus-attock", RADIUS_M),
    "Attock, 450 m": disc("indus-attock", 450),
    "Plain near Swabi, 450 m": disc("swabi-plain", 450),
    "Plain east of Mardan, 450 m": disc("mardan-plain", 450),
    "Plain box": plain,
    "Box at 71.925, 6 km": square(*FARM_6KM),
    "Box at 71.925, 13 km": square(*FARM_13KM),
    "6 Oct patch": _box_mask(layer, OCT6_PATCH),
    "Tarbela box": _box_mask(layer, TARBELA_BOX),
    "Attock box": _box_mask(layer, ATTOCK_BOX),
    "Whole window": scored,
}


def share(flag: np.ndarray, mask: np.ndarray) -> float:
    return 100 * float(flag[mask & scored].mean())


print(f"{int(scored.sum())} scored pixels at {rule['pixel_m']} m; dates {', '.join(d[5:] for d in dates)}")
print(f"rule in the manifest: mean step {limits[0]} dB and stability {limits[1]}, same direction in HH and HV, same split")

print("\nInflation from choosing the best split, per-pixel shuffles: |step| dB, then stability")
for name, mask in (("Stable ground", stable_ground), ("Plain box", plain), ("Whole window", scored)):
    values = shuffle_dates(pixels(mask), rng)
    for p, pol in enumerate(("HH", "HV")):
        d, t = _split_terms(values[:, p], 2)
        middle = d.shape[0] // 2
        fixed, best = np.abs(d[middle]), np.nanmax(np.abs(d), axis=0)
        fixed_t, best_t = t[middle], np.nanmax(t, axis=0)
        print(f"  {name:14s} {pol}: one fixed split p50 {np.nanmedian(fixed):.2f} p99 {np.nanpercentile(fixed, 99):.2f}; "
              f"best of {d.shape[0]} p50 {np.nanmedian(best):.2f} p99 {np.nanpercentile(best, 99):.2f}; "
              f"ratio p50 {np.nanmedian(best) / np.nanmedian(fixed):.2f} p99 {np.nanpercentile(best, 99) / np.nanpercentile(fixed, 99):.2f}; "
              f"stability fixed p99 {np.nanpercentile(fixed_t, 99):.2f}, best p99 {np.nanpercentile(best_t, 99):.2f}")

controls = np.any([disc(s, STEP_CONTROL_RADIUS_M) for s in sites if "control" in sites[s]["role"].lower()], axis=0)
print("\nRule, recomputed:", step_rule(stack, controls, plain & has_data))
print("Control pixels:", int((controls & has_data).sum()))


def combine(terms: tuple, name: str, a: float, b: float) -> np.ndarray:
    d, t = terms
    same, ad = np.sign(d[0]) == np.sign(d[1]), np.abs(d)
    hh, hv = (ad[0] >= a) & (t[0] >= b), (ad[1] >= a) & (t[1] >= b)
    return {"each passes alone": same & hh & hv, "mean and RMS": same & (ad.mean(axis=0) >= a) & (np.sqrt((t ** 2).mean(axis=0)) >= b),
            "HH only": hh, "either": hh | hv}[name]


def scored_terms(v: np.ndarray) -> tuple:
    d, o = best_split(v)
    return d, step_stability(v, o)


print("\nWays to combine HH and HV, on the plain box: best limits with shuffled false alarms at most 1%, and the share of")
print("synthetic steps found, added to shuffled pixels at a random split. Sizes are HH/HV dB. The known sites play no part.")
plain_values = pixels(plain, 10 ** 6).astype(np.float64)
nulls = [scored_terms(shuffle_dates(plain_values, rng)) for _ in range(3)]
alts = {}
for size_db, ratio in ((3, 1.0), (4, 1.0), (5, 1.0), (6, 1.0), (3, 0.6), (4, 0.6), (5, 0.6), (6, 0.6)):
    v = shuffle_dates(plain_values, rng)
    position = rng.integers(2, v.shape[0] - 1, v.shape[2])
    sign = rng.choice([-1.0, 1.0], v.shape[2])
    after = np.arange(v.shape[0])[:, None] >= position[None]
    v[:, 0] += size_db * sign * after
    v[:, 1] += ratio * size_db * sign * after
    alts[(size_db, ratio)] = scored_terms(v)
grid = [(a, b) for a in (2.0, 2.5, 3.0, 3.5) for b in (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)]
for name in ("each passes alone", "mean and RMS", "HH only", "either"):
    rows = []
    for a, b in grid:
        fa = 100 * float(np.mean([combine(n, name, a, b).mean() for n in nulls]))
        if fa <= 1.0:
            found = {k: 100 * float(combine(t, name, a, b).mean()) for k, t in alts.items()}
            rows.append((float(np.mean(list(found.values()))), a, b, fa, found))
    mean_found, a, b, fa, found = max(rows, key=lambda r: r[0])
    print(f"  {name:18s} best {a} dB, {b}: false alarms {fa:.2f}%, mean found {mean_found:.0f}%; "
          + " ".join(f"{k[0]}/{k[0] * k[1]:.1f}:{v:.0f}" for k, v in found.items()))


def false_alarms(values: np.ndarray, level: tuple[float, float], shuffles: int = 5) -> float:
    out = []
    for _ in range(shuffles):
        v = shuffle_dates(values, rng)
        s, o = best_split(v)
        out.append(step_flags(*step_strength(s, step_stability(v, o)), *level).mean())
    return 100 * float(np.mean(out))


print("\nFalse alarms, percent")
samples = {"Stable ground": pixels(stable_ground), "Plain box": pixels(plain), "Box at 71.925, 13 km": pixels(square(*FARM_13KM)),
           "Whole window": pixels(scored)}
for level in (limits, *OTHER_LIMITS):
    print(f"  limits {level}: per-pixel shuffle " + ", ".join(f"{n} {false_alarms(v, level):.3f}" for n, v in samples.items()))
for name, values in (("Plain box", samples["Plain box"]), ("Whole window", samples["Whole window"])):
    hits = []
    for _ in range(200):  # the same order for every pixel keeps patches together, as weather would
        v = values[rng.permutation(values.shape[0])]
        s, o = best_split(v)
        hits.append(100 * step_flags(*step_strength(s, step_stability(v, o)), *limits).mean())
    print(f"  whole-area shuffle, 200 orders, {name}: median {np.median(hits):.3f}, p90 {np.percentile(hits, 90):.3f}, max {np.max(hits):.3f}")

print("\nPercent flagged by region, at the rule and two other limits")
for name, mask in regions.items():
    cells = [share(step_flags(size, strength, *level), mask) for level in (limits, *OTHER_LIMITS)]
    print(f"  {name:30s} n={int((mask & scored).sum()):8d} " + " ".join(f"{c:6.2f}" for c in cells))

print("\nWhat combining HH and HV does on the real data, at the same limits:")
print("  HH alone, HV alone, either, each passes alone, the rule (mean and RMS); last column HH >= 3 dB with no stability test")
hh = (np.abs(step[0]) >= limits[0]) & (stability[0] >= limits[1])
hv = (np.abs(step[1]) >= limits[0]) & (stability[1] >= limits[1])
both = hh & hv & (np.sign(step[0]) == np.sign(step[1]))
for name, mask in regions.items():
    print(f"  {name:30s} " + " ".join(f"{share(f, mask):6.2f}" for f in (hh, hv, hh | hv, both, flags, np.abs(step[0]) >= 3)))
print(f"  where either polarization passes, they agree in direction at {100 * float((np.sign(step[0]) == np.sign(step[1]))[hh | hv].mean()):.1f}% of pixels")

print("\nStep dates among flagged pixels, percent; up then down")
header = [d[5:] for d in rule["split_dates"]]
print(f"  {'':30s} " + " ".join(f"{h:>6s}" for h in header) + "  |  " + " ".join(f"{h:>6s}" for h in header))
for name, mask in regions.items():
    here = flags & mask
    if not here.any():
        print(f"  {name:30s} none flagged")
        continue
    up = [100 * float(((split == dates.index(d)) & (step[0] > 0) & here).sum() / here.sum()) for d in rule["split_dates"]]
    down = [100 * float(((split == dates.index(d)) & (step[0] < 0) & here).sum() / here.sum()) for d in rule["split_dates"]]
    print(f"  {name:30s} " + " ".join(f"{c:6.1f}" for c in up) + "  |  " + " ".join(f"{c:6.1f}" for c in down))

print("\nSite curves: best split, then the best second split inside the longer side (needs 4 dates)")
print("  (a line for each site; stability here is the RMS of the two polarizations; both are read from the curve)")
removed = np.array([[change["removed_offsets_db"][d][p] for p in ("HH", "HV")] for d in dates])
for sid, s in curves.items():
    by_date = {p["date"]: p for p in s["series"]}
    v = np.array([[by_date[d]["hh_db"], by_date[d]["hv_db"]] for d in dates], dtype=np.float64) - removed
    first = s["step"]
    k = dates.index(first["date"])
    line = (f"  {sid:16s} {first['previous_date'][5:]} to {first['date'][5:]}: HH {first['hh_db']:+.2f} HV {first['hv_db']:+.2f}, "
            f"t {first['stability']:.1f}, flagged {first['flagged']}, map {first['map_share']:.2f}")
    part, base = (v[k:], k) if len(dates) - k >= k else (v[:k], 0)
    if part.shape[0] >= 4:
        d2, o2 = best_split(part[:, :, None])
        size2, t2 = step_strength(d2, step_stability(part[:, :, None], o2))
        line += (f"; second {dates[base + int(o2[0]) - 1][5:]} to {dates[base + int(o2[0])][5:]}: HH {d2[0, 0]:+.2f} HV {d2[1, 0]:+.2f}, "
                 f"t {t2[0]:.1f}, passes {bool(step_flags(size2, t2, *limits)[0])}")
    print(line)

print("\nSecond step among flagged pixels, by the same rule, on the side with at least 4 dates")
ys, xs = np.nonzero(flags)
orders = split[ys, xs]
second = np.zeros(flags.shape, bool)
for k in np.unique(orders):
    at = orders == k
    before, after = stack[:k, :, ys[at], xs[at]], stack[k:, :, ys[at], xs[at]]
    for part in (before, after):
        if part.shape[0] >= 4:
            s, o = best_split(part)
            f = step_flags(*step_strength(s, step_stability(part, o)), *limits)
            second[ys[at], xs[at]] |= f
for name, mask in regions.items():
    if (flags & mask).any():
        print(f"  {name:30s} {100 * float(second[flags & mask].mean()):6.1f}% of {int((flags & mask).sum())}")
print("  Tarbela box, pixels bright on 26 Jul and dark on 19 and 31 Aug, then back above -12 dB on all of 24 Sep, 6 Oct, 18 Oct:")
i26, i19, i31 = dates.index("2026-07-26"), dates.index("2026-08-19"), dates.index("2026-08-31")
late = [dates.index(d) for d in ("2026-09-24", "2026-10-06", "2026-10-18")]
pulse = regions["Tarbela box"] & (stack[i26, 0] > -10) & (stack[i19, 0] < -13) & (stack[i31, 0] < -13) & (stack[late, 0] > -12).all(axis=0)
print(f"    n={int(pulse.sum())}, flagged {share(flags, pulse):.1f}%, with a second step {100 * float(second[pulse].mean()):.1f}%")

print("\nDoes a flagged step survive dropping any one date? Percent of flagged pixels flagged again, same direction")
print(f"  {'':30s} " + " ".join(f"{d[5:]:>6s}" for d in dates) + "   all")
kept = {}
for i in range(len(dates)):
    part = np.delete(stack, i, axis=0)
    s, o = best_split(part)
    f = step_flags(*step_strength(s, step_stability(part, o)), *limits)
    kept[i] = f & (np.sign(s[0]) == np.sign(step[0]))
every = np.all(list(kept.values()), axis=0)
for name, mask in regions.items():
    here = flags & mask
    if here.any():
        print(f"  {name:30s} " + " ".join(f"{100 * float(kept[i][here].mean()):6.1f}" for i in range(len(dates)))
              + f" {100 * float(every[here].mean()):5.1f}")

print("\n14 July reads low on plain ground even after normalising. Percent of flagged pixels flagged again with 1 dB more added to it")
raised = stack.copy()
raised[0] += 1.0
s_raised, o_raised = best_split(raised)
again = step_flags(*step_strength(s_raised, step_stability(raised, o_raised)), *limits) & (np.sign(s_raised[0]) == np.sign(step[0]))
for name, mask in regions.items():
    if (flags & mask).any():
        print(f"  {name:30s} {100 * float(again[flags & mask].mean()):6.1f}")
del raised

print("\nDoes a line fit better than a step? Percent of flagged pixels where a straight trend through the dates leaves less scatter")
days = np.array([np.datetime64(d, "D").astype(int) for d in dates], dtype=np.float64)
days -= days.mean()
x = np.stack([days, np.ones_like(days)], axis=1)
fit = np.linalg.pinv(x)
for name, mask in regions.items():
    here = flags & mask
    if not here.any():
        continue
    v = stack[:, 0, here].astype(np.float64)
    keep = np.isfinite(v).all(axis=0)
    v = v[:, keep]
    line_error = ((v - x @ (fit @ v)) ** 2).sum(axis=0)
    k = split[here][keep]
    before = np.arange(len(dates))[:, None] < k[None]
    n1 = before.sum(axis=0)
    mean1 = (v * before).sum(axis=0) / n1
    mean2 = (v * ~before).sum(axis=0) / (len(dates) - n1)
    step_error = ((v - np.where(before, mean1, mean2)) ** 2).sum(axis=0)
    print(f"  {name:30s} {100 * float((line_error < step_error).mean()):6.1f}")

print(f"\nWhole window: {share(flags, scored):.2f}% of scored pixels flagged; manifest says {100 * rule['flagged_share']:.2f}%")
frame = ROOT / "app" / "public" / "data" / rule["frame"]
print(f"step frame {frame.stat().st_size / 1e6:.2f} MB")
