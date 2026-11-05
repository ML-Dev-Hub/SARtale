# AI tool use and event timing

Updated 4 Nov 2026. The Space Apps FAQ says a submission "must include a description of how SI tools were used" (NASA's term is Super Intelligence, SI). This file is that record, kept honest and updated as work continues.

## Event timing

- Work on this repository began on 2026-11-01, before the 14 Nov 2026 hackathon start. This must be reviewed against the event rules and disclosed as required.
- The team is to tell the Islamabad Local Lead exactly what exists and get written guidance. If the Local Lead objects, their instruction applies, which may mean discarding this work.
- An earlier chapter on the Peshawar Valley was built on 1 and 2 Nov 2026 and removed from the app on 4 Nov 2026 to focus on Lake Watch. It remains in the git history (branch `build/sartale`).

## Tools used

| Tool | Used for | Where |
|---|---|---|
| Claude Code (Anthropic) | Planning, writing the app and pipeline code, tests, code review and documentation; running the pipeline on the real NISAR passes; drafting the copy, with every number taken from the data | Whole repository, including this file |
| OpenAI Codex | Research on past Space Apps winners and glacial lakes, plan and code review, and a draft of the demo script | Internal research notes (not published), review comments |
| ElevenLabs (eleven_v4 voice "Nathaniel", music_v2_5, sound effects) | Narration, music and two sound effects of the demo video | `media/SARtale-lake-watch-demo.mp4` only. Not part of the app or the data |

No AI model runs in the pipeline or the app. Lake Watch is plain statistics: a darkness rule on radar backscatter, a two-view shadow rule, and a change test against each lake's own noise.

## Team logo

The team logo (`app/logo/SARtale.png`, with smaller copies in `app/public/brand/`) was supplied by the team. Its origin is unknown to this record. **The team must state here whether an AI tool made it, and which one if so, before submission.** The smaller copies were produced by resizing only (`app/scripts/make_brand_assets.py`), with no redrawing.

## Human responsibility

Saeed Ahmad, Shaharyar Sajid and Usama Hussain are responsible for the submission. Every claim about real NISAR data must be checked by a team member against the data before it is presented. The lake copy and the video script were drafted by AI tools from the data and need that check.

## To complete before submission

- State whether an AI tool made the logo.
- Add any other AI tool used from now on (for example for slides or translation).
- Record the Local Lead's answer on the early start.
