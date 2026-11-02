# Independent review: Space Apps global winners versus SARtale

Prepared 2 November 2026. Scope: the current repository in `I:/SARtale`, judged as a prospective two-person NASA Space Apps entry.

## Verdict

**SARtale has a credible technical foundation and a much less convincing reason to win.** It has real-data provenance, an unusually candid account of uncertainty, and an existing guided story. It currently asks judges to admire careful radar exploration more than it gives a particular audience something memorable to discover or accomplish. More layers will not fix that.

My recommendation is to position it as an interactive investigation: **learn to distinguish a supported surface-change hypothesis, a suspicious radar signal, and an event the satellite could not observe.** Make the visitor reach a defensible conclusion using the evidence. That is a plausible storytelling/data-accessibility entry. Calling the present build a disaster decision tool would create expectations its observations and validation cannot meet.

There is also a potentially overriding eligibility issue: the repository explicitly records substantial development before the hackathon. Resolve that through the organizers before treating any implementation recommendation below as an authorized competition plan. This review does not determine eligibility.

## Evidence boundaries and independence

- **[WEB] Verified from web:** the cited page or search-indexed extract was retrieved during this review. A team or sponsor describing a capability establishes that they reported it, not that the capability works. NASA winner announcements establish awards and NASA's descriptions, not independently audited performance.
- **[REPO] Verified from repository:** source text, implementation, manifests, and file inventory inspected here. Numerical scientific results quoted from project documentation remain **project-reported results**, not results independently recomputed by this review.
- **[INFERENCE]** My assessment of likely judging consequences, product quality, prioritization, and effort. These are not statements from judges or measured probabilities of winning.
- **[MEMORY]** No project names, awards, competition rules, or project-specific capabilities in this report rely on memory. Unverified details are omitted.

I worked alone, without subagents. I began with `README.md` and `app/src/`. I read no other files under `docs/research_notes`. Supporting project material inspected included `app/public/data/manifest.json`, the overlay/frame inventory, `processing/sites_in.json`, `docs/DATA_SOURCES.md`, and `docs/SI_USE.md`. I did not follow the app's references to another reviewer's research. Its embedded claim of an independent check is assessed only as a claim the app presents.

This is a source-informed product and scientific-communication review, **not a live browser usability test or a rerun of the radar analysis**. Screen names below refer to their implemented content and code; I do not claim to have observed rendering defects. I did not run builds, tests, downloads, or pipelines, because those can write artifacts outside the one permitted report. I did not read credentials, including `~/.netrc`.

### Web access and coverage

