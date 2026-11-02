# AI tool use and event timing

Written 2026-11-01, updated 2026-11-02. The Space Apps FAQ says a submission "must include a description of how SI tools were used" (NASA's term is Super Intelligence, SI). This file is that record, kept honest and updated as work continues.

## Event timing

- Work on this repository began on 2026-11-01, before the 14 Nov 2026 hackathon start. This must be reviewed against the event rules and disclosed as required.
- The team's reading of the rule, and what existed before this work, is in section 3 of `docs/SARtale-hackathon-plan.md`. The team is to tell the Islamabad Local Lead exactly what exists and get written guidance. If the Local Lead objects, their instruction applies, which may mean discarding this work.
- Before the repository: public pages were read, a metadata-only catalogue search was run, and a plan and a concept image were created. On 2026-11-01 the repository, app and pipeline code were written.
- On 2026-11-01 and 2026-11-02 NASA's public browse preview images for nine track 84 dates were downloaded (no login) and the catalogue was read for metadata. Two public 2008 single-pol NISAR sample GCOV files were downloaded only to test the file reader. On 2026-11-02 the calibrated P05023 GCOV files were downloaded and the first calibrated build was run, with OPERA DSWx-S1 tiles and Flood Forecasting Division bulletins read for the checks. Sources are listed in `docs/DATA_SOURCES.md`.

## Tools used

| Tool | Used for | Where |
|---|---|---|
| Claude Code (Anthropic) | Planning, writing code (app and pipeline), writing tests, code review, writing documentation. Also ran the checks on the browse previews and the first calibrated build, chose the sites from the real stack, compared them with OPERA and the bulletins, and drafted the site cards, with the numbers recorded in the project's working notes | Whole repository, including this file |
| Claude Code (Anthropic), change layer | Chose the statistical method after reading `distmetrics`, wrote `processing/sartale/change.py` and its tests, ran it on the real stack, set the threshold from the control pixels by a stated rule, wrote the Change control, and drafted the verdict in `docs/DATA_SOURCES.md`. Later wrote the before-and-after step layer from a prototype, tested it with shuffled dates, and drafted its verdict. Both layers are plain statistics: no AI model runs in the pipeline or the app, and no deep learning was used | `processing/sartale/change.py`, `processing/checks/change_evidence.py`, `processing/checks/step_evidence.py`, the app |
| OpenAI Codex | Plan review | Review comments on the plan. It also produced the concept storyboard image `docs/assets/sartale-concept-storyboard.png` |
| Claude (Anthropic), Lake Watch, via subagents | Code, documentation, pipeline and app implementation for Lake Watch (`lakes-*` subcommands, `lakes.json`, the lake views, the meeting log, the demo script and these records). Plain statistics: no AI model runs in the pipeline or the app | `processing/sartale/`, `app/`, `docs/` |
| OpenAI Codex, Lake Watch | Research and review of past Space Apps winners, glacial-lake literature, and code review | Notes under `docs/research_notes/`, `docs/reports/`, review comments |
| ElevenLabs, via MCP | Narration of the explainer video, voice "Alice" | The video narration audio. Not part of the app or the data |

The concept storyboard image is a planning aid. It is an AI-generated mock-up and is not data or a screenshot of the app.

## Team logo

The team logo (`app/logo/SARtale.png`, with smaller copies in `app/public/brand/`) was supplied by the team. Its origin is unknown to this record. **The team must state here whether an AI tool made it, and which one if so, before submission.** The smaller copies were produced by resizing only (`app/scripts/make_brand_assets.py`), with no redrawing.

## Human responsibility

Saeed Ahmad and Shaharyar Sajid are responsible for the submission. Any claim about real NISAR data must be checked by a team member against the data before it is written into the app. The site choices and every card were drafted by an AI tool from the data and have not yet been checked by a person, so a team member must read each card against its curve and open the 2 July evidence in `docs/DATA_SOURCES.md` before submission. The cards keep their explanations as hypotheses, and no flood, damage or crop finding is claimed. The change layer's verdict and the notes on four cards were also drafted by an AI tool and need the same check.

## To complete before submission

- State whether an AI tool made the logo.
- Add any other AI tool used from now on (for example for slides, narration or translation).
- Record the Local Lead's answer on the early start.
