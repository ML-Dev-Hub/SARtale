# AI tool use and event timing

Updated 4 Nov 2026. The Space Apps FAQ says a submission "must include a description of how SI tools were used" (NASA's term is Super Intelligence, SI). This file is that record, kept honest and updated as work continues.


## Tools used

| Tool | Used for | Where |
|---|---|---|
| Claude Code (Anthropic) | Planning, writing the app and pipeline code, tests, code review and documentation; running the pipeline on the real NISAR passes; drafting the copy, with every number taken from the data | Whole repository, including this file |
| OpenAI Codex | Research on past Space Apps winners and glacial lakes, plan and code review, a draft of the demo script, the SVG map status markers, and a UI/UX review of the site | Internal research notes (not published), review comments, `app/src/statusMarkers.ts` |
| ElevenLabs (eleven_v4 voice "Nathaniel", music_v2_5, sound effects) | Narration, music and sound effects of the two videos | `media/SARtale-lake-watch-demo.mp4` and `media/SARtale-how-it-works.mp4` only. Not part of the app or the data |

No AI model runs in the pipeline or the app. Lake Watch is plain statistics: a darkness rule on radar backscatter, with radar shadow and layover on the valley walls (from the Copernicus terrain model) left out of the reference, and a change test against each lake's own noise.

## Team logo

The team logo (`app/logo/SARtale.png`, with smaller copies in `app/public/brand/`) was created using ChatGPT Imaging model. The smaller copies were produced by resizing only (`app/scripts/make_brand_assets.py`), with no redrawing.

## Human responsibility

Saeed Ahmad, Shaharyar Sajid and Usama Hussain are responsible for the submission. Every claim about real NISAR data must be checked by a team member against the data before it is presented. The lake copy and the video script were drafted by AI tools from the data and need that check.