I started at the requested [2025 global-winners page](https://www.spaceappschallenge.org/2025/awards/global-winners/). It repeatedly returned HTTP 502. The analogous 2023 page also initially failed; the 2024 URL was inaccessible through the tool. Several challenge and project-tab pages likewise failed. Search-indexed official pages and NASA's three official announcements were accessible, allowing verification of **all ten categories in each year**.

Coverage is therefore a complete award-roster/official-summary comparison, with selected deeper project evidence, rather than a claim to have played all thirty demos. The CATALYST case-study PDF exceeded the web tool's size limit; only its indexed extract was available. I do not use unofficial winner compilations or other researchers' strategy analyses as evidence.

## 1. What won: all categories, 2023–2025

The entries below use the **winning team names**, adding a product title only when the cited source supplies one. Descriptions are intentionally short. “Best Storytelling” and “Best Use of Storytelling” are treated as the corresponding category across years.

### 2023 — [WEB]

All rows are supported by [NASA's 2023 winners announcement, published 26 January 2024](https://science.nasa.gov/directorates/smd/2023-nasa-international-space-apps-challenge-announces-10-global-winners/).

| Category | Winning team | NASA-described work, condensed |
|---|---|---|
| Best Use of Science | LunarTech Ensemble | Apollo moonquake visualization and an immersive game. |
| Best Use of Data | Storm Prophet | LSTM-based geomagnetic storm prediction. |
| Best Use of Technology | Spacebee | Apollo seismic locations, classifications, dates, and plots. |
| Galactic Impact | Greetings from Earth!! | Ocean-data exploration explaining planetary ecological roles. |
| Best Mission Concept | ASTROGENESIS | Personalized itineraries for exploring celestial destinations. |
| Most Inspirational | Space Quest Maidens - Donzelas da Missao Espacial | Children's eclipse education through interactive learning. |
| Best Storytelling | TeamVoyagers | Water-cycle and climate storytelling through a game. |
| Global Connection | Arcobaleno | Image sonification for people with visual impairments. |
| Art & Technology | Oogway Comics | A scientifically informed habitable-exoplanet comic. |
| Local Impact | $quality_over_quantity | Biodiversity exploration supporting conservation prioritization. |

### 2024 — [WEB]

All rows are supported by [NASA's 2024 winners announcement, published 16 January 2025](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-international-space-apps-challenge-announces-2024-global-winners/).

| Category | Winning team | NASA-described work, condensed |
|---|---|---|
| Best Use of Science | WMPGang | SkyShield: space-hazard risk-zone visualization. |
| Best Use of Data | GaamaRamma | Waterwise: agricultural water-management support. |
| Best Use of Technology | 42 QuakeHeroes | Neural-network identification of seismic events. |
| Galactic Impact | NVS-knot | Planting-risk assessment using hydrological data. |
| Best Mission Concept | AsturExplorers | Landsat Connect: reflectance access and overpass notifications. |
| Most Inspirational | Innovisionaries | Eco-Metropolis: sustainability through city-building choices. |
| Best Storytelling | TerraTales | Climate stories across Egypt, Brazil, and Germany. |
| Global Connection | Asteroid Destroyer | Exoplanet mapping with data processing and machine learning. |
| Art & Technology | Connected Earth Museum | Interactive climate-data galleries in a virtual museum. |
| Local Impact | Team I.O. | G.R.O.W.: accessible communication of environmental GIS information. |

### 2025 — [WEB]

All rows are supported by [NASA's 2025 winners announcement, published 18 December 2025](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/).

| Category | Winning team | NASA-described work, condensed |
|---|---|---|
| Best Use of Science | SpaceGenes+ | Molecular astronaut-health research dashboard. |
| Best Use of Data | Resonant Exoplanets | Automated exoplanet and possible-biosignature analysis. |
| Best Use of Technology | Twisters | SkySense: activity-specific weather assessments. |
| Galactic Impact | Astro Sweepers: We Catch What Space Leaves Behind | Orbital-debris compliance and risk platform. |
| Best Mission Concept | PureFlow | Space-habitat design and threat testing. |
| Most Inspirational | Photonics Odyssey | Satellite broadband infrastructure concept for India. |
| Best Use of Storytelling | HerCode Space | A Solar Tale: illustrated heliophysics for children. |
| Global Connection | Gaia+LEO | Joint orbital/terrestrial computing-network optimization. |
| Art & Technology | Zumorroda-X | Farming-adaptation learning through mini games. |
| Local Impact | QUEÑARIS | Queñua restoration and water-security support. |

### A deeper example: what “useful” actually means

[WEB, team-reported] NVS-knot's project page defines two concrete farmer questions: whether moisture supports germination and whether machinery can enter a field. It describes daily assessments for 100 m field portions, at least two weeks ahead, and a second-opinion view showing moisture and uncertainty. It also reports farmer feedback and earlier pilots. These are stronger evidence of a defined workflow than a generic promise to help agriculture; they are not independently verified forecast-skill measurements. [NVS-knot project submission](https://www.spaceappschallenge.org/nasa-space-apps-2024/find-a-team/nvs-knot/?tab=project).

[INFERENCE] SARtale does not need that infrastructure or history. It needs the same specificity about what a visitor can now answer. A bounded educational outcome is entirely legitimate; it does not have to invent an operational risk service.

### SAR comparators and the 2025 challenge

[WEB] The 2025 challenge asked participants to use multi-frequency **or** multi-polarization SAR for a chosen area and develop hypotheses about physical drivers. That wording is reproduced on the official [GaiaSAR team page](https://www.spaceappschallenge.org/2025/find-a-team/gaiasar/). The [official challenge introduction](https://www.youtube.com/watch?v=iQ__KsJRLHo) also verifies the challenge title and existence; I did not obtain a reliable full video transcript.

| Entry | What is actually verified | What SARtale should learn — [INFERENCE] |
|---|---|---|
| **FarmHubGlobal**, Toulouse | The official page marks it **Global Nominee and Honorable Mention**. Its description proposes existing SAR data, site-specific decision support, and tutorials for farmers with limited access. Full project-tab retrieval failed; implementation and performance were not verified. [Official team page](https://www.spaceappschallenge.org/2025/find-a-team/farmhubglobal/). | An accessible SAR application with a local-benefit story is already a credible competition baseline. Those qualities alone do not guarantee a global award. |
| **Cea-SAR — The Shannon Pulse**, Athlone | The local organizer reports **first place and global nomination**, Sentinel-1 analysis over 2015–2024, and proposed ground sensors/forecasting. It also discloses generative sample data in the demo. Treat the forecasting and sensor system as proposals, not proven deployment. [Organizer's account](https://hackathlone.com/blogs/inside-the-2025-podium). | Local geography, a repeated phenomenon, and a route to checking satellite evidence make a stronger story than an unbounded map. SARtale can differentiate with real displayed measurements and explicit refusals to overinterpret them. |
| **Frank Tan and Isaac Huang's ship-detection project**, Waterloo; project name not verified | The sponsor reports a **PCI Geomatics Young Scholar Award** for AI/deep-learning ship detection in SAR under this challenge. This is not a NASA global award. Only the PDF's indexed extract was accessible. [Sponsor case study](https://catalyst.earth/wp-content/uploads/2026/03/NASA-Hackathon-Case-Study-v2-23.02.2026.pdf). | A sharply bounded interpretation task can be compelling. Do not copy the AI label; copy the bounded question. |
| **UpIT**, Ciudad de la Costa | Official page verifies the SAR challenge, **Global Nominee** status, and a two-developer team. No project implementation details were accessible. [Official team page](https://www.spaceappschallenge.org/2025/find-a-team/upit/). | Two people can reach global judging. The page does not support claims about what made its solution work or why it did not receive a global award. |

[WEB + bounded inference] None of the ten 2025 global winners in NASA's announcement is listed under this SAR challenge. This establishes the award outcome, **not** that SAR was disfavored, that these entries were weak, or that another challenge would be easier.

[WEB] The 2026 challenge summary reproduced on an official team page calls for an interactive NISAR application tracking and visualizing surface change. I verified that summary, not the full challenge's detailed requirements, because the main challenge URL failed. [Official platform's “Dancing with the SARs” summary](https://www.spaceappschallenge.org/2026/find-a-team/al-1/).

## 2. What separates winning entries from good entries that do not win?

**The evidence supports a useful standard, not a causal formula.** We have official descriptions of winners and a small selection of recognized SAR entrants, not a matched sample with judge scores. It would be dishonest to say that all winners did user testing, all non-winners lacked originality, or any particular team lost for a known reason.

[WEB] Award definitions explicitly distinguish scientific validity, distinctive data access/application, technical innovation, impact, plausible design, inspiration, storytelling, global connection, combined art/technology, and local benefit. Global nominees advance through expert judging and then executive selection of ten winners. [Official 2025 awards definitions and process](https://www.spaceappschallenge.org/2025/awards/). These are award descriptions, not verified 2026 criterion weights. `README.md` itself says the planned judging criteria still need confirmation.

The following are **[INFERENCE]**, grounded in the winner inventory and the NVS-knot example:

| A good entry often provides | A stronger contender makes unmistakable |
|---|---|
| A working visualization of NASA data | A precise question the visualization helps someone answer. |
| A plausible social benefit | A named audience, a believable setting, and an observable outcome. |
| Several competent features | One interaction a judge can describe after the demo closes. |
| A scientifically relevant dataset | A visible chain from observation to interpretation, with a way to challenge it. |
| An attractive narrative wrapper | A narrative structure that changes what the viewer understands or chooses. |
| A technically sophisticated method | A reason the sophistication improves the answer. |
| Broad ambition | A complete, convincing slice of that ambition. |
| Many disclaimers | Uncertainty that helps the visitor make the right interpretation. |

The winning roster includes models, games, stories, visualizations, and concepts. **A new algorithm, AI runtime, global coverage, and a commercial product are not universal prerequisites.** Conversely, “we use real NASA data” is an entry credential, not a sufficient distinction.

The non-winning comparators also expose the limit of this advice: FarmHubGlobal and Cea-SAR already describe a particular user and application. A clear audience is necessary to a persuasive pitch, but cannot explain award outcomes by itself. Execution, category fit, and the strength of the comparison pool remain uncertain.

For SARtale, the most defensible emphasis is **Best Use of Storytelling / Best Use of Data**. Science can support that emphasis. Local Impact needs actual local-user evidence; the current ending does not supply it. This is positioning advice, not a statement that teams formally choose one award category.

## 3. Ten largest issues, ranked by likely effect on judging

All rankings and consequences are **[INFERENCE]**. Evidence paragraphs identify **[REPO]** observations, with external verification marked separately. Effort is **total person-hours**, assuming the existing app and processed data can be reused within event rules. Two people can overlap content and implementation, but elapsed time is not always half the total. Estimates exclude waiting for organizers/users and any large new data download.

### 1. Eligibility is unresolved before product quality even matters

**Evidence / file:** `docs/SI_USE.md:7–10` records app/pipeline development on 1 November, before the 14 November start, and a pending request for organizer guidance. Its closing checklist still asks for the Local Lead's answer. [WEB] A 2026 local-event page on the official platform explicitly says teams must not develop the intended solution before the event. That is corroborating local guidance, not a substitute for the global terms or an Islamabad ruling. [Santiago's official event page](https://www.spaceappschallenge.org/2026/local-events/santiago-dominican-republic/).

**Why it matters:** Conditional on an adverse eligibility ruling, every other improvement has no effect on global judging. I cannot estimate the probability, and I am not declaring the team disqualified. This is ranked first for severity, not proven likelihood.

**Concrete fix:** Give the relevant organizers a factual inventory of what existed when, obtain authoritative written guidance about eligibility/reuse, and record exactly what can be submitted. Complete the existing SI/logo disclosures. Preserve the history; do not relabel earlier development as weekend work. If a rebuild is required, scope that separately rather than assume this estimate covers it.

**Effort:** 1–2 person-hours to prepare the inventory and disclosures, plus external response time; any required rebuild is unknown. I sent no messages to organizers.

### 2. The beneficiary and demonstrated outcome are still hypothetical

**Evidence / screen:** The final story beat, `app/src/content/story.json`, `id: next`, says a planner could check flagged river stretches against gauges and a visit. `README.md`, judging table, calls the decision/check planned and “Not yet judged.” Site Stories offers measurements and hypotheses, but no completed planning task or measured learning outcome.

**Why it matters:** The viewer reaches the end and still has to invent the usefulness. “Could help planners” is weaker than showing one person making one better interpretation. A narrow educational product is more convincing than an implied operational product without its workflow.

**Concrete fix:** Pick an audience the team can actually reach during the event—such as local geography students or educators—and define one task: distinguish a supported water-change interpretation from interference and an unobserved event. Test that task with 3–5 people; record their actual answers before and after, including failures. Alternatively, demonstrate a real planner's review task if a planner is available. Do not manufacture endorsements or extrapolate a small test into population-level impact.

**Effort:** 5–8 person-hours, including small user sessions; recruitment may add elapsed time. Acceptance: a visitor can complete a stated task and the pitch reports observed outcomes rather than imagined benefits.

### 3. Validation cannot yet support a strong science-award pitch

**Evidence / screen:** `app/src/content/evidence.json:82–110` acknowledges tuned controls, non-blind rule revision, 35%/68% flags on two plain sites with unknown cause, and only 24% of flags surviving every single-date omission. `processing/sites_in.json` describes choosing sites from observed signal behavior, including rejecting an earlier control. The app presents a fresh-city check but says its script is absent. `docs/SI_USE.md:28` says the interpretations and site choices still await human checking.

**Why it matters:** Selection based on apparent stability makes quiet controls less persuasive. A null-calibration target near 1% is not measured physical-change accuracy, a false-discovery guarantee, or a 99% confidence score for a colored patch. The reported 1.4% real-order coverage versus a 1.26% maximum from 200 shuffled orders does not by itself establish useful classification of surface processes. These limitations do not invalidate every local observation, but they narrow the claim substantially.

**Concrete fix:** Freeze the rule before a small new evaluation. Preselect spatially separate areas using external geography/land-cover evidence, not their NISAR curves; include both quiet locations and externally supported changes. Have a person check the two headline interpretations against the underlying records. Publish reproducible inputs, counts, code, and sensitivity results for that limited evaluation. Replace unverifiable reviewer authority with rerunnable evidence or remove it. If this cannot be completed, present the layer as exploratory evidence and make the supported case studies—not detector accuracy—the main scientific result.

**Effort:** 8–12 person-hours for a bounded check with available data; this does not produce a validated general flood detector. Acceptance: another person can reproduce the check, and every performance statement identifies what was actually tested.

### 4. The headline suggests more timing and spatial precision than the analysis has

**Evidence / screens:** Hero copy says “Around 19 Aug” (`app/src/content/story.json:5`); the Tarbela beat names 19 August. `app/src/app.ts`, `STEP_CAPTION`, correctly explains that the color is the first pass after the fitted split. The manifest lists 26 July and 19 August as consecutive used passes at that split. `app/src/content/evidence.json:105–110` states 90 m analysis, 270 m drawing, omitted isolated flags, and dependence on two July baseline dates.

**Why it matters:** The careful explanation is downstream of a more memorable date. A visitor can walk away believing the event happened on 19 August or that a colored cell is a mapped physical boundary. The split is a model summary; it is not a directly observed onset.

**Concrete fix:** Lead with “A darker shore was observed by 19 Aug; the preceding used pass was 26 Jul.” Show the **26 Jul–19 Aug observation interval**, explicitly not a statistical confidence interval. At Attock, show the wider/gradual-transition ambiguity. Put the 90 m/270 m distinction beside the legend and identify drawn cells as generalized flags. Keep full sensitivities in the evidence view. Do not turn those cells into claimed flood area.

**Effort:** 3–5 person-hours. Acceptance: the hero, legend, card, and pitch agree on what the date and colored extent mean.

### 5. The story is guided, but the visitor mostly receives conclusions

**Evidence / screens:** `app/src/content/story.json` already contains ten steps in six beats, with automatic map views. `app/src/storyPanel.ts` renders their paragraphs, Next navigation, site links, and playback. The user can inspect, but the interpretation is generally supplied before they have to reason about it.

**Why it matters:** A guided tour is good presentation; it is not automatically distinctive storytelling. The surprising material is already present—an apparently dramatic signal attributed to interference, a water-related change, and a missed river peak—but it is delivered as exposition.

**Concrete fix:** Build a 90-second core investigation with three short decisions: “What can we conclude?”, “Which evidence would test this?”, and “What was not observed?” Reveal the evidence and answer after the choice. Use the existing detailed tour as the optional deeper route. Keep a visible “insufficient evidence” option; do not teach that every dramatic patch must have a physical explanation.

**Effort:** 6–9 person-hours. Acceptance: a first-time visitor can retell the central discovery and one limitation without reading a methods essay.

### 6. The independent evidence is described more than it is shown

**Evidence / screens:** `app/src/content/sites.json:118–121` and `:239–242` put FFD/OPERA checks into prose. `app/src/chart.ts` plots HH and HV only. `app/src/storyPanel.ts:118–120` renders source names as text; `app/src/evidenceView.ts` builds prose/tables with internal section links. The evidence page points users to a repository path rather than giving direct, dated references in the case itself. It also says only the first listed source is satellite data, despite listing OPERA as another satellite-derived product (`app/src/content/evidence.json:22`).

**Why it matters:** “Reference agrees” asks the judge to trust the author at the exact moment the app should show its strongest evidence. The absence of an August OPERA observation is especially important at Tarbela and should be visible, not buried.

**Concrete fix:** Add one compact evidence panel per headline site: the NISAR series, separate dated FFD measurements or OPERA water counts, a spatial footprint, and clickable source/product identifiers. Use separate labeled scales, actual observation dates, and visible gaps; do not interpolate external data onto NISAR dates or call OPERA ground truth. Correct the satellite-data sentence. This uses existing cited numbers before requiring any new dataset.

**Effort:** 5–8 person-hours. Acceptance: a judge can inspect the agreement, temporal mismatch, and source in one place.

### 7. Geographic and seasonal framing do not match the strongest evidence cleanly

**Evidence / screens:** The supplied task frames 2025–26 and Peshawar–Charsadda–Nowshera. The actual manifest contains nine July–October **2026** dates only. `README.md` correctly describes one season; `app/src/content/story.json` extends the area east to Tarbela, and its main supported changes are Tarbela/Attock. `processing/sites_in.json` has no Charsadda or Nowshera analysis site. The only shipped context overlay is `app/public/data/overlays/places.geojson`; `app/src/maplibreAdapter.ts` can load rivers/roads, but those files are absent. Labels are documented as approximate.

**Why it matters:** A judge unfamiliar with Pakistan cannot easily connect a radar texture, the Kabul/Indus system, the named communities, and the headline sites. A pitch about two monsoons or direct observation of Nowshera flooding would outrun this build.

**Concrete fix:** Use one honest scope sentence throughout: a 2026 radar season across the Peshawar Valley and adjoining Tarbela/Attock study window. Add a small Pakistan locator and sourced river/reservoir outlines, with site footprints and gauge locations. Explain why the study window includes the two headline sites. Keep Nowshera as the documented missed-observation example unless its own measured case is added. Do not imply that a new 2025 time series already exists.

**Effort:** 3–5 person-hours with readily available, properly attributed context geometry. Acceptance: a newcomer can locate the sites and explain which year and places the data cover.

### 8. The HH/HV controls expose radar terminology without fully teaching the distinction

**Evidence / screen:** The “Meet NISAR” beat calls HH/HV two ways of listening; the polarization beat primarily explains step sizes and the water noise floor (`app/src/content/story.json:35,94–101`). It does not clearly explain horizontal transmit/receive versus cross-polarized receive, or how the L-band choice affects the kinds of hypotheses worth examining.

**Why it matters:** Many visitors can toggle two images without learning why they differ. That weakens both science communication and the claim that the design is specifically about radar rather than a generic before/after map.

**Concrete fix:** Add a small, labeled HH/HV schematic and one controlled comparison using actual site curves. Explain that moisture, roughness, and vegetation structure can all affect the signal; demonstrate ambiguity rather than equating HV with a crop label. Tie L-band to sensitivity under vegetation while keeping surface/material interpretation conditional. NASA's radar education material supports the physical distinction; it does not validate these particular sites. [NASA polarization overview](https://science.nasa.gov/wp-content/uploads/2023/09/nasaisrosarmissionsnwgcapabilitiesandgaps.pdf), [NASA ARSET SAR Q&A](https://appliedsciences.nasa.gov/sites/default/files/2024-12/SAR_Part1_QandA.pdf).

**Effort:** 3–5 person-hours including a science/content check. Acceptance: a novice can explain what changed when switching polarization, without claiming the app identified a material conclusively.

### 9. Local accessibility and constrained-device delivery are not demonstrated

**Evidence / files:** `app/index.html` is English, and inspected content is English. The map requires WebGL (`app/src/startup.ts`, `app/src/lazyHost.ts`). `app/src/app.ts:597–614` honors Save-Data but otherwise warms all frames for a polarization. The frame directory contains **28 files totaling 34,389,154 bytes** (about 32.8 MiB); this is the full frame inventory, **not a measured initial download**. `README.md` explicitly says offline use has not been tested. Keyboard controls, textual chart tables, responsive styling, and reduced-motion handling already exist and deserve credit.

**Why it matters:** A local-impact claim is weaker if language, hardware, and connection constraints are assumed away. This is an untested delivery risk, not evidence that the app currently fails on phones.

**Concrete fix:** Test the core route on a modest phone, constrained network, keyboard, and reduced-motion setting. Provide a user-controlled lightweight mode and a static illustrated fallback for the three core cases. Translate that short route into Urdu or Pashto only if a fluent person can review it; retain English for international judging. Record measured loading and task-completion results. Do not call ordinary browser caching an offline guarantee.

**Effort:** 5–8 person-hours; add 2–3 if a reviewed translation is included. Acceptance: the core lesson is available even without an interactive map, and limitations are measured rather than assumed.

### 10. The best evidence cannot yet travel as a self-contained judging artifact

**Evidence / files:** In `app/src/app.ts`, views, story position, and selected dates live in application state; `app/src/main.ts` mounts the app without parsing a route. Inspection of `app/src` found no URL-state handling or report export. The README explains the project and local execution but does not itself provide a short, evidence-first judging walkthrough. This does not prove that the team has no presentation elsewhere; none was assessed here.

**Why it matters:** A reviewer following a link or reopening the app must rediscover the strongest case. A good live explanation can hide that weakness; the submitted artifact has to make its case by itself.

**Concrete fix:** Add reproducible local route state for the key case/date/polarization and a compact printable evidence card, or a static case page if that is faster. Prepare a short recorded walkthrough showing a real interaction, the external check, and the uncertainty. Follow the actual submission guide's duration/format when available; “90 seconds” here is a design target, not an official limit. Include source dates, provisional status, and the data/model version in the artifact.

**Effort:** 4–6 person-hours. Acceptance: someone outside the team can open the intended case, understand the result, and find its evidence without being coached.

## 4. Five bold but achievable differentiators

All five are **[INFERENCE / proposals]**. They build on the existing static app and data. None assumes a backend, a live forecast, fabricated testimony, or a new global dataset. Estimates overlap the corresponding fixes above; do not add them twice.

| Idea | What the visitor actually does | Why it is distinctive and achievable | Effort / scope limit | If only two |
|---|---|---|---|---|
| **1. The Radar Jury** | Examine three real cases and choose: supported surface-change hypothesis, likely instrument/interference issue, or insufficient observation. Reveal the competing evidence after each choice. | Makes scientific restraint a memorable activity. Existing Tarbela, 2 July, and Nowshera material supplies the cases. “Likely interference” remains uncertain; do not grade it as proven hardware diagnosis. | **8–12 person-hours**, three fixed cases, no AI chat or procedural game. Includes short user testing. | **KEEP** |
| **2. Three Witnesses, One Shore** | Scrub a single case while seeing NISAR, FFD, and OPERA observations on aligned time axes with their own dates, footprints, and missing intervals. Finish with a small evidence card. | Turns “Reference agrees” into inspectable evidence. Tarbela is especially useful because the missing August OPERA evidence prevents a falsely neat conclusion; Attock provides a second later-season check if time permits. | **8–12 person-hours**, Tarbela first, existing measurements, separate scales; no new real-time integration. | **KEEP** |
| **3. The Peak Between Passes** | Move a clearly labeled hypothetical sampling schedule over the recorded gauge series and see how a peak can be missed. Switch back to the actual NISAR pass dates and separate outage interval. | The visitor experiences the difference between cloud penetration and temporal coverage. It makes the already strong “What NISAR Missed” concept active. Never simulate radar observations or imply a daily gauge series resolves the continuous hydrograph. | **5–7 person-hours**, one gauge sequence, one timeline, no forecasting. | **CUT**; retain the existing factual missed-peak story. |
| **4. A Two-Voice Radar Score** | Play HH/HV site measurements as two explicitly labeled tones while a visual cursor and numeric values move through the season; gaps become silence. | Makes the “dance” literal and gives another way to perceive differing signals. The mapping is a representation of measurements, not sound recorded from Earth. Keep visual/text equivalents. | **4–6 person-hours**, one site, browser-generated tones, opt-in audio, one documented mapping. | **CUT FIRST**; attractive, but less valuable than evidence and audience outcome. |
| **5. The Valley Field Notebook** | Follow a short Urdu/English or Pashto/English investigation, then print/download one page of what was seen, what remains unknown, and which reference to check next. | A small, reviewable local-language artifact is a more credible community bridge than an abstract global-impact promise. A teacher or local participant can test it during the event. | **5–8 person-hours**, one reviewed language pair and one case; no full-app translation, no invented resident quotes. | **CUT as a full feature**; keep a short reviewed translation if audience testing shows it is essential. |

### Why these two

The Radar Jury supplies the narrative and measurable learning task. Three Witnesses supplies the proof. Together they change the project from “watch our radar season” to “use evidence to decide what radar can tell you.” They also use its strongest existing assets: real observations, explicit alternative explanations, controls, and honest missingness.

They are more defensible than adding an LLM narrator, a general flood-risk score, another decorative map mode, or a rushed crop classifier. Those additions would consume time while leaving the main judging weaknesses intact.

### A realistic two-person execution envelope

After an authoritative eligibility decision, aim for **roughly 32–40 total person-hours**, with one person responsible for measurements, source checks, and audience testing, and the other for the core interaction and evidence display. Reserve about 6 of those hours for integration, real-device checks, and the submission/demo. The two feature estimates above overlap with the recommended evidence and story fixes.

Do not try to finish all ten fixes plus all five ideas. The indispensable sequence is: resolve eligibility; have humans verify the two headline cases; repair timing/scope language; implement the jury plus one evidence panel; test the audience outcome; package the demonstration. If independent validation is not ready, narrow the claims and keep the statistical layer exploratory. If data access becomes a time sink, use the existing referenced measurements with explicit gaps.

The claim I would want a judge to remember is: **“SARtale lets you investigate one monsoon season—and learn when radar evidence supports an interpretation, when it is suspect, and when it is simply missing.”** That is a sharper and more supportable ambition than promising flood intelligence from this build.

## Review completion record

- Covered all 30 global winners through official NASA announcements, across all ten categories in each year.
- Examined SAR challenge wording and four explicitly bounded SAR comparators; distinguished global awards, honorable mentions, nominations, local wins, and sponsor recognition.
- Ranked exactly ten repository-grounded issues, each with a concrete fix and a two-person effort estimate.
- Proposed exactly five differentiators and explicitly retained two.
- No other research-note files read; no subagents, installs, code edits, builds, commits, publishing, or outbound messages performed. The only intended filesystem write is this report.
