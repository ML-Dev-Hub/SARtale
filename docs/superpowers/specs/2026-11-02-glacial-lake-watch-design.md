# SARtale Lake Watch: design

Date: 2 Nov 2026. Team SARcastic Scientists (Saeed Ahmad, Shaharyar Sajid), NASA Space Apps 2026, challenge "Dancing with the SARs", Islamabad Local Event.

Supersedes the product direction in `docs/SARtale-hackathon-plan.md`. That plan's data handling, change test and event logistics still apply where this document does not say otherwise.

## 1. Intent

**Problem.** Disaster teams in Gilgit-Baltistan and upper Khyber Pakhtunkhwa have to decide which glacial lakes to inspect, and which villages, roads and power plants downstream to brief. SUPARCO tracks 131 potentially dangerous glacial lakes, a list supplied by PDMA KP, GBDMA and WAPDA. Its status updates rest on optical imagery. Its 2 Jul 2026 update was built on a single image from 16 Jun and states: "Persistent cloud cover after 16 June 2026 has limited the availability of cloud-free satellite imagery, making it difficult to accurately assess lake area changes." The update does not mention radar. At that point 40 lakes were unfrozen, up from 24 two weeks earlier, and 13 were above their 2025 maximum area. UNDP estimates that more than 7 million people in GB and KP are exposed to glacial lake outburst floods (GLOFs). Shisper's outburst on 7 May 2022 destroyed the Karakoram Highway bridge at Hassanabad. Sources are in `docs/research_notes/Glacial lake watch/codex_glacial_lakes.md`.

**Pitch.** SARtale uses NISAR's cloud-penetrating radar to keep watching Pakistan's dangerous glacial lakes when optical satellites cannot, and shows disaster teams which lakes changed and need checking next.

**Why it matters for judging.** No past winner has had all three of the following. The research for this design (`docs/reports/Space Apps winners vs SARtale.md`) found they are what separates winners:
- a named user (GBDMA, PDMA KP and the district administrations);
- one plain status per thing that user cares about;
- a question that fits a 30-second demo: "Which lakes grew while the clouds were in?"

The only SAR-challenge finalist with a comparable framing, TengriSpacers (2025), did glacier risk without a user interface. SARtale would be the first entry on record to process real NISAR data for this purpose. It would not be the first SAR glacial-lake project: Ice Exped did Sentinel-1 lake detection at Space Apps 2021.

## 2. Users and decisions

The primary user is the duty analyst at GBDMA or PDMA KP, or a district administration officer. The app supports four decisions:
1. Which lakes need a review now.
2. Where to send a field team or ask for a ground check.
3. Which downstream villages and operators should be briefed.
4. Whether to ask NDMA's authorised contact to request a NISAR Urgent Response acquisition. The app prepares the evidence for that request. It does not request anything itself.

## 3. Goals, non-goals, anti-goals

**Goals**
- A Lake Watch view covering GB and upper KP lakes. Each lake shows:
  - a status: Growing, Stable, Shrinking, Not seen this pass, or Not observable;
  - the date of the latest valid look and the number of looks behind the status;
  - the share of the lake the radar could see;
  - an area trend since 18 Jun 2026.
- A count of valid NISAR looks per lake during the cloudy weeks, set against SUPARCO's single 16 Jun image. This is the headline number of the pitch.
- A one-page lake brief per lake that can be printed or saved as a file: what changed, when, how sure we are, and what lies downstream. It must work offline once loaded.
- An honest limits panel: what NISAR cannot see, and what the app cannot do (see the anti-goals).
- The Peshawar valley flood story, cut to one closing chapter on what happens downstream, reusing the existing change map and the "What NISAR missed" view.

**Non-goals for the hackathon**
- Coverage of Punjab, Sindh or all of Pakistan.
- History before NISAR beyond a baseline outline per lake. No Sentinel-1 time series.
- Deforestation and land-cover change.
- Water level, volume or dam-strength estimates.

**Anti-goals.** Any of these would make the entry fail even if it technically worked:
- Presenting the app as a breach alarm. Shisper has drained in 1–2 days, NISAR repeats every 12 days per track, and products arrive 36–72 hours after acquisition.
- Implying it warns of cloudburst flash floods, such as Buner in 2025.
- Showing "no lake" or "safe" where the radar could not see.
- Inventing lake coordinates, or presenting inventory points as current lake outlines.
- Claiming lives saved or decisions changed without a user saying so.

## 4. Constraints

- The challenge requires NISAR data, an interactive application, and open source. The 2026 Submission and Judging guides publish on 13 Nov. Re-check this design against them.
- Pitch materials are due 17:00 PKT on 15 Nov, the live pitch is at 18:30, and the portal closes at 23:59 PKT.
- The early-work question (the NASA FAQ forbids work before 14 Nov) is still open with the Local Lead. Ask about it at the same meeting as the administration contact.
- Data: NISAR L2 GCOV PROVISIONAL (CRID P05023), mode 4005, HH/HV, 10 m. Calibrated data starts 17 Jun 2026. Pixel spacing depends on the mode, so check it per granule.
- Stack: the existing static app (Vite, TypeScript, MapLibre, uPlot, Vitest) and the Python pipeline (h5py, numpy, rasterio, pytest) in conda env `sartale`. There is no backend.
- Never read or print the Earthdata credentials. Authentication goes through the user's netrc, which requests picks up on its own.
- Deploying the app and making the repo public are the team's actions. No hosted link is created on their behalf.

## 5. Decided parts of the how

