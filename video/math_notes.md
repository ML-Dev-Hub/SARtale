# Equations and figures planned for the video

Equations as drawn:

1. Decibels: sigma_dB = 10 log10(P), and a 10 dB rise is ten times the power. The product is gamma-0 backscatter.
2. Season median comparison ("Unusual dates"): z = |x_t - median| / (1.4826 MAD), floored scale, threshold 3.5.
3. Step at split k: Delta = mean(after) - mean(before).
4. Stability: t = |Delta| / ( s * sqrt(1/n1 + 1/n2) ), where s is the pooled within-segment standard deviation, using n - 2, floored at 0.5 dB.
5. Best split: the split with the largest t_HH^2 + t_HV^2, at least 2 dates each side.
6. Flag rule: sign(Delta_HH) = sign(Delta_HV), and (|Delta_HH| + |Delta_HV|)/2 >= 3 dB, and sqrt((t_HH^2 + t_HV^2)/2) >= 3.

Figures planned, for Tarbela south-east shore, from app/public/data/sites.json, 8 dates (no 2 Jul):
- HH: 14 Jul -6.07, 26 Jul -7.64, 19 Aug -16.60, 31 Aug -16.79, 12 Sep -15.62, 24 Sep -14.06, 6 Oct -12.98, 18 Oct -12.77.
- Unusual-dates score on 19 Aug: 1.17, threshold 3.5.
- Raw site-curve split scan, HH steps -7.95, -4.34, -2.08, -0.73, -0.08; HV -5.04, -3.10, -1.78, -0.91, -0.29; t HH 5.77, 1.66, 0.71, 0.23, 0.02; t HV 6.95, 2.09, 1.02, 0.47, 0.13.
- The app card, after scene normalisation: step HH -8.14, HV -5.26, stability 6.12.
- Whole map: 1.39% flagged, per-pixel shuffle 0.25%, whole-scene shuffle maximum 1.26% over 200.
- 2 Jul HV jump about 14 dB; season peak 78.5 thousand cusecs on 23 Jul; gap 27 Jul 22:03:25Z to 10 Aug 00:55:27Z.
