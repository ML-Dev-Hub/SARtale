"""Lake Watch settings and method constants."""
# No CRID is pinned: every pass keeps the composite release ID (CRID) of its own file, so a new NASA release is
# picked up without a code change. lakes.json lists the CRIDs used.

# Lake Watch method constants (docs: global-constraints in the Lake Watch plan).
DROP_DB = 3.0  # dark = HH and HV both at least this far below the window median
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
MIN_LOOKS = 3  # valid same-track passes needed for a trend
MIN_OBSERVABLE = 0.5  # share of the lake zone that must be observable
NOISE_FLOOR_KM2 = 0.005
CHANGE_FACTOR = 2.0
SPECKLE_BOX = 3  # boxcar width (pixels) applied to linear power before dB
CLOUD_WINDOW = ("2026-06-17", "2026-08-04")  # inclusive; headline cloud count
