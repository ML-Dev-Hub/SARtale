# AI tool use and event timing

Updated 15 Nov 2026. The Space Apps FAQ says a submission "must include a description of how SI tools were used" (NASA's term is Super Intelligence, SI). This file is that record, kept honest and updated as work continues.


## Tools used

| Tool | Used for | Where |
|---|---|---|
| Claude Code (Anthropic) | Planning, writing the app and pipeline code, tests, code review and documentation; running the pipeline on the real NISAR passes; drafting the copy, with every number taken from the data | Whole repository, including this file |
| OpenAI Codex | Research on past Space Apps winners and glacial lakes, plan and code review, drafts and reviews of the video scripts and edits, the SVG map status markers, a UI/UX review of the site, and stamping the "AI-generated" mark on the logo | Internal research notes (not published), review comments, `app/src/statusMarkers.ts`, `app/scripts/add_ai_mark.py` |
| ElevenLabs (voice "Nathaniel": eleven_v4 for the two longer videos, eleven_multilingual_v2 for the demos; music_v2_5; sound effects) | Narration, music and sound effects of the videos | The four videos in `media/` only. Each says so on screen and in its file metadata. Not part of the app or the data |

No AI model runs in the pipeline or the app. Lake Watch is plain statistics: a darkness rule on radar backscatter, with radar shadow and layover on the valley walls (from the Copernicus terrain model) left out of the reference, and a change test against each lake's own noise.

## Team logo

The team logo (`app/logo/SARtale.png`, with smaller copies in `app/public/brand/`) was created using ChatGPT Imaging model and carries a small "AI-generated" mark, as Space Apps asks for AI-generated images. The smaller copies were produced by resizing only (`app/scripts/make_brand_assets.py`), with no redrawing. The team photos in the videos and slides are real photographs.

## Human responsibility

Saeed Ahmad, Shaharyar Sajid and Usama Hussain are responsible for the submission. Every claim about real NISAR data must be checked by a team member against the data before it is presented. The lake copy and the video script were drafted by AI tools from the data and need that check.
