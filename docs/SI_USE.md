# AI tool use and event timing

Written 2026-11-01. The Space Apps FAQ says a submission "must include a description of how SI tools were used" (NASA's term is Super Intelligence, SI). This file is that record, kept honest and updated as work continues.

## Event timing

- Work on this repository began on 2026-11-01, before the 14 Nov 2026 hackathon start. This must be reviewed against the event rules and disclosed as required.
- The team's reading of the rule, and what existed before this work, is in section 3 of `docs/SARtale-hackathon-plan.md`. The team is to tell the Islamabad Local Lead exactly what exists and get written guidance. If the Local Lead objects, their instruction applies, which may mean discarding this work.
- Before the repository: public pages were read, a metadata-only catalogue search was run, and a plan and a concept image were created. On 2026-11-01 the repository, app and pipeline code were written.
- No real NISAR data file has been downloaded. The only NISAR query so far was a metadata-only catalogue search on 2026-11-01.

## Tools used

| Tool | Used for | Where |
|---|---|---|
| Claude Code (Anthropic) | Planning, writing code (app and pipeline), writing tests, code review, writing documentation | Whole repository, including this file |
| OpenAI Codex | Plan review | Review comments on the plan. It also produced the concept storyboard image `docs/assets/sartale-concept-storyboard.png` |

The concept storyboard image is a planning aid. It is an AI-generated mock-up and is not data or a screenshot of the app.

## Team logo

The team logo (`app/logo/SARtale.png`, with smaller copies in `app/public/brand/`) was supplied by the team. Its origin is unknown to this record. **The team must state here whether an AI tool made it, and which one if so, before submission.** The smaller copies were produced by resizing only (`app/scripts/make_brand_assets.py`), with no redrawing.

## Human responsibility

Saeed Ahmad and Shaharyar Sajid are responsible for the submission. Any claim about real NISAR data must be checked by a team member against the data before it is written into the app. No such claim exists yet.

## To complete before submission

- State whether an AI tool made the logo.
- Add any other AI tool used from now on (for example for slides, narration or translation).
- Record the Local Lead's answer on the early start.