**Data access (tested 2 Nov).** Read only a window around each lake from the remote GCOV files, using HTTPS range requests, rather than downloading whole files. Each 7 GB file costs 24–43 MB and about 20 s. The reader must retry on dropped connections; one drop occurred in testing. The tested reader is `docs/research_notes/Glacial lake watch/spike/remote_read.py`.

**Geometry.** Hunza is seen from tracks 055 A, 156 A and 063 D, each repeating every 12 days. The grids from different tracks lined up pixel for pixel in the test. Compare each pass only with earlier passes from the same track, so that a change between viewing directions is never read as a change in the lake.

**Water rule (starting point, needs tuning).** A pixel counts as water when HH and HV are both at least 4 dB below the median of the surrounding window, in both an ascending and a descending view. Shadow and layover depend on the viewing direction; water mostly does not. This cleanly outlined Attabad Lake. A fixed threshold (HH below −18 dB) failed. Two adjustments for dates:
- The persistent-water mask may use a median over the season.
- Lake status must use individual passes, because a season median can erase a lake that fills and drains quickly.

A pixel that is invalid or in shadow in a view means "unknown" for that view, never "dry".

**Pass screening.** Screen out bad passes per track, as was done for the Peshawar stack. In the Hunza test, 7 Jul on track 156 was about 25 dB too bright, and 5 Sep on track 156 was anomalous over the lake.

**Status per lake.** Area comes from the water rule inside a buffer around the lake's reference outline. The status compares the latest valid same-track area with that track's earlier areas, and changes only when the difference exceeds the noise seen between passes. The thresholds are left to the builder, but they must be stated in the app's "How we know" text.

**Lake list.** Use the GBDMA/PDMA list if the administration provides one; SUPARCO publishes only lake ID numbers. Otherwise use public inventory points:
- the HMA GLOF database (Shrestha et al. 2023);
- Passu (moraine-dammed);
- Khurdopin and Ghulkin;
- Shisper, as a story case and to show a lake whose status is unconfirmed.

Attabad stays in as the known-water check. Every lake records the source of its coordinates.

**Validation for the pitch.**
- Attabad, as the known-water control.
- Two or three lakes compared with optical outlines (Sentinel-2) on clear dates close to a NISAR pass, reporting area error.
- Where a SUPARCO lake ID can be matched, a comparison with SUPARCO's 16 Jun and 5 Aug areas.
- State what was not validated: frozen lakes, lakes under 0.05 km², and wind-roughened water.

**Story order.**
1. The cloud gap, using SUPARCO's own words.
2. How radar sees lakes, including the two-view rule.
3. Lake Watch.
4. One lake in depth.
5. What happens downstream: the Peshawar chapter.
6. Limits and the next steps with the administration.

**Delivery.**
- A demo video of about 30 seconds that shows the app first. The current 5-minute explainer becomes optional supporting material.
- A deck of 7 slides or fewer.
- The deployed app and a public repository.

## 6. Questions for the administration meeting (Islamabad)

1. Which lakes do you watch, and can we have their IDs and locations?
2. During the 2026 monsoon, when did cloud stop you seeing a lake you cared about, and what did you do instead?
3. How quickly do you need a lake update to act on it?
4. Who would receive this information, and in what form: a map, a PDF, WhatsApp, a list?
5. What would make you distrust a radar-based status?
6. Who in Pakistan can request NISAR Urgent Response?
7. Can we quote you, or name your office, in the pitch?

Record the answers verbatim. The app and pitch may cite only what was actually said.

## 7. Settled questions

These came from the builder check. Items marked *(our call)* are design decisions the team can overturn.

1. **When to build.** On 1 Nov the team chose to start before the event and accepted the early-work risk. Build now. The 2 Nov spike code and findings may be reused. The team will disclose the pre-event work to the Local Lead and abide by the ruling.
2. **Lake scope.** *(our call)* Aim for 8–12 lakes across GB and upper KP. Hunza comes first, because its coverage is verified. The first build task checks every candidate lake against the NISAR catalogue. A lake with fewer than 3 valid same-track passes since 17 Jun is still listed, with the status "Not enough NISAR looks yet", but has no trend. The pitch claims only the area the lakes actually cover.
3. **Reference outlines.** *(our call)* Use a published polygon where one exists: the Shisper polygons (Lovell and Muhammad), the Glacial Lake Observatory, or GLakeMap-type products. Where a lake has only a point, use a fixed search window around it, and label the lake's number as "water area in the search window", not as the lake's outline. Do not derive a lake's reference outline from the same radar passes used for its status.
4. **How sure the app sounds.** *(our call)* This is an indicative screening tool on provisional data. Every number is shown with its date, the number of looks, and the noise seen between passes. If the Sentinel-2 comparison disagrees badly, report that result in "How we know" and the pitch rather than hiding it.
5. **Existing app.** The static app and the Peshawar stack were working at the last review, 1–2 Nov, on branch `build/sartale`. The builder confirms the tests pass before refactoring, and treats any failures as the first task.
6. **Event-day access.** *(our call)* Fetch and cache the window arrays for every lake ahead of time, and commit them to the repo (about 30 MB per pass in raw form, much less after cropping to the lake buffer). That way the demo does not depend on Earthdata access or reprocessing during the event. Record the CRID of each pass, and refuse to mix CRIDs within a track.

## 8. Left to the builder

- Screen layout, colours and how the existing views are refactored.
- Exact tuning of the water rule and the status thresholds, as long as they are stated in the app.
- Window size per lake, caching, and the file format for each lake's time series.
- Which reference-outline source to use per lake, as long as it is recorded.
- How the one-page brief is produced (print stylesheet or generated file).
