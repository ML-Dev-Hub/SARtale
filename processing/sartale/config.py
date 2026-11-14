"""Lake Watch settings and method constants."""
# No CRID is pinned: every pass keeps the composite release ID (CRID) of its own file, so a new NASA release is
# picked up without a code change. lakes.json lists the CRIDs used.

# Lake Watch method constants (docs: global-constraints in the Lake Watch plan).
# Lake water is method D17 (.superpowers/sdd/post-merge/method-study.md): a Lee filter on linear HH power, then water =
# valid and HH at least DROP_DB below the window-median HH. HV is not used for water; it stays in the pass screens.
METHOD_ID = "D17"
DROP_DB = 3.0  # water: HH at least this far below the window-median HH (the screens' dark share: HH and HV both)
LEE_BOX = 7  # Lee filter window (pixels) on linear HH power, before dB
LEE_ENL = 4.0  # equivalent number of looks of the Lee filter (the median GCOV numberOfLooks is 4.5-5)
# The window-median HH that water is measured against leaves out radar layover and shadow, from the Copernicus GLO-30
# DEM, the look azimuth fitted to GCOV's numberOfLooks layer (NISAR looks left) and an incidence angle of DEM_INCIDENCE_DEG.
# Inside the lake zone nothing is masked: a flat lake surface is almost never in layover or shadow.
DEM_LOOK_AZIMUTH_DEG = {"A": 255.0, "D": 105.0}  # ground azimuth of the look, from north, clockwise
DEM_INCIDENCE_DEG = 40.0
DEM_MARGIN_M = 3000.0  # DEM read this far past the window, so terrain outside it can cast shadow into it
# The window cache (lakes-fetch, data/lakes) keeps each pass cropped to the lake zone (outline buffered 200 m, or the
# circle) plus WINDOW_MARGIN_M on every side, inside the 6 km search window, with HH, HV and looks as CACHE_DTYPE.
# The window median D17 measures water against is taken over the cropped window. A Sentinel-2 check records the
# margin in its key (lakebuild.check_key), so a change of margin re-checks every lake. float16 keeps 3 significant
# digits of linear power down to about -42 dB (subnormal below), far finer than the 3 dB water rule.
WINDOW_MARGIN_M = 1500.0
CACHE_DTYPE = "float16"
FETCH_NEW_LAKES_PER_RUN = 12  # the weekly refresh fetches at most this many lakes new to the cache (lakes-fetch)
BRIGHT_PASS_DB = 3.0  # a pass whose window-median HH is further than this from its track median is excluded
# Second per-track screen (ruling R-F1): robust z-score, (value - track median) / max(1.4826 * MAD, floor),
# of each pass's window dark-pixel share and window-median HV. |z| > OUTLIER_Z excludes the pass.
OUTLIER_Z = 3.5
OUTLIER_SHARE_FLOOR = 0.01  # dark share: 1 percentage point, so 3.5 points is the smallest exclusion
OUTLIER_HV_FLOOR_DB = 1.0  # HV median: 1 dB, so 3.5 dB is the smallest exclusion (early-summer HV dips of ~2-2.5 dB stay in)
OUTLIER_MIN_PASSES = 4  # fewer passes on a track: no robust screen
# Passes excluded by hand, with the reason shown in each affected lake's `excluded` list. Applied to every
# lake that has the pass and has not already excluded it by a computed screen.
MANUAL_EXCLUSIONS = {"2026-09-05_156A": "anomalous over Hunza lakes; spec §5"}
MIN_LOOKS = 3  # earlier valid passes on its own track a pass needs before it is compared (gets a z)
MIN_OBSERVABLE = 0.5  # share of the lake zone that must be observable
NOISE_FLOOR_KM2 = 0.005
# Alert levels (lakestatus.assess). Every valid pass, on any track, is compared with the median of up to BASELINE_PASSES
# earlier valid passes on its own track: z = (area - baseline) / noise, where noise is the track's pass-to-pass noise on
# up to NOISE_PASSES of those passes, floored at max(NOISE_FLOOR_KM2, NOISE_REL_FLOOR x baseline).
BASELINE_PASSES = 6
NOISE_PASSES = 8
NOISE_REL_FLOOR = 0.02
CHANGE_FACTOR = 2.0  # |z| at least this: one pass is a Watch; two passes in a row (same sign) an Alert or a Decrease noted
CUSUM_K = 0.5  # CUSUM over the z stream: allowance per pass ...
CUSUM_H = 4.0  # ... and the sum that makes a Watch
AFTER_OPEN_PASSES = 2  # after a frozen spell, this many valid passes per track only rebuild the baseline
MIN_VALIDATION_IOU = 0.4  # a lake whose Sentinel-2 check (lakes-check) overlaps less than this gets no level
SPECKLE_BOX = 3  # boxcar width (pixels) applied to linear power before dB, for the pass screens and the pictures
CLOUD_WINDOW = ("2026-06-17", "2026-08-04")  # inclusive; headline cloud count
# Open-water season for the Sentinel-2 cross-check of lakes (lakes-check), as (month, day) pairs, inclusive, in any
# year. Outside it a lake can be frozen or snow-covered (Shazore was open 26 Jun-9 Oct 2026 and frozen by 19 Oct;
# Rogheli had snow and ice from early October), and optical MNDWI never counts snow or ice as water, so a pair then is
# no test of radar water. The absence check of a no-lake site does not use it: it runs all year and takes only scenes
# whose lake zone is clear of cloud, snow and ice (lakecheck.absence_check).
OPEN_WATER_SEASON = ((6, 15), (9, 30))
# A site the register holds as "no lake now" is re-checked with Sentinel-2 at every refresh, all year (lakes-absence).
# Water on more than this share of the lake zone's clear pixels turns it into "Lake may be forming". A site sets its
# own `forming_share` in lakes_in.json when its empty zone holds other water (a river, a pond nearby); this is the
# default. It comes from Shisper, the reference empty basin (docs/DATA_SOURCES.md, "No lake now"): in the 1 km circle
# the empty basin read 0.6-1.6% water on every clear scene of 15 Jun-30 Sep 2026 (stream threads), while the lake
# filled 6.8-12.6% (26 Mar and 5 Apr 2022, 20 and 25 May 2020). 4% sits clear of both.
FORMING_WATER_SHARE = 0.04

