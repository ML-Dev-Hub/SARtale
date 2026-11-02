# Glacial lake watch: feasibility spike (2 Nov 2026)

Throwaway test, not product code. Scripts and images are in `spike/`.

## What was tested

- NISAR L2 GCOV PROVISIONAL (P05023), mode 4005 (40+5 MHz), HH/HV, 10 m, EPSG:32643.
- Shisper (box 74.56–74.64 E, 36.29–36.37 N): 24 passes, 18 Jun – 23 Oct 2026.
- Attabad Lake, a known landslide-dammed lake used as a positive control (box 74.79–74.92 E, 36.28–36.37 N): 18 passes before a server disconnect.

## Findings

1. **Partial reads work.** The GCOV grids are stored in 512×512 gzip chunks. Reading a 7 km window over HTTPS range requests fetched 24–43 MB per 7 GB file, in 11–28 s each. Whole-region monitoring is feasible without bulk downloads. A production reader needs retries, because one connection drop occurred.
2. **Three viewing geometries cover Hunza:** tracks 055 A, 156 A and 063 D. In the 4005 mode, track 055 covers Attabad but only clips the edge of the Shisper box (99% empty). Every geometry repeats every 12 days, so together they give a pass every few days. Grids from different tracks share the same 10 m posting and were pixel-aligned in this test.
3. **Bad passes exist.** 7 Jul 156A reads about +25 dB everywhere, and 5 Sep 156A is anomalous over the lake. The robust-median and outlier screening from the Peshawar stack is needed here too.
4. **Fixed dB thresholds fail in mountains.** HH < −18 and HV < −26 missed Attabad Lake entirely and flagged slopes facing away from the radar.
   - Attabad Lake: HH ≈ −13 dB, HV ≈ −20 dB.
   - Surrounding terrain: HH ≈ −7 dB, HV ≈ −14 dB.
   - Radar shadow: ≈ −22 dB, darker than the lake.
5. **The two-view rule works.** Call a pixel water only if HH and HV are both at least 4 dB below the scene median in an ascending AND a descending view, using a per-pixel median over each view's passes.
   - Attabad: a clean lake outline with little clutter, 3.0 km² inside the window.
   - Shisper: only the Hunza river and scattered specks, so no persistent two-view water candidate in the box from 18 Jun to 23 Oct 2026. This does NOT show there was no lake. Medians over the season would erase a brief filling, the lake's maximum is usually in May (before these passes), and published absence evidence only runs to Sep 2024. Codex's review corrected this point (see codex_glacial_lakes.md, A2).
   - The reason it works: shadow and layover depend on look direction, water does not.
6. **Not yet tested:**
   - accuracy of the area estimate against an optical outline
   - small lakes below about 0.05 km²
   - frozen lakes (winter) and wind-roughened lakes
   - change over time per lake, as opposed to a static outline
   - a moraine-dammed glacial lake (as opposed to a landslide-dammed lake)
