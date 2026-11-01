# Task W report: website improvement

Status: DONE_WITH_CONCERNS

## Commits (none carries a Co-Authored-By line, per the later instruction)
34d6bfe story copy, hero finding, card map checks
0f0ce2a time axis and frame preloader
bbac21a site cards reworked
f1046b9 How we know view, DATA_SOURCES additions
16664dd story panel, hero picture
d8e8dc5 map fills the stage, lazy map loading
43379d1 start screen, story, date line, Change key, footer, mobile layout
3ea4d9b README and docs
5437c9e copy fix (no "farmland"), Change key on short screens

## What changed
- Start screen: real radar picture (hero-radar.webp, 213 KB, scaled from the composite by app/scripts/make_hero_image.py; data frames untouched), plain-language lede, one finding worded as a hypothesis, nine-pass timeline with the gap.
- Guided story (story.json): ten steps in six parts; each moves the real map; leave via "Explore freely" and resume.
- Map fills the stage (cover fit, no side bands); scale bar, zoom buttons; floating controls; upright phones show the middle two thirds.
- Date line spaced by real time, gap as hatched band, flagged and excluded dates marked; frames preload (HH first, HV on demand); loading pill and "Preparing frames n of 9"; play waits for the next frame.
- Change view: key with a row per date and two shades, dates tinted on the date line, caption states one season-wide map and that colour is the step date; limits in plain words; Unusual dates secondary.
- How we know (evidence.json); cards chart-first with controls marked; tap a chart point or table date to open the map on that date.
- Header has one logo; footer has credits and team; mobile tab bar, bottom-sheet story.
- Performance: map library split out (main JS 1.2 MB to 136 KB); build shows no outside URLs.
- Task C fixes: limits wording, pixel counts instead of bare percentages, shore two-earlier-dates note, control wording, 270 m/90 m and 31%, README 8 GB note, card lenient wording.

## Screenshots (.superpowers/sdd/2026-11-01-sartale-hackathon/web-*.png)
hero 1440x900 and 1280x720; map; change; story; card and control card; evidence; missed; mobile 390 (2x, touch emulation) hero, map, story, peak, change, card, evidence; focus ring. The final batch of screenshots was still rendering at handback; the copied files are the most recent complete renders, and a few desktop ones may predate the last CSS tweak.

## Tests
npm test: 284 pass (16 files, new tests for story navigation, time axis and gap, preloader, lazy host, copy limits, evidence). npm run build passes. pytest not run (no Python under processing/tests touched; no test reads docs).

## Could not verify
- Five fresh cities at 0% and the 8 GB figure for `run_pipeline change` are reviewer numbers; written into docs and README as such. The 31% was reproduced from the COGs (also 43% not in own class).
- Not tested offline with the network off, real touch devices, screen readers, or Safari/Firefox. Contrast was judged by palette, not measured.
- Chart tap was tested with a fake chart, not a real uPlot click in a browser.

## Concerns
- Older commits (6a07aab and before) still carry the trailer; rewrite is pending as noted.
- On 1280x720 the Change key can scroll a little; on mobile the key is folded.
- Hero image is a new derived asset (reported as required).

## Fix round 1

Changes: 14 Jul and 2 Jul cautions now sit inside the story card (story-caution, all screen sizes) and the 23 July text states the 14 July caution; mobile toolbar wraps (Change full-width, no sideways scroll), duplicate resume chip removed (header button resumes, title says the step), story hides composite/before picker on phones to keep map room; closing a whole-area story step returns the map to its default view; padding is clamped so MapLibre cannot report "Map cannot fit within canvas" (no console warnings seen at 390 px); strip caption spacing and mobile sheet height fixed; evidence.json drops the invented 2 July reprocessing expectation, mask sentence follows DATA_SOURCES, "likely" on the 2 July bullet, fresh-cities labelled as an independent reviewer's result everywhere; "HV no data." wording; Escape returns focus to the story button; off-screen site markers get tabindex -1; preload.onChange unsubscribed in destroy; background story steps carry a "Background, not a finding" tag.
Covering tests (appStory.test.ts, evidenceView.test.ts, sitesView.test.ts): cautions in card, background tag, Escape focus and home camera, preload unsubscribe, no invented expectation, reviewer wording, no-data wording.
Commands: `npx tsc --noEmit`, `npx vitest --run` -> 292 passed; `npm run build` ok.
Screenshots: web-fix-m-peak, web-fix-m-2jul, web-fix-m-closed, web-fix-m-controls (390 px, 2x), web-fix-d-peak (1440x900).
Not unit-tested: adapter padding clamp and marker tabindex (need WebGL); checked only by screenshot and absence of console warnings. The closed phone map keeps the default upright view, which still leaves empty bands above and below the image.

## Fix round 2

- sites.json Peshawar "test" no longer predicts a value: it compares 2 July HV with a later NASA reprocessing and with other passes made without interference. evidenceView.test.ts now also checks all cards, story.json and the hero for "interference filtering", "back to about -10", "should bring HV", and that the Peshawar test names no dB value.
- Console capture at a true 390 px (CDP, touch emulation, console.warn hooked, walking every story step and then leaving the story): first run showed one "Map cannot fit within canvas with the given bounds, padding, and/or offset." on the gap step (the second tall padding in a row). Fix: maplibreAdapter clears the map's existing padding before a fit move. Re-run over all ten steps plus exit: warnings `[]`.
- 23 July card at 390 px: the strip caption was clipped (caption bottom 613 against card body bottom 561). On phones the caption is now hidden (the labelled axis and its aria-label carry the same facts); re-measured at scroll 0 and after scrolling 40 px: axis bottom 558 inside body bottom 561, clipped false. Desktop keeps the caption. Screenshot: web-fix2-m-peak.png.
- Commands: `npx tsc --noEmit`; `npx vitest --run` -> 292 passed; `npm run build` ok.