# Frozen status (lakes-freeze; .superpowers/sdd/post-merge/frozen-spike.md and the lake detail and frozen design).
# Air temperature is NASA POWER daily T2M at the lake, moved from the POWER cell's height to the lake's with this lapse
# rate (degrees C per km of height; negative: colder higher up).
LAPSE_C_PER_KM = -6.5
FREEZE_COLD_RUN_DAYS = 7  # Frozen (likely): daily mean below 0 C on at least this many days in a row ...
FREEZE_FDD = 30.0  # ... and at least this many freezing degree-days (sum of -T2M on days below 0 C) since 1 Sep
BREAKUP_WARM_RUN_DAYS = 7  # Break-up likely: a frozen lake with daily mean above 0 C on this many days in a row
THAW_WARM_RUN_DAYS = 14  # Released (no longer counted as frozen): this many warm days in a row plus one radar pass back within its summer range
# Radar break-up signature: the lake core at least this much brighter against its window than its summer level, in
# both HH and HV, and its dark share at least BREAKUP_DARK_DROP below its summer level (Shazore, 25 Jun and 2 Jul 2026).
BREAKUP_CONTRAST_DB = 2.0
BREAKUP_DARK_DROP = 0.3
# A radar pass is back within its summer range when its core contrast is within this many dB of summer in both HH and
# HV and its dark share no more than SUMMER_DARK_DROP below summer.
SUMMER_CONTRAST_DB = 1.0
SUMMER_DARK_DROP = 0.15
SUMMER_MIN_PASSES = 3  # fewer open-water-season passes on a track: the radar break-up test is not assessed there
# Sentinel-2 override: the clearest scene of the last S2_FREEZE_DAYS days whose lake zone is at least S2_FREEZE_CLEAR
# clear of cloud, cloud shadow and their 100 m edge; snow/ice on S2_FROZEN_SNOW_SHARE of the lake seen clear says
# frozen, water on S2_OPEN_WATER_SHARE says open. The evidence holds until other evidence or the rules release it.
S2_FREEZE_DAYS = 7
S2_FREEZE_CLEAR = 0.8
S2_FROZEN_SNOW_SHARE = 0.8
S2_OPEN_WATER_SHARE = 0.5
# Both shares are measured over the lake itself (its unbuffered outline, or the summer radar water core for a lake
# without one), over its clear pixels; a scene counts only when at least this share of the lake itself is clear.
S2_TARGET_CLEAR = 0.5
POWER_STALE_DAYS = 10  # newest POWER day older than this at the build: "Not assessed"
FREEZE_SEASON_START = (9, 1)  # freezing degree-days and the freeze state reset on 1 Sep
FREEZE_SEASON_END = (5, 31)  # 1 Jun-31 Aug the state is open unless Sentinel-2 shows snow or ice
