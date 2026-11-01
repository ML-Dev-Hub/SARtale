# AI tool use and event timing

Written 2026-11-01, updated 2026-11-02. The Space Apps FAQ says a submission "must include a description of how SI tools were used" (NASA's term is Super Intelligence, SI). This file is that record, kept honest and updated as work continues.

## Event timing

- Work on this repository began on 2026-11-01, before the 14 Nov 2026 hackathon start. This must be reviewed against the event rules and disclosed as required.
- The team's reading of the rule, and what existed before this work, is in section 3 of `docs/SARtale-hackathon-plan.md`. The team is to tell the Islamabad Local Lead exactly what exists and get written guidance. If the Local Lead objects, their instruction applies, which may mean discarding this work.
- Before the repository: public pages were read, a metadata-only catalogue search was run, and a plan and a concept image were created. On 2026-11-01 the repository, app and pipeline code were written.
- On 2026-11-01 and 2026-11-02 NASA's public browse preview images for nine track 84 dates were downloaded (no login) and the catalogue was read for metadata. No calibrated NISAR GCOV file has been downloaded, because that needs an Earthdata login. Two public 2008 NISAR sample GCOV files were downloaded only to test the file reader. Sources are listed in `docs/DATA_SOURCES.md`.

## Tools used

| Tool | Used for | Where |
|---|---|---|
| Claude Code (Anthropic) | Planning, writing code (app and pipeline), writing tests, code review, writing documentation. Also ran the checks on the browse previews (which colour channel is which polarization, and where the images sit on the map), with the numbers recorded in the project's working notes | Whole repository, including this file |
| OpenAI Codex | Plan review | Review comments on the plan. It also produced the concept storyboard image `docs/assets/sartale-concept-storyboard.png` |

The concept storyboard image is a planning aid. It is an AI-generated mock-up and is not data or a screenshot of the app.

## Team logo

The team logo (`app/logo/SARtale.png`, with smaller copies in `app/public/brand/`) was supplied by the team. Its origin is unknown to this record. **The team must state here whether an AI tool made it, and which one if so, before submission.** The smaller copies were produced by resizing only (`app/scripts/make_brand_assets.py`), with no redrawing.

## Human responsibility

Saeed Ahmad and Shaharyar Sajid are responsible for the submission. Any claim about real NISAR data must be checked by a team member against the data before it is written into the app. The app now shows real browse previews, and its only statements about them are limits and cautions: the pixels are display-scaled and not calibrated, placement is good to about 2 km, 2 July may show radio interference (unconfirmed, seen by eye on the preview only), and 14 July is a forecast-orbit product. The team should look at all nine frames themselves before submission. No finding about the ground is claimed.

## To complete before submission

- State whether an AI tool made the logo.
- Add any other AI tool used from now on (for example for slides, narration or translation).
- Record the Local Lead's answer on the early start.
