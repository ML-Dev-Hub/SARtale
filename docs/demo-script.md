# Demo script and deck outline

Numbers come from `app/public/data/lakes.json` (rebuilt 3 Nov 2026). Re-read it before presenting. Every figure is indicative and on provisional data.

## 30-second script (app first)

**0-5 s. The cloud gap.** App on the Lake Watch start screen. Read the quote: "Persistent cloud cover after 16 June 2026 has limited the availability of cloud-free satellite imagery, making it difficult to accurately assess lake area changes during the last three to four days." (SUPARCO, GLOF Status Update, 2 July 2026.)

**5-20 s. Lake Watch.** "NISAR radar sees through cloud. From 17 June to 4 August, while SUPARCO's updates reported cloud limiting optical imagery, NISAR made 60 valid looks across 11 lakes. In this build all 11 read Stable." Open one lake, for example Attabad: latest look 23 October on track 156A, 7 looks, 0.128 km2 against a median of 0.135 km2, noise 0.013 km2. Say what the status means: the radar water area did not move by more than its noise.

**20-30 s. The brief, then the close.** Open the lake brief: status, date, look count, noise, and the line that official warnings come from PMD and NDMA. Close with: "Built on NISAR, open source."

Do not call any lake fine or fixed. A Stable status means no change beyond noise in this build, on provisional data.

## Deck outline (7 slides)

1. **Problem.** SUPARCO tracks 131 potentially dangerous glacial lakes. Its 2 July 2026 update rests on one 16 June image and says cloud limited cloud-free imagery. Shisper's outburst on 7 May 2022 destroyed the Karakoram Highway bridge at Hassanabad.
2. **User.** GBDMA, PDMA KP and the district administrations, deciding which lakes to inspect and which downstream places to brief. Only what is in `docs/admin-meeting.md` may be cited as their words.
3. **Why NISAR.** L-band radar sees through cloud. Provisional calibrated GCOV data from 17 June 2026, read as small windows over HTTPS: 232 passes, about 5.4 GB, about an hour.
4. **The two-view rule.** In each pass, a dark pixel inside the lake zone counts as water unless it is shadow-prone: dark in one viewing direction's season median image but not in the other's, which is radar shadow, not water. A lake mostly in shadow says "Not observable".
5. **Lake Watch.** The app: 11 lakes, one plain status each (Growing, Stable, Shrinking, Not seen this pass, Not observable, Not enough NISAR looks yet), every number with its date, look count and noise. 60 valid looks in the cloud window; all 11 Stable in this build.
6. **Validation and limits.** In the same-day Sentinel-2 cross-check, areas were similar only at Attabad (radar 0.218, optical 0.185 km2), and even there the overlap was low (IoU 0.11); elsewhere the areas disagreed widely. Khurdopin: 0.036 against 0.885 km2. Passu: 0.048 against 0.239. Shisper, where no lake is expected: 0.087 against 0.288, so optical also flags water there. The data is provisional, areas are water inside a search circle, and the constants were not tuned on ground truth. Official warnings come from PMD and NDMA.
7. **Ask.** Introductions to GBDMA and PDMA KP; their lake IDs and locations; answers to the meeting questions; guidance on who can request NISAR Urgent Response.
