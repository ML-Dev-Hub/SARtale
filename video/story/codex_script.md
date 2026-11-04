# SARtale Lake Watch — demo narration

## Main cut: 34 seconds, six shots

78 spoken words (counting “thirty-one” and “cloud-window” as two each). Read warmly and directly, at roughly 140 words per minute. Stress **Find. Compare. Brief.** Leave a small beat between the closing sentences. These are edit timings, not a measured voice recording; time the read before locking the cut.

| Time | Spoken line | Big caption (maximum six words) | Visual |
|---|---|---|---|
| 0:00–0:03 | SARtale Lake Watch: tracking lakes through clouds. | Lake Watch: lakes through clouds | Open immediately on the real Lake Watch start screen with the SARtale name visible. No separate logo intro. |
| 0:03–0:11 | In Pakistan, SUPARCO tracked one hundred and thirty-one potentially dangerous lakes. Clouds limited its optical checks of mountain lakes above roads and villages. | 131 lakes. Clouds limit the view. | Show the dated SUPARCO report: **2 July 2026**, based on **16 June imagery**. Frame its lake imagery and cloud limitation together; keep the agency and date readable. This is the one local problem: clouds obscure the lakes people need to check. |
| 0:11–0:14 | Find a lake with NISAR radar. | Find a lake | Real **Lake Watch** list and locator. Select Attabad, retaining its “landslide-dammed control” label. This means finding an entry to inspect, not discovering a previously unknown lake. |
| 0:14–0:18 | Compare its readings over time, with uncertainty in view. | Compare readings over time | Attabad detail: show **Area by track**, then focus on the status sentence with its date and noise. Keep “water area in the search window” visible. Use the actual chart; do not animate invented growth. |
| 0:18–0:22 | Brief your team with dates, evidence, and limits. | Brief your team | Click **Print lake brief**, then cut directly to its real print preview. Frame the status, dated readings and limits. Keep the footer stating that official warnings come from PMD and NDMA readable. |
| 0:22–0:34 | Sixty valid looks across eleven lakes in our cloud-window dataset. All eleven read Stable. Indicative screening, using provisional data. Keep looking. Keep checking. | 60 valid looks. 11 lakes. | Return to the real Lake Watch coverage headline and Stable list. Retain the interval **17 June–4 August 2026** as a supporting date label. At about 0:30, dissolve to the SARtale mark and replace the big caption with **Keep looking. Keep checking.** Hold to the end. |

Throughout shots 3–6, retain a readable supporting label: **Indicative only · NISAR PROVISIONAL**. On the close, retain **Official warnings: PMD and NDMA**. These are supporting labels, separate from the one big caption. Do not shrink them into an unreadable disclaimer. Use real app captures and the actual report, not a fabricated dashboard or disaster image. The final proof is observation coverage, not demonstrated hazard detection.

## Alternatives

Slogans (replace the final four words and end-card caption):

- **Clouds pass. Evidence stays.**
- **Look closer. Check further.**

Opening lines (replace shot 1; keep the full product name on screen from frame one):

- **SARtale Lake Watch: lake checks through clouds.**
- **SARtale Lake Watch: radar for lake review.**

## Honesty check and source ledger

