STACK_ID = "084_A_019"
MODE = "4005"
POLE = "DHDH"
BBOX = (71.4, 33.9, 72.1, 34.4)  # lon_min, lat_min, lon_max, lat_max; the CMR search area
WINDOW = (71.2, 33.8, 73.4, 34.8)  # west, south, east, north; what is built, analysed and shown
PLAIN_BOX = (72.10, 34.10, 72.25, 34.28)  # noisy plain ground for the step rule's shuffles; land cover not checked
GAP_START = "2026-07-27T22:03:25Z"
GAP_END = "2026-08-10T00:55:27Z"
CRID = "P05023"
POLS = ("HHHH", "HVHV")
SOURCE = "A"

# OPERA DSWx-S1 WTR (water classification) layer class values.
# Source: OPERA Level-3 DSWx-S1A/B Product Specification, JPL D-108761 Rev A,
# Version 1.0.0, April 16, 2024, "Layer: 1 Water classification (WTR)".
# https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-docs/web-misc/opera/D-108761_OPERA_DSWx_S1AB_ProductSpec_Rev_A.pdf
# (linked from https://podaac.jpl.nasa.gov/dataset/OPERA_L3_DSWX-S1_V1)
DSWX_WTR_NOT_WATER = 0
DSWX_WTR_OPEN_WATER = 1
DSWX_WTR_INUNDATED_VEGETATION = 3
DSWX_WTR_HAND_MASKED = 250
DSWX_WTR_LAYOVER_SHADOW_MASKED = 251
DSWX_WTR_FILL = 255
DSWX_WTR_WATER_VALUES = frozenset({DSWX_WTR_OPEN_WATER, DSWX_WTR_INUNDATED_VEGETATION})
DSWX_WTR_INVALID_VALUES = frozenset(
    {DSWX_WTR_HAND_MASKED, DSWX_WTR_LAYOVER_SHADOW_MASKED, DSWX_WTR_FILL}
)

# Lake Watch method constants (docs: global-constraints in the Lake Watch plan).
DROP_DB = 3.0  # dark = HH and HV both at least this far below the window median
BRIGHT_PASS_DB = 3.0  # a pass whose window-median HH is further than this from its track median is excluded
MIN_LOOKS = 3  # valid same-track passes needed for a trend
MIN_OBSERVABLE = 0.5  # share of the lake zone that must be observable
NOISE_FLOOR_KM2 = 0.005
CHANGE_FACTOR = 2.0
SPECKLE_BOX = 3  # boxcar width (pixels) applied to linear power before dB
CLOUD_WINDOW = ("2026-06-17", "2026-08-04")  # inclusive; headline cloud count
