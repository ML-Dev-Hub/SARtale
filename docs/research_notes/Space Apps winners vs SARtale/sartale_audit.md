# SARtale audit, as a Space Apps judge would see it (state on 2 Nov 2026)

How to read these notes. "Cited Findings" holds facts I checked in the repo or measured. "Inferences" holds my judgement. Scores are judgement. Links are repo files, relative to this note. "[audit run]" means my own headless Chrome run on 2 Nov 2026 (1440x900 and 390x844 phone emulation against the dev server, then load timing against `app/dist`, served by a plain local server with no compression; CPU-rendered WebGL). Its output is outside the repo at `C:\Users\kjm70\AppData\Local\Temp\claude\i--SARtale\65f7b82c-aa96-442c-8ee5-dfa7bfeaf486\scratchpad\audit\` (`results.json`, `shots\`). I did not run the test suites, because the brief was read-only.

## What does the app do, screen by screen?

### Takeaway
SARtale is a polished, single-area web story: a start screen, a ten-step guided tour, a free map, seven site cards, a coverage timeline and a long evidence page. It shows and explains one NISAR season over the Peshawar Valley. It gives the viewer no task to perform and nothing to take away.

### Cited Findings
**Identity and data**
- Team SARcastic Scientists (Saeed Ahmad, Shaharyar Sajid), Islamabad Local Event, challenge "Dancing with the SARs" — [README.md:7](../../../README.md).
- Data: NISAR L2 GCOV provisional, stack 084_A_019, CRID P05023, 9 dates from 2 Jul to 18 Oct 2026, window 71.2-73.4 E, 33.8-34.8 N — [manifest.json](../../../app/public/data/manifest.json), [DATA_SOURCES.md:61-76](../../DATA_SOURCES.md).
- Static TypeScript app on MapLibre and uPlot with no backend — [README.md:119](../../../README.md), [DATA_SOURCES.md:412-413](../../DATA_SOURCES.md). Size: 8,510 lines of TS including tests (`wc -l app/src/*.ts`). Test cases written: 288 app, 212 Python (grep count, not run).
- No AI model runs in the pipeline or app; both change layers are plain statistics — [SI_USE.md:17](../../SI_USE.md).

**Start screen**
- Badge "Provisional NISAR data"; title "One monsoon season over the Peshawar Valley, seen by radar from space"; a 45-word lede; a 51-word finding box (HH fell from -7.6 to -16.6 dB as the reservoir rose from 1528.11 to 1550.00 ft, "may indicate the rising water covering the shore"); buttons Start the story, Explore the map, How we know; a mini date line; the seasonal composite as the picture — [story.json:2-11](../../../app/src/content/story.json), [app.ts:76-99](../../../app/src/app.ts), [audit run].

**Guided story (10 steps, 6 parts)** — [story.json:12-161](../../../app/src/content/story.json)
1. Why the valley matters. 2. Meet NISAR (HH and HV as "two ways of listening"). 3. Nine passes play. 4a. Tarbela shore goes dark. 4b. Attock river brightens in autumn, with OPERA agreeing. 4c. HH against HV. 5a. 2 July interference. 5b. 23 July peak fell between passes. 5c. The data gap. 6. "What a planner could check next".
- Each step moves the map; cards run 47 to 84 words plus sources. Leaving keeps your place, and "Resume the story" returns you — [app.ts:794-863](../../../app/src/app.ts).

**The Dance** — [app.ts:101-160, 175-190](../../../app/src/app.ts)
- Full-screen radar frame, Play, a date line spaced by real time with a hatched gap, HH/HV switch, Before and after swipe with a date picker, Seasonal composite (26 Jul, 12 Sep, 18 Oct), Change.
- Change shows one season-wide map coloured by the date of the step, light for brighter and deep for darker, with five date classes and an Unusual dates sub-view — [app.ts:47-54, 439-500](../../../app/src/app.ts), [manifest.json](../../../app/public/data/manifest.json).
- No basemap. Overlays are six hand-typed place labels and seven unlabelled orange site dots — [README.md:58](../../../README.md), [DATA_SOURCES.md:16](../../DATA_SOURCES.md), [audit run, `desk_change.jpg`].

**Site Stories** — [sitesView.ts](../../../app/src/sitesView.ts), [sites.json](../../../app/src/content/sites.json)
- Seven sites: 3 controls, Tarbela shore, plain near Swabi, plain east of Mardan, Indus at Attock. Each card has a curve, Observation, Hypothesis, What would test it, Limits, Change map note, Unusual dates scores, and a values table. Badges: Observed (3), Hypothesis (2), Reference agrees (2).
- Opens with no card chosen, so the first look is a list and an empty pane — [audit run: card hidden on open, desktop and phone].

**What NISAR Missed** — [missedView.ts](../../../app/src/missedView.ts)
- A coverage strip, a legend, a day-range list ("Timeline in words"), the nine dates, and one FFD river paragraph. [audit run, `desk_missed.jpg`]: 402 words.

**How we know** — [evidence.json](../../../app/src/content/evidence.json), [evidenceView.ts](../../../app/src/evidenceView.ts)
- Can and cannot lists, data, method, controls, rule, limits, what would change our mind, check it yourself. 1,832 words on screen — [audit run].

**What does not exist**
- No address sharing or state in the URL, no local save, no print, no data download, no share. A grep of `app/src/*.ts` for `location.hash`, `URLSearchParams`, `localStorage`, `window.print`, `download=` and `.tif` returns nothing outside tests.
- No site can be sampled except the seven; "click-anywhere curves" were dropped by plan — [plan:285](../../SARtale-hackathon-plan.md).
- No outbound link anywhere in the app: a grep for `https?://` or `github` in `app/src/*.ts` and content JSON outside tests returns nothing, so sources are named but not linked.

### Inferences
- A judge will read this as a careful science explainer, closer to a good interactive article than to a tool.
- The evidence-labelled cards and What NISAR Missed are the most distinctive features.
- The hero picture and the Change map are the strongest visuals. The Change map is good enough to be the lead image in a pitch.

### Gaps
- The app's behaviour on a real phone, real GPU and real hosted network was not tested; my run was emulated.
- Test status: not rerun here. The ledger says Task W completed with review, with console capture "self-reported" — [progress.md:116](../../../.superpowers/sdd/2026-11-01-sartale-hackathon/progress.md). I saw no console errors or exceptions on the dev server.

## How does it score against Impact, Creativity, Validity, Relevance and Presentation?

### Takeaway
My scores out of 5, as it stands today: Impact 2, Creativity 3.5, Validity 4, Relevance 4.5, Presentation 2.5 (the app alone would earn 4, but no judge can reach it yet). Validity and Relevance are the assets. Impact and delivery are where it would lose to a project with a clearer user.

### Cited Findings
- The five criteria come from the Seoul event site and are unconfirmed; NASA's Judging and Awards Guide is due 13 Nov, and the README's own table marks every row "Not yet judged" — [README.md:34-44](../../../README.md).

**Impact evidence**
- The only "use" content is one card at step 10: a planner "could" take marked river stretches and shores and check them against gauges and a visit — [story.json:150-160](../../../app/src/content/story.json).
- The team has spoken to no planner or NGO, and the plan says not to claim validation — [plan:105](../../SARtale-hackathon-plan.md). No stakeholder appears in the repo.
- The plan's ending, one decision tied to a crossing, was not built; the plan's "printable field-check list" does not exist — [plan:38, 114](../../SARtale-hackathon-plan.md).
- story.json has no mention of people, villages, farmers, roads, bridges or hospitals (grep returned nothing).
- The hero finding's second half comes from gauge bulletins: the reservoir level was already known from FFD — [story.json:5](../../../app/src/content/story.json).

**Creativity evidence**
- "The Dance" framing, What NISAR Missed as a first-class view, a date-coloured single-image change map, and a time-true date line — [README.md:24-30](../../../README.md).
- The step layer was a project-specific response to a real failure of the z-score approach at the Tarbela shore — [DATA_SOURCES.md:212, 363](../../DATA_SOURCES.md).

**Validity evidence**
- Urban and water controls, shuffled-date tests at pixel and scene level, an OPERA comparison, FFD bulletins, a two-frequency check on 2 July, sensitivity tables, and a published list of what would change their mind — [DATA_SOURCES.md:96-386](../../DATA_SOURCES.md), [evidence.json:119-130](../../../app/src/content/evidence.json).
- A test blocks banned claims such as "damage" and "detected flood" in visible text, and tests tie quoted numbers to the data — [content.ts:5-18](../../../app/src/content.ts), [README.md:90](../../../README.md).
- Counterweights: not blind, one rule changed after seeing sites — [DATA_SOURCES.md:220](../../DATA_SOURCES.md); no person has checked the site choices or cards — [SI_USE.md:28](../../SI_USE.md).

**Relevance evidence**
- The statement asks for an interactive app using NISAR to track surface change, supplemental data, hypothesised drivers, polarization comparison and future applications — [plan:32, 34-44](../../SARtale-hackathon-plan.md).
- SARtale does the first four. Polarization is compared at one place in the story, plus per-site curves — [story.json:89-102](../../../app/src/content/story.json).
- Future applications are thin: step 10's "Next" lists data to add, where the plan promised a section on what continuous 12-day coverage could do — [story.json:156](../../../app/src/content/story.json), [plan:44](../../SARtale-hackathon-plan.md).

**Presentation evidence**
- Desktop app is clean: no console errors, no horizontal overflow on any view at 1440 or 390 — [audit run].
- No deployed link, no public repo, no deck, no hosted video (see the delivery question).

### Inferences
- Impact 2: the story ends on advice to check things, with no named user and no decision. A judge will ask "who does what differently on Monday?" and the app has no answer.
- Creativity 3.5: original framing and honest storytelling, but the interaction pattern (slider, swipe, cards) is standard for this genre.
- Validity 4: unusually rigorous for a weekend project, and open about its limits. Docked for the unreviewed AI drafting, the small reference set and the claim issues listed under science.
- Relevance 4.5: close to a direct answer to the statement. Docked for future applications and for not using human drivers. Tarbela is an operated reservoir, and the story never says so.
- Presentation 2.5 today. The risk of over-rigour is real: the honesty that earns Validity points also reads as hedging in the first minute.
- Fit with the 2025 award categories named in the plan: Best Use of Data and Best Use of Storytelling are plausible. Local Impact is weak until a local user or decision exists.

### Gaps
- Actual 2026 criteria, weights and video rules are unknown until 13 Nov — [plan:64-66](../../SARtale-hackathon-plan.md).
- How past winners score on these criteria belongs to the other research notes.

## What is weak or missing for a first-time user?

### Takeaway
The first 10 seconds say what it is and look striking, but not why it matters to anyone. Jargon starts in the first finding. Phone layout is the worst weakness: in story mode the panels cover almost all of the map. The change layer is explained honestly but at length.

### Cited Findings
**First 10 seconds**
- At 1440x900 everything fits with no scrolling; at 10 Mbps the title appeared at about 0.6 s and the hero picture at about 1.1 s — [audit run].
- The word "HH", the unit "dB" and "1528.11 ft" appear in the headline finding before HH or dB are explained; HH and HV are first explained at story step 2, and dB never is in the story — [story.json:5, 33-36](../../../app/src/content/story.json).

**Who the user is, and what action it enables**
- The plan's primary audience is "local judges, then global judges and the public", and planners are secondary and unconsulted — [plan:103-105](../../SARtale-hackathon-plan.md).
- Nothing on the start screen names a user. No action is possible beyond viewing (see the first question).

**Free exploring**
- "Explore the map" opens on the first date, 2 July HH, a flagged date — `state.i` starts at 0, [app.ts:309, 405](../../../app/src/app.ts).
- Site dots are identical for controls and changing sites and have no labels until opened — [audit run, `desk_change.jpg`].
- The chart's date axis reads 7/2, 8/16 while the rest of the app reads 2 Jul — [audit run, `desk_site_card.jpg`].
- No basemap or rivers. Optional road and river overlays are missing, so the built app logs two 404s — [audit run: `roads.geojson`, `rivers.geojson`].

**Mobile (390x844, emulated)**
- Story mode: the card is fixed at 295 px with 189 px of readable text area, while step text needs 250 to 513 px, so every one of the 10 steps must be scrolled inside the card — [audit run].
- At steps with Change on, the change key and the story card together leave only a thin strip of map visible, so the place being discussed cannot be seen — [audit run, `phone_story_04.jpg`]. In free mode the Change panel covers the whole map — [audit run, `phone_change.jpg`].
- Two rulings accepted hiding some controls in the story on phones — [progress.md:113-114](../../../.superpowers/sdd/2026-11-01-sartale-hackathon/progress.md).
- The hero finding sits below the buttons and below the fold; only one line shows above the fixed footer — [audit run: finding at y 691-927 of 844, `phone_01_hero.jpg`].

**Loading**
- Landing automatically fetches all nine HH frames with no user action, about 15 to 17 MB of a total about 17 to 18 MB — [app.ts:881](../../../app/src/app.ts), [audit run].
- At 10 Mbps: first map frame about 3.7 s, all nine HH about 16 s. At a throttled 1.6 Mbps phone connection: hero picture about 5 s, first frame about 21 s, nine HH about 96 s — [audit run]. These are approximate. My server did not compress the JS (about 1.4 MB), but WebP frames dominate.
- Good: the map code loads after first paint, the map says what it is waiting for, and Data Saver stops preloading — [app.ts:597, 619-627](../../../app/src/app.ts).

**Accessibility**
- Present: skip link, `aria-live` view name, focus styles, reduced-motion rule, alt text, a labelled slider, keyboard swipe, a text timeline, values tables behind charts — [app.ts:58-64](../../../app/src/app.ts), [styles.css:33, 834](../../../app/src/styles.css). No unnamed controls on any screen — [audit run].
- Site dots are 26x26 px. The phone view has text at 11 to 13 px on most screens — [audit run: font-size counts].
- The five date hues depend on colour. My rough colour-vision simulation (Lab distance, approximate) gives the 24 Sep and 6 Oct light tints a distance of about 7 and the 19 Aug and 31 Aug deep shades about 6 under deuteranopia, against 26 and 45 at the closest pairs for normal vision — calculated from `change.step.classes` in [manifest.json](../../../app/public/data/manifest.json).
- I did not measure text contrast or run a screen reader.

**Jargon**
- Visible terms include HH, HV, dB, backscatter, polarization, composite, flagged date, stability, IoU, two-sample t statistic, modified z-score ("Unusual dates score"), RTC gamma-0 — [evidence.json:84, 92](../../../app/src/content/evidence.json), [app.ts:215](../../../app/src/app.ts), [sitesView.ts:209](../../../app/src/sitesView.ts).
- Language is English only; Urdu labels were cut by plan — [plan:252, 103](../../SARtale-hackathon-plan.md).

**How the change layer is explained**
- The map key has about 90 words of caption and limit, then nested folds; at 900 px height the panel clips its last lines and needs scrolling — [app.ts:47-54, 133-140](../../../app/src/app.ts), [audit run, `desk_change.jpg`].
- The caption's core is clear: "Each coloured patch stepped between two passes, and its colour is the date of the first pass after the step."
- "The date slider changes the radar underneath, not these colours" is in the fold — [app.ts:483](../../../app/src/app.ts).
- The largest visible colour class, up on 19 Aug across the plains, has no explanation. The limit says "no known cause".

### Inferences
- The start screen tells a judge the what but not the so-what. A single sentence of stakes would do more than the finding's dB numbers.
- Opening free mode on the interference date is an own goal, even though the flag appears. Changing the default date is a tiny fix.
- Mobile will hurt if a judge opens a link on a phone during live judging, which seems likely.
- Fetching 15 MB unprompted on the landing page is poor for a judge on event Wi-Fi or mobile data. Loading a few frames first would be kinder.
- "Plain language" is true of the hero sentence structure, less so of its content.
- The Change map's caveats appear before a user has understood what they are looking at; one worked example ("this orange patch means...") would teach it faster than the limit text.

### Gaps
- The plan's one-minute comprehension test with someone outside the team has no recorded result — [plan:340](../../SARtale-hackathon-plan.md). No user test of any kind is on record.
- WCAG contrast, screen-reader pass and offline behaviour are untested; the README itself says offline is untested — [README.md:58](../../../README.md).

## What is weak in the science?

### Takeaway
The method is sound for a prototype and its limits are unusually well disclosed. The real weaknesses are: one track, two flagged dates out of nine, flags on plain ground with no cause, two sites with outside references, no reference on the August finding except gauge levels, and no optical, rain, elevation or land-cover check. Task 11 was not started. Nothing has been read by a human against the data.

### Cited Findings
**One track and scene**
- Only stack 084_A_019 is used. Track 012 A 019 covers 99% of the pilot, 5 days offset, with 9 files, and was left out. Descending 164 D 071 covers 100% — [plan:124-128, 253](../../SARtale-hackathon-plan.md).
- 9 dates, of which 2 Jul is left out of change analysis, and 14 Jul is a forecast-orbit file that still reads low on plain ground — [DATA_SOURCES.md:214, 282](../../DATA_SOURCES.md).
- No pre-monsoon baseline: the stack starts 2 Jul — [evidence.json:127](../../../app/src/content/evidence.json).
- All data are Provisional, not validated, and NASA expects reprocessing — [DATA_SOURCES.md:74](../../DATA_SOURCES.md).

**Flagged-pixel share**
- 1.39% of 2,814,517 scored 90 m pixels, which is 39,096 pixels — [DATA_SOURCES.md:261, 291](../../DATA_SOURCES.md). That is about 317 km2 (my arithmetic).
- Of flagged pixels, 31% lie in cells not drawn and a further 12% are drawn in another class, so 43% are not drawn in their own class. The check script was not kept — [DATA_SOURCES.md:291](../../DATA_SOURCES.md).
- The map draws 2.7% of cells against 1.39% of pixels, so it looks about twice as extensive as measured — [DATA_SOURCES.md:287](../../DATA_SOURCES.md).
- About 80% of flagged pixels step up, and 39% of all flags are "up on 19 Aug" — [DATA_SOURCES.md:261, 263](../../DATA_SOURCES.md).

**False positives: what is known**
- Per-pixel shuffles flag 0.253% of the window and 1.006% of the plain box. Scene-wide shuffles (200 orders) give the window a median of 0.15%, 90th percentile 0.72%, maximum 1.26%; the plain box median 0.38%, maximum 6.9%. Real: 1.39% and 8.5% — [DATA_SOURCES.md:237, 241](../../DATA_SOURCES.md).
- Controls: 0 to 1%. But the three controls were used to set the limit, and Hazro was picked as the steadier site after a first control failed at 2.13 dB — [DATA_SOURCES.md:136, 247-249, 292](../../DATA_SOURCES.md).
- The "five fresh cities" check is reported, not reproducible: cities unnamed, script not in repo — [DATA_SOURCES.md:292](../../DATA_SOURCES.md). The ledger records it as part of a code review — [progress.md:104](../../../.superpowers/sdd/2026-11-01-sartale-hackathon/progress.md).
- The app calls this "An independent reviewer" and "the independent check" — [evidence.json:82](../../../app/src/content/evidence.json), [sitesView.ts:249](../../../app/src/sitesView.ts), [app.ts:493](../../../app/src/app.ts). SI_USE lists "code review" among Claude Code's roles and no outside person — [SI_USE.md:16](../../SI_USE.md).
- Plain sites flag at 35% and 68% within 450 m with no cause — [DATA_SOURCES.md:254-255](../../DATA_SOURCES.md).
- Robustness: only 24% of flagged pixels survive every single-date drop; 46 to 51% survive dropping a July date; with 1 dB added to 14 Jul, 73% stay flagged — [DATA_SOURCES.md:281-282](../../DATA_SOURCES.md).
- 6 Oct has an unexplained brightening; 33% of flags in that patch are dated to it, and only 44% survive dropping it — [DATA_SOURCES.md:284](../../DATA_SOURCES.md). A line fits better than a step at 15% of flagged pixels, 42% at Attock — [DATA_SOURCES.md:285](../../DATA_SOURCES.md).

**Validation against references**
- OPERA DSWx-S1 has no tile between 28 Jun and 15 Sep, so nothing checks the monsoon peak or the August step — [DATA_SOURCES.md:140](../../DATA_SOURCES.md).
- Water mask against OPERA: recall 0.78 to 0.90, precision 0.45 to 0.69, IoU 0.43 to 0.60 over the window, about 0.90 to 0.92 around Tarbela; whole-window agreement is near the all-dry baseline and on 6 Oct is below it — [DATA_SOURCES.md:142-152](../../DATA_SOURCES.md). This tests the water mask, which is not the step map.
- Flagged water-like pixels against OPERA changes: on every row most flags are not DSWx changes (at most 44.5% are) and most DSWx changes are not flagged (at most 34.8% are) — [DATA_SOURCES.md:371-382](../../DATA_SOURCES.md).
- Only 2 of 7 sites carry "Reference agrees". The bulletins are gauge values, and neither reference gives the surface on a NISAR date — [DATA_SOURCES.md:162](../../DATA_SOURCES.md).
- The shore step rests on two earlier dates, one flagged; its HH remains 5 dB below July on 18 Oct with no explanation, though the reservoir was then lower than on 26 Jul — [sites.json:119-120](../../../app/src/content/sites.json), [DATA_SOURCES.md:194-202](../../DATA_SOURCES.md).
- Not used or downloaded: HLS, DSWx-HLS, GPM IMERG, soil moisture, OpenStreetMap, UNOSAT, WorldPop, HydroSHEDS — [DATA_SOURCES.md:388-402](../../DATA_SOURCES.md). No rain record was compared, and land cover is unchecked — [evidence.json:108](../../../app/src/content/evidence.json).
- No elevation test of the shore: the card calls a height survey future work — [sites.json:118](../../../app/src/content/sites.json).
- Plan checks with no result on record: geolocation by visual offset against optical imagery, vegetation check, clean rerun from manifest — [plan:335-339](../../SARtale-hackathon-plan.md).

**Unfinished items**
- Task 11 (remaining dates, then road closures): the dates were added by Task R, but Lifelines was deferred entirely. `network.py` and `lifelines.ts` do not exist, `networkx` and `osmnx` are listed but not imported, and the only overlay is `places.geojson` — [progress.md:59](../../../.superpowers/sdd/2026-11-01-sartale-hackathon/progress.md), [plan file:699-748](../../superpowers/plans/2026-11-01-sartale-hackathon.md), [DATA_SOURCES.md:434-435](../../DATA_SOURCES.md).
- Task 12 (clean rerun, test run, checklist, submission) is deferred; all submission checklist boxes are unticked — [progress.md:60](../../../.superpowers/sdd/2026-11-01-sartale-hackathon/progress.md), [plan:348-358](../../SARtale-hackathon-plan.md).
- SI_USE says a team member must still read each card against its curve and open the 2 July evidence; it records that nobody has yet — [SI_USE.md:28](../../SI_USE.md).
- Open minor items include "card step uses averaged curve; shuffle shows order not cause" — [progress.md:107](../../../.superpowers/sdd/2026-11-01-sartale-hackathon/progress.md).
- Data and licence wording is still "to confirm" for NISAR, OPERA and FFD reuse, and the logo's origin is unknown — [DATA_SOURCES.md:440-445](../../DATA_SOURCES.md), [SI_USE.md:22-24](../../SI_USE.md).

### Inferences
- The strongest honest claim is narrow: two sites where radar steps match outside evidence, plus quiet controls. The map itself has no measured precision. The shuffles give a chance floor of about 11 to 18% of the 1.39% (0.15 and 0.25 over 1.39), and the worst scene order reaches 91%. They test whether date order matters, not whether a flagged pixel is a real event of interest.
- A real order that barely beats the highest of 200 orders (1.39 against 1.26) is less impressive than "more than any of the 200" sounds. Any seasonal trend would beat shuffles.
- "One result does not depend on that choice" ([evidence.json:96](../../../app/src/content/evidence.json)) seems too strong: the scene shuffle is run at limits chosen with the sites in view.
- "Independent reviewer" is the single riskiest phrase in the app. If that reviewer was an AI review agent in the same workflow, which the ledger suggests, a judge who asks will find it hollow. It should say who ran it, or the check should be rerun with named cities and a script in the repo. Five cities also test only the easy case.
- The biggest colour class on the map is unexplained, and a scientist judge will look there first. HLS NDVI and IMERG rain for Swabi and Mardan would turn the weakest area into a finding, and a DEM check of the shore against 1528 to 1550 ft would be a cheap, independent test of the headline claim.
- Adding track 012 would halve the revisit in the season and test any step independently, which the single-track design cannot do. It does cost about 66 GB and new processing.
- Road closures are not needed for scientific credit, but they were the plan's only route to Impact.

### Gaps
- I did not recompute any science numbers; I checked that the app and docs agree with each other, and spot-checked quoted figures against DATA_SOURCES.md. The review ledger says numbers were reproduced — [progress.md:104](../../../.superpowers/sdd/2026-11-01-sartale-hackathon/progress.md).
- Who the "reviewer" was is not stated in any file I read. The evidence for an AI reviewer is indirect.
- PDMA situation reports have not been reviewed, so a local event on a NISAR date cannot be ruled out — [plan:408](../../SARtale-hackathon-plan.md).

## What is weak in delivery?

### Takeaway
As of 2 Nov nothing a judge could open exists. No deployed app, no public repo, no hosted video, no deck. The video is well made but is a 5-minute methods talk, and the early-work rule is the largest open risk to the whole entry.

### Cited Findings
**Demo video**
- `video/out/SARtale-explainer.mp4`, 29 MB, about 5:06 by the subtitle end time (00:05:05) and durations totalling 306 s; burned-in subtitles and an SRT exist — [durations.json](../../../video/out/durations.json), [build.py](../../../video/build.py). `ffprobe` was not installed, so I did not probe the file itself.
- Structure: 3:51 of Manim maths and method first, then 0:53 of app capture (17%), then 0:22 of close — [durations.json](../../../video/out/durations.json), [narration.json](../../../video/narration.json). The app appears only at 3:51.
- Narration is 748 words. It has no occurrence of OPERA, Flood Forecasting, planner, Attock, Mardan, Swabi, road or bridge, and "reservoir" once. It presents the shore step without saying the reservoir rose, so the headline finding has no explanation in the video — [narration.json:8-69](../../../video/narration.json).
- The close says "A step is not a cause... we do not yet know why" and states no benefit — [narration.json:68](../../../video/narration.json).
- Voice is a synthetic named voice ("Alice", with a voice ID) — [narration.json:2-3](../../../video/narration.json). SI_USE lists no narration tool, and it says any used for narration must be added — [SI_USE.md:33](../../SI_USE.md).
- Hosted nowhere I can find: `video/` is untracked, `video/out/` is in an uncommitted `.gitignore` change, and no YouTube, Vimeo or Drive link appears in README or docs (git status; grep).

**App deployment**
- Not deployed. No workflow, Netlify, Vercel or Docker config in git; `https://saeedahmadicp.github.io/SARtale/` redirects to `saeedahmad.me/SARtale/`, which returned 404. The ledger leaves deployment to the team — [progress.md:31, 65](../../../.superpowers/sdd/2026-11-01-sartale-hackathon/progress.md).
- It is ready to host: static, relative paths, 36 MB `dist` built at 08:59, one minute after the last source change — [README.md:58](../../../README.md).

**Pitch deck**
- None. No `.pptx`, `.key`, `.pdf`, deck or slides file is tracked, and the only mentions are in plans. A deck and live pitch are required locally, by 17:00 and 18:30 PKT on 15 Nov — [plan:53, 74](../../SARtale-hackathon-plan.md).

**Repository**
- Remote is `github.com/saeedahmadicp/SARtale`. Anonymous fetch of the page returned 404, while `git ls-remote` works with local credentials, so it is private. `gh` is not logged in, so I could not read its visibility directly.
- Only `build/sartale` is on the remote, at d2bacd2; local HEAD 84d3c2f is one commit ahead and unpushed (git status, `git ls-remote`).
- **`build/sartale` is not merged.** Local `main` has 1 commit (`f08f5a7`, the plans), `build/sartale` is 60 ahead, and `main` is not on the remote.
- README has no screenshot, demo link or video link, and it says "downloadable GeoTIFF" though no download exists and `*.tif` and `data/` are git-ignored — [README.md:14](../../../README.md), [.gitignore](../../../.gitignore).
- "Check it yourself" sends readers to repo paths, which are unreachable while it is private — [evidence.json:135](../../../app/src/content/evidence.json).

**Rules and eligibility**
- FAQ: "Teams are not allowed to begin working on the challenges prior to the hackathon." The hackathon is 14-15 Nov — [plan:19, 52](../../SARtale-hackathon-plan.md).
- All 61 commits are dated 1 and 2 Nov 2026 (`git log`); 18 and 43 respectively. The team accepted the risk, and the Local Lead's reply is not yet recorded — [progress.md:3](../../../.superpowers/sdd/2026-11-01-sartale-hackathon/progress.md), [SI_USE.md:7-8, 34](../../SI_USE.md).
- The plan says the Local Lead's objection "may mean discarding this work" and rates the severity as Severe — [plan:97, 364](../../SARtale-hackathon-plan.md).
- SI_USE still lacks the logo statement and the Local Lead's answer — [SI_USE.md:32-34](../../SI_USE.md).
- Submission format, video length and judging guide arrive 13 Nov — [plan:64-66](../../SARtale-hackathon-plan.md).

### Inferences
- Deployment, merge and publication are hours of work, and the plan says the team does them. They are not the real delivery risk.
- The real risks are the eligibility question and the video's fit. If the 2026 demo format is short, the 5:06 cut will not fit, and a shorter one built around the app, the finding and the stakes will be needed.
- For a general judge, 3:51 of equations before seeing the product is the wrong order. The maths would work as an appendix for technical judges.
- A public git history dated before 14 Nov makes the early start easy for anyone to see. Disclosure before submission is safer than discovery.

### Gaps
- GitHub visibility is inferred, not read from the API.
- The Space Apps project page state could not be checked. The plan says the team page used "early-warning tool" wording that must change — [plan:373](../../SARtale-hackathon-plan.md).
- The video was not watched; this is based on the script, timings and build code.
- Which narration tool was used is not recorded in the repo.

## Which items are verified facts, and which are judgement?

### Takeaway
Everything under "Cited Findings" in these notes is a file, a command result or a measurement I took. Everything under "Inferences", and all scores, is judgement. The list below gives the items a report writer is most likely to blur.

### Cited Findings
**Verified in code, git or my run**
- Default free-map date is 2 July — [app.ts:309](../../../app/src/app.ts).
- Landing preloads all HH frames, and my measured load figures — [app.ts:881](../../../app/src/app.ts), [audit run].
- No download, print, share, URL state or outbound link in the app (grep).
- Phone story card text overflow on all ten steps — [audit run].
- `build/sartale` not merged, one commit unpushed, `video/` untracked, no deck file, no deployment config (git).
- Video timing split and narration word counts — [durations.json](../../../video/out/durations.json), [narration.json](../../../video/narration.json).
- "Independent reviewer" wording in three places — [evidence.json:82](../../../app/src/content/evidence.json), [sitesView.ts:249](../../../app/src/sitesView.ts), [app.ts:493](../../../app/src/app.ts).

**Taken from project docs, not recomputed by me**
- Every science number in the science section — [DATA_SOURCES.md](../../DATA_SOURCES.md).
- Rule quotes and deadlines — [plan](../../SARtale-hackathon-plan.md). I did not reopen the official pages.

**Indirect**
- Repo is private (anonymous 404, authenticated `ls-remote`).
- Colour-vision distances are my rough calculation, not a tested result.

### Inferences
Judgement only, and open to challenge:
- All five scores.
- That the reviewer was an AI agent.
- That judges will open the link on phones.
- That the video order is wrong for judges.
- That Local Impact is out of reach today.
- That Impact is the main gap to close and that track 012, HLS, IMERG and a DEM are the best science additions.

### Gaps
- Comparison with past winners is not made here; it is for the report writer, using the other notes.