| Line or visual that could overclaim | Required interpretation and evidence |
|---|---|
| “Tracking lakes through clouds”; “Find a lake with NISAR radar.” | Radar can observe through cloud, but this detector is **indicative only**. Neither line promises continuous coverage, accurate shorelines, new-lake discovery or observation through terrain shadow. The list contains selected lake sites and controls, not all hazardous lakes in Pakistan. |
| “SUPARCO tracked … 131 potentially dangerous lakes.” | A dated SUPARCO monitoring count, not SARtale coverage or a count of imminent outbursts. The supplied [research note, B2](../../docs/research_notes/Glacial%20lake%20watch/codex_glacial_lakes.md) records **131 potentially dangerous locations**, the **2 July 2026** update, **16 June** imagery and cloud-limited recent assessment. Retain that date in shot 2. Do not imply SUPARCO lacks radar capability or all monitoring stopped. |
| “Compare its readings … with uncertainty in view.” | Compare indicative radar estimates on the same track, not measured lake volume or flood probability. [lakes.json](../../app/public/data/lakes.json) gives Attabad’s latest status-track reading as **23 October 2026**, **7 looks**, **0.128 km²** versus a prior median **0.135 km²**, with noise **0.013 km²** (rounded as the app does). These are search-window estimates; noise is not a complete accuracy bound. |
| The radar picture or area chart looks precise. | Sentinel-2 agreement is weak: `checks[].iou` rounds to **0.11 Attabad, 0.01 Khurdopin, 0.03 Passu, 0.02 Shisper**—a range of **0.01–0.11**. Even Attabad’s similar area does not validate the boundary. Keep the provisional/indicative labels visible; do not call the method validated. Radar pictures are in radar geometry, not georeferenced map overlays. |
| “Brief your team …” | A demonstrated print-brief feature, not a claim of agency adoption, an official bulletin or automatic distribution. [admin-meeting.md](../../docs/admin-meeting.md) has no recorded answers or endorsements. Capture the actual print preview; clicking opens a print dialog rather than silently delivering a brief. |
| “Sixty valid looks across eleven lakes in our cloud-window dataset.” | Sum of `lakes[].cloud_window_looks` is **60**; the array has **11** entries, all with looks in `cloud_window`, **17 June–4 August 2026**. These are lake-level looks passing the pipeline checks, not 60 unique satellite passes or 60 detected changes. The window corresponds to reported cloud limitations; it does not establish cloud over every lake at every look or uninterrupted radar coverage. |
| “All eleven read Stable.” | All **11** `status.status` values are **Stable** in this build. Stable means the estimated change did not cross the method’s change threshold, **2 × its noise**, compared with earlier same-track readings. It does **not** mean safe, no hazard, no water change or no future outburst. Never substitute red Growing markers for dramatic effect. |
| “Using provisional data.” | The files here are **NISAR PROVISIONAL**, processing version **P05023**, subject to reprocessing. Preserve that wording in both the voice and supporting label. The JSON build timestamp is **2026-11-02T15:22:59Z**; do not present it as a live feed. |
| “Keep looking. Keep checking.” / alternative slogans | A call for continued evidence review, not a promise of protection. “Clouds pass. Evidence stays.” refers to retaining dated observations, not guaranteed availability or accuracy. **Official warnings come from PMD and NDMA.** SARtale does not predict floods or issue flood warnings. |

The structure follows the supplied [winner video study](../../docs/research_notes/Space%20Apps%20winners%20vs%20SARtale/winner_video_study.md): immediate name and purpose, a local numeric problem, three visible actions, existing proof, then a short slogan. Screen choices follow [story.json](../../app/src/content/story.json), [demo-script.md](../../docs/demo-script.md), [README.md](../../README.md), and the implemented Lake Watch detail and print brief.

Keep the other sourced stakes out of this short cut to avoid competing stories. The research material records Shisper’s **7 May 2022** outburst and Hassanabad KKH bridge destruction, and UNDP’s **more than 3,000 lakes / 33 hazardous / 7.1 million people at risk**. Those are separate historical or inventory contexts, not SARtale results; the UNDP 33 and SUPARCO 131 must not be presented as a measured increase. No claim that this prototype could have prevented the bridge loss is supported.

## Why the old narration missed the story

[The old cut](../short/narration.json) has useful restraint: it names radar, real coverage numbers, a brief and the official warning authorities. But it opens with a bureaucratic summary—“reported this summer that cloud limited its optical checks”—before viewers know the product or why it matters. It offers no concrete numeric scale for the problem.

Its middle packs the satellite, product, two regions, lake count, observation count and status concept into one sentence. “Reads it” and “while the clouds were in” are vague; the latter also sounds like confirmed cloud at every observation. Three broad segments give the editor too few clear action beats. The new version assigns one verb to each real screen and anchors the coverage claim to a dated dataset.

“For the duty officer” implies a user workflow the empty meeting log has not established. “One click prints” skips the print dialog. The old ending supplies caveats but omits PROVISIONAL and the fact that every lake currently reads Stable. “Built on NISAR, open source” describes implementation; it leaves little human idea to remember. The new close asks viewers to keep looking and checking, without promising flood prediction or warnings.
