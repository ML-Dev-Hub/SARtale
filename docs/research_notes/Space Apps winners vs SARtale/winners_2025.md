# NASA Space Apps Challenge 2025 Global Winners: Per-Project Evidence

Evidence checked 2 November 2026. Project details below are the teams' own submission text unless marked otherwise, so performance and impact figures are self-reported and were not independently tested. Team members are given in NASA's abbreviated form.

## Which projects won each 2025 global award, and what did each entry look like?

### Takeaway
There were exactly 10 awards and 10 winners, one each. Seven winners have a checkable product link that loads and an eighth, Gaia+LEO, has a public repo, but the entries range from a working geospatial stack to a deck-based concept. The demos were very short: five confirmed videos of 29 to 30.5 seconds and two PDFs of 6 and 7 pages.

### Cited Findings

#### Summary table

Sources for all rows: [NASA announcement](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/) (award, team, challenge, country) and [Meet the 2025 Global Winners](https://www.spaceappschallenge.org/2025/meet-the-2025-global-winners/) (team pages). Local events are from each team page, linked in the per-project entries.

| Award | Team / project | Country (NASA) | Local event | Challenge | Form | Demo submitted |
|---|---|---|---|---|---|---|
| Best Use of Science | SpaceGenes+ | Germany | Berlin | Build a Space Biology Knowledge Engine | Web dashboard | Drive link now 404, unverified |
| Best Use of Data | Resonant Exoplanets / Resonant Worlds Explorer | United States | Mountain View, CA | A World Away: Hunting for Exoplanets with AI | Full-stack web app and ML/physics pipeline | YouTube, 30 s |
| Best Use of Technology | Twisters / SkySense | Mexico | Monterrey | Will It Rain on My Parade? | Web app with chatbot | PDF, 6 pages |
| Galactic Impact | Astro Sweepers | Universal Event | Universal Event | Commercializing Low Earth Orbit (LEO) | Web portal, analysis and business plan | MP4, 30.5 s |
| Best Mission Concept | PureFlow | Brazil | Aracaju | Your Home in Space: The Habitat Layout Creator | 3D web design and simulation tool | YouTube, 29 s |
| Most Inspirational | Photonics Odyssey / AakashNet | India | Chennai | Commercializing Low Earth Orbit (LEO) | Concept, mockups and hardware simulation | Canva deck, unverified |
| Best Use of Storytelling | HerCode Space / A Solar Tale | Universal Event | Universal Event | Stellar Stories: Space Weather Through the Eyes of Earthlings | Scroll-driven digital children's story | YouTube, length unverified |
| Global Connection | Gaia+LEO | United States | Seattle, WA | Commercializing Low Earth Orbit (LEO) | Optimization model with dashboard | PDF, 7 pages |
| Art & Technology | Zumorroda-X / Henry's Farm Adventure | Egypt | Cairo | NASA Farm Navigators | Browser game | MP4, 29.2 s |
| Local Impact | QUEÑARIS | Peru | Arequipa | BloomWatch | Web decision-support platform with drone and field work | YouTube, 30 s |

Video lengths come from YouTube page metadata (`lengthSeconds`) or the MP4 `mvhd` header of the linked file. PDF page counts come from the PDF `/Count` field. I did not watch the videos, so visual style is not assessed unless stated.

#### Best Use of Science: SpaceGenes+
- Team: Saloni T., a one-person entry in NASA's listing, event Berlin — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/); [team page](https://www.spaceappschallenge.org/2025/find-a-team/spacegenes/).
- The team profile describes a UX designer with a healthtech/fintech background joining solo and seeking collaborators — [team page](https://www.spaceappschallenge.org/2025/find-a-team/spacegenes/).
- Product: an interactive dashboard surfacing how radiation and microgravity jointly change gene expression, naming TP53, ATM and GADD45A as non-additive responders — [team page](https://www.spaceappschallenge.org/2025/find-a-team/spacegenes/).
- Data: NASA GeneLab GLDS-288/OSD-288, mouse spleen RNA-seq in spaceflight — [team page](https://www.spaceappschallenge.org/2025/find-a-team/spacegenes/).
- Method: a simple statistic. Synergy scores use fold-change across conditions, and a gene is flagged when the combined effect exceeds the sum of the individual effects — [team page](https://www.spaceappschallenge.org/2025/find-a-team/spacegenes/).
- Stack: Framer front end, Bolt for the dashboard, Python (Pandas, NumPy) for preprocessing, Figma, Google Sheets/CSV; Lovable is also listed — [team page](https://www.spaceappschallenge.org/2025/find-a-team/spacegenes/).
- Scope limit: filtering by organ and stressor is described as future work — [team page](https://www.spaceappschallenge.org/2025/find-a-team/spacegenes/).
- Conflict: the team page says the tool currently features OSD-288, while the site advertises "Cross-Study Integration" of multiple GeneLab datasets — [team page](https://www.spaceappschallenge.org/2025/find-a-team/spacegenes/); [project site](https://spacegenes-plus.framer.website/).
- Demo and repo: the site loaded (HTTP 200) on 2 November 2026, the linked Drive demo returned 404, and no repo is listed — [project site](https://spacegenes-plus.framer.website/); [team page](https://www.spaceappschallenge.org/2025/find-a-team/spacegenes/).
- Team statement: the project relied on synergistic gene responses and "demonstrated how thoughtful design and data visualization can make complex space biology far more accessible" — [Meet the Winners](https://www.spaceappschallenge.org/2025/meet-the-2025-global-winners/).

#### Best Use of Data: Resonant Exoplanets (Resonant Worlds Explorer)
- Team: Adhvaidh S., Gabriel S., Jack A., Sahil S.; event Mountain View, CA — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/); [team page](https://www.spaceappschallenge.org/2025/find-a-team/resonant-exoplanets/).
- Product: an end-to-end pipeline that fetches NASA data, detects transits, validates signals with physics models, checks atmospheric chemistry, and outputs plots and generated reports — [team page](https://www.spaceappschallenge.org/2025/find-a-team/resonant-exoplanets/).
- NASA data: Kepler, TESS, JWST and Hubble through MAST. Partner material cited: ESA PLATO and Ariel — [team page](https://www.spaceappschallenge.org/2025/find-a-team/resonant-exoplanets/).
- Method: XGBoost, Lightkurve and Astroquery, plus "Modulus", which the team calls an exact-math solver built from a modified Qwen transformer. Biosignature logic tests whether O₂, CH₄ and O₃ can coexist without biological replenishment — [team page](https://www.spaceappschallenge.org/2025/find-a-team/resonant-exoplanets/).
- Stack: FastAPI, TypeScript/React, ReportLab, Google Cloud — [team page](https://www.spaceappschallenge.org/2025/find-a-team/resonant-exoplanets/).
- Demo: 30-second YouTube video, uploaded 5 October 2025, 1,702 views when checked, description "Global 1st Place (Best Use of Data)" — [YouTube](https://www.youtube.com/watch?v=5fBB5YJpfwU).
- Live site loaded (HTTP 200), a JavaScript shell titled "Exoplanet AI - Hunting for New Worlds"; I did not exercise it — [site](https://resonant-planet.vercel.app).
- Team statement: "We built our project to make those signals more transparent and more trustworthy for everyone" — [Meet the Winners](https://www.spaceappschallenge.org/2025/meet-the-2025-global-winners/).

#### Best Use of Technology: Twisters (SkySense)
- Team: Fernando A., Marcelo T., Mariana D., Regina R., Regina F.; event Monterrey — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/); [team page](https://www.spaceappschallenge.org/2025/find-a-team/twisters/).
- Product: personalized local weather risk for planning outdoor activity, with suggested safe time windows, calendar sync, and the TwisterBot assistant — [team page](https://www.spaceappschallenge.org/2025/find-a-team/twisters/).
- NASA data: POWER API and Data Access Viewer, Earthdata, Giovanni, GES DISC. Partner and other data: Open-Meteo, OpenStreetMap, Google APIs — [team page](https://www.spaceappschallenge.org/2025/find-a-team/twisters/).
- Method: a pipeline that blends and cleans sources into probability metrics, plus Gemini for conversation. The "predictive model" is not specified — [Meet the Winners](https://www.spaceappschallenge.org/2025/meet-the-2025-global-winners/); [team page](https://www.spaceappschallenge.org/2025/find-a-team/twisters/).
- Stack: React, Firebase, Supabase, Figma. AI disclosure: Lovable, Builder.io, ChatGPT — [team page](https://www.spaceappschallenge.org/2025/find-a-team/twisters/).
- Demo: 6-page PDF titled "Twisters_Global Stage.pdf", 71 MB — [Drive](https://drive.google.com/file/d/1LDaKDOHBKm3PxC03xcEJGfdybsVEwOTf/view).
- Link rot: skysense.surf now serves a domain-for-sale page, so the live demo could not be checked — [site](https://skysense.surf/).
- No public repo is listed — [team page](https://www.spaceappschallenge.org/2025/find-a-team/twisters/).

#### Galactic Impact: Astro Sweepers
- Team: Harshiv T., Pragathy S., Pratik J., Sherlin D., Yousra H., Zienab E.; Universal Event, with member profiles from India, Egypt, the Philippines and Germany — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/); [team page](https://www.spaceappschallenge.org/2025/find-a-team/astro-sweepers-we-catch-what-space-leaves-behind/).
- Product: a compliance and risk platform that automates NASA Debris Assessment Software workflows, auto-fills ODAR/EOMP reports, and scores every object with the ASRI index — [team page](https://www.spaceappschallenge.org/2025/find-a-team/astro-sweepers-we-catch-what-space-leaves-behind/).
- Data: NASA DAS, SPARK 2022, Space-Track TLEs/CDMs, ESA DISCOS and Copernicus Data Space, plus a Kaggle debris dataset — [team page](https://www.spaceappschallenge.org/2025/find-a-team/astro-sweepers-we-catch-what-space-leaves-behind/).
- Method: a weighted index (R 0.45, D 0.25, C 0.20, S 0.10), Gaussian-smoothed altitude-inclination density, vis-viva Δv, fairness selection of the top 3 objects per country, and DAS population runs to 2100 — [team page](https://www.spaceappschallenge.org/2025/find-a-team/astro-sweepers-we-catch-what-space-leaves-behind/).
- Worked case: a CZ-2C rocket body moved from failing to compliant with a roughly 22 m/s burn. Scenario comparison: about 21,800 objects by 2100 with no DAS against about 11,200 with DAS plus ASRI (self-reported) — [team page](https://www.spaceappschallenge.org/2025/find-a-team/astro-sweepers-we-catch-what-space-leaves-behind/).
- Business case: eight revenue tiers, break-even after about 60 missions, and a claimed path to $500M+ ARR (self-reported) — [team page](https://www.spaceappschallenge.org/2025/find-a-team/astro-sweepers-we-catch-what-space-leaves-behind/).
- Inconsistency: the CNN classifier is called exploratory and not integrated, yet the same text says one ML model is deployed — [team page](https://www.spaceappschallenge.org/2025/find-a-team/astro-sweepers-we-catch-what-space-leaves-behind/).
- Demo: 30.5-second MP4 of 3.4 MB, filename "WhatsApp Video 2025-10-06 at 03.23.19.mp4" — [Drive](https://drive.google.com/file/d/1L3cIR8WZdzdp7eUY3leIToGTbnMiBT4N/view).
- Live site loaded and offers business plan, audit report, financial model and team presentation downloads. No repo is listed — [site](https://astro-sweepers.vercel.app/).
- The submission text keeps what reads like assistant-draft wording, such as "Your platform", "which judges value", and "Prepare two line charts" — [team page](https://www.spaceappschallenge.org/2025/find-a-team/astro-sweepers-we-catch-what-space-leaves-behind/).

#### Best Mission Concept: PureFlow
- Team: Esthefany M., João F., Laiza L., Lara D., Pedro H., Thayane D.; event Aracaju; the repo says students from a Computer Science course — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/); [team page](https://www.spaceappschallenge.org/2025/find-a-team/pureflow2/); [repo](https://github.com/larasdiniz/PureFlow-2025).
- Product: a 3D habitat design tool that computes mass, power and life support from crew size and mission duration, and tests designs against space weather — [team page](https://www.spaceappschallenge.org/2025/find-a-team/pureflow2/).
- NASA data: the DONKI space weather API, an NTRS softgoods habitat report, and NASA 3D resources — [team page](https://www.spaceappschallenge.org/2025/find-a-team/pureflow2/).
- Differentiator: the team's pitch is one question, "Would Your Habitat Survive a Solar Storm... Today?", with a live link to real solar events — [team page](https://www.spaceappschallenge.org/2025/find-a-team/pureflow2/).
- Method: engineering calculations and simulation, with no ML claimed — [team page](https://www.spaceappschallenge.org/2025/find-a-team/pureflow2/).
- Demo: 29-second YouTube video, 1,493 views when checked. Audio credited to elevenlabs.io, which suggests AI voiceover — [YouTube](https://www.youtube.com/watch?v=hHUpo7bTVuc); [team page](https://www.spaceappschallenge.org/2025/find-a-team/pureflow2/).
- Live site loaded and the public repo has a two-sentence README. The YouTube description calls the tool "Habitat Designer" — [site](https://larasdiniz.github.io/PureFlow-2025/src/public/html/home/home.html); [repo](https://github.com/larasdiniz/PureFlow-2025); [YouTube](https://www.youtube.com/watch?v=hHUpo7bTVuc).

#### Most Inspirational: Photonics Odyssey (AakashNet)
- Team: Manish D., Deeraj K., Prasanth G., Rajalingam N., Rashi M., Sakthi R.; event Chennai. The page URL slug is `photonic-force` — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/); [team page](https://www.spaceappschallenge.org/2025/find-a-team/photonic-force/).
- Product: a concept for a sovereign Indian LEO broadband network, with phased-array user terminals (about 1,280 antennas) and laser inter-satellite links — [team page](https://www.spaceappschallenge.org/2025/find-a-team/photonic-force/).
- NASA framing: help connect more than 700 million people who lack broadband access — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/).
- Data: the only NASA reference listed is the NASA Image and Video Library. ISRO ISTRAC is the partner reference — [team page](https://www.spaceappschallenge.org/2025/find-a-team/photonic-force/).
- Method: RF and link budget modelling in MATLAB and OpenEMS, and a front-end-only dashboard in HTML, Tailwind and JavaScript, described as locally hosted — [team page](https://www.spaceappschallenge.org/2025/find-a-team/photonic-force/).
- Demo: a Canva deck (not viewed) and a Drive folder containing AakashNet.pptx. No hosted app or repo is listed — [team page](https://www.spaceappschallenge.org/2025/find-a-team/photonic-force/); [Drive folder](https://drive.google.com/drive/folders/17Sjo9YEayU1WuYzge4OO2uTpEkqAI4ms).
- Team statement: about "lifting a child studying under a lantern in remote Ladakh to the same signal strength as a founder in Chennai" — [Meet the Winners](https://www.spaceappschallenge.org/2025/meet-the-2025-global-winners/).

#### Best Use of Storytelling: HerCode Space (A Solar Tale)
- Team: Alice R., Joselyn R., Paula C., Pierina J.; Universal Event, all four profiles list Peru; a self-described collective of women "turning data into meaningful stories" — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/); [team page](https://www.spaceappschallenge.org/2025/find-a-team/hercode-space/).
- Product: a digital children's story narrated by the Sun in five poetic acts, running from ancient myths and Galileo to modern solar impacts — [team page](https://www.spaceappschallenge.org/2025/find-a-team/hercode-space/).
- Sources: NASA web pages on solar storms and space weather, an NASA SVS item, and NOAA SWPC. These are reference pages, not processed datasets — [team page](https://www.spaceappschallenge.org/2025/find-a-team/hercode-space/).
- Stack: HTML5, SCSS, React, react-scrollama on Netlify, which makes this a scrollytelling build — [team page](https://www.spaceappschallenge.org/2025/find-a-team/hercode-space/).
- AI tools disclosed: Nano banana, Pixverse (spelled "Pixaverse"), Narakeet, Gemini, ChatGPT — [team page](https://www.spaceappschallenge.org/2025/find-a-team/hercode-space/).
- Method: no statistics or ML. The team's own highlights are narrative design, educational value, visual simplicity, and "Data Trust" from NASA/NOAA sourcing — [team page](https://www.spaceappschallenge.org/2025/find-a-team/hercode-space/).
- Demo: YouTube video "A Solar Tale - 2025 NASA Space Apps Challenge" on channel TheCatGirl17. The watch page returned a sign-in gate to my script, so length is unverified — [oEmbed](https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=1C9ueho9ero&format=json).
- Live site loaded (HTTP 200), a JavaScript shell I did not exercise — [site](https://a-solar-tale.netlify.app/).
- Team statement: "Our story brings together science, poetry, and history" — [Meet the Winners](https://www.spaceappschallenge.org/2025/meet-the-2025-global-winners/).

#### Global Connection: Gaia+LEO
- Team: Adam H., Katia L., Prajwal S., Upendra K.; event Seattle, WA — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/); [team page](https://www.spaceappschallenge.org/2025/find-a-team/gaialeo/).
- Product: a mixed-integer optimization that chooses where to place orbital and ground data centers and how to route workloads, minimizing CapEx plus OpEx under latency, bandwidth, power and thermal limits — [team page](https://www.spaceappschallenge.org/2025/find-a-team/gaialeo/).
- NASA data: POWER irradiance, temperature and humidity for 4 October 2023 to 4 October 2025. Other data: US EIA energy costs and CO₂, public data-center data, and the Starcloud white paper — [team page](https://www.spaceappschallenge.org/2025/find-a-team/gaialeo/).
- Assumption: each orbital module is a 40 MW solar-powered, radiatively cooled node — [team page](https://www.spaceappschallenge.org/2025/find-a-team/gaialeo/).
- Stack: Python, Three.JS, Streamlit. The repo holds `mip_model.py`, dashboard scripts and three notebooks — [team page](https://www.spaceappschallenge.org/2025/find-a-team/gaialeo/); [repo](https://github.com/stayingfoolish/gaia-LEO).
- Demo: 7-page PDF of 14 MB, "Gaia+LEO.pdf". The project link is the README, so no hosted app was listed — [Drive](https://drive.google.com/file/d/17eORY_V279WEXn_29pDwuUACGKpyKx6K/view); [team page](https://www.spaceappschallenge.org/2025/find-a-team/gaialeo/).

#### Art & Technology: Zumorroda-X (Henry's Farm Adventure)
- Team: Alaa A., Esraa A., Malak S., Mennatulla E.; event Cairo; computer engineering students at the German University in Cairo — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/); [team page](https://www.spaceappschallenge.org/2025/find-a-team/zumorroda-x/).
- Product: a pixel-art browser game. Henry visits farmers in India (2021 heat), Pakistan (2022 floods), Egypt (salinization), the United States (drought) and Brazil (crop management), with a mini-game or quiz at each stop — [team page](https://www.spaceappschallenge.org/2025/find-a-team/zumorroda-x/).
- NASA data: Earth Observatory Landsat before-and-after imagery, NDVI through APIs, IMERG, SEDAC extreme heat data, GISS crop-climate data, NASA Harvest GLAM. Other: U.S. Drought Monitor — [team page](https://www.spaceappschallenge.org/2025/find-a-team/zumorroda-x/).
- Note: the team calls the Drought Monitor "NASA's", though it is hosted by the University of Nebraska-Lincoln's domain — [team page](https://www.spaceappschallenge.org/2025/find-a-team/zumorroda-x/); [Drought Monitor](https://droughtmonitor.unl.edu/).
- Method: Phaser 3 game, an image slider, and a Python ML model that predicts crop survival from country, year, CO₂ and adaptation. Model type is not stated — [team page](https://www.spaceappschallenge.org/2025/find-a-team/zumorroda-x/); [repo README](https://raw.githubusercontent.com/esralsayed/Henry-s-Farming-Adventure-Game/main/README.md).
- Demo: 29.2-second MP4, "nasa demo.mp4", 66 MB — [Drive](https://drive.google.com/file/d/1P-sOTecG2uO2eLu3UabS0PXWLYUKaF4p/view).
- Live game page loaded (HTTP 200) and the repo is public. Its link now resolves to the renamed Henry-s-Farming-Adventure-Game — [game](https://henrysfarmadventures.vercel.app/); [repo](https://github.com/esralsayed/test_farmy).
- Team statement: "all we had was some programming experience" — [Meet the Winners](https://www.spaceappschallenge.org/2025/meet-the-2025-global-winners/).

#### Local Impact: QUEÑARIS
- Team: Borax Q., Carlos Y., Marcelo S., Máximo S., Oscar M., Pamela P.; event Arequipa. The page URL slug is `watana-project` — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/); [team page](https://www.spaceappschallenge.org/2025/find-a-team/watana-project/).
- Product: a decision-support system for restoring queñua (Polylepis) forests to protect Arequipa's water supply — [team page](https://www.spaceappschallenge.org/2025/find-a-team/watana-project/).
- NASA data: LP DAAC and Landsat vegetation indices (NDVI, EVI, NDMI, with SAVI and NBR references) via earthaccess. Other data: USGS EarthExplorer, ESA Earth Online, MTBS, DJI drone orthomosaics, and a local-news document — [team page](https://www.spaceappschallenge.org/2025/find-a-team/watana-project/).
- Method: drone and satellite integration with a Gemini-based analysis step to choose sites. No trained model or validation is described — [team page](https://www.spaceappschallenge.org/2025/find-a-team/watana-project/).
- Stack: Django/GeoDjango, PostgreSQL, Celery, React, Rasterio, GeoPandas, Metashape, QGIS — [team page](https://www.spaceappschallenge.org/2025/find-a-team/watana-project/).
- Real-world hook: 5,000 seedlings described as already prepared for a December field campaign, and a spring flow drop "from 14 L/s to 0 in days" (self-reported). Field outcome not verified — [team page](https://www.spaceappschallenge.org/2025/find-a-team/watana-project/).
- Oddity: the team's sector shares (agribusiness 28.5%, energy 67.7%, mining 11%) sum to more than 100% — [team page](https://www.spaceappschallenge.org/2025/find-a-team/watana-project/).
- Demo: 30-second YouTube video, 1,426 views when checked. Live site loaded (HTTP 200). No repo is listed — [YouTube](https://www.youtube.com/watch?v=QvbLhHqKULc); [site](https://quenaris.vercel.app).

### Inferences
- Live availability is weak evidence about 2025 judging, since judges saw these entries 13 months ago. SkySense's dead domain shows that link rot happens afterwards.
- A public repo was not a condition of winning. Only three of the ten surfaced a repo in the sources I checked.
- Two "demo" links being PDFs shows that slide-format entries reached Best Use of Technology and Global Connection.

### Gaps
- Actual video style (screen capture, narration, captions) was not assessed. Only metadata was read.
- A Solar Tale's video length, the SpaceGenes+ demo and the Photonics Canva deck are unverified.
- No repo was found for Resonant Worlds Explorer. A Product Hunt result called it open source, but I found no code link and no tie to Space Apps.
- Working-state testing was not done: "loaded" means an HTTP 200 and an expected page title, not that features work.

## Were there judges' citations?

### Takeaway
I found no published judges' citation for any 2025 winner. What exists is one generic line per award, NASA's editorial blurbs, and the teams' own statements.

### Cited Findings
- The awards page defines each award in a single sentence, for example Best Use of Storytelling: "The project that most creatively communicates the potential of open data through the art of storytelling" — [Awards](https://www.spaceappschallenge.org/2025/awards/).
- Best Use of Science: "The project that makes the best and most valid use of science and/or the scientific method" — [Awards](https://www.spaceappschallenge.org/2025/awards/).
- Best Use of Data: "The project that best makes space data accessible or leverages it for a unique application" — [Awards](https://www.spaceappschallenge.org/2025/awards/).
- Best Use of Technology: "The project that exemplifies the most innovative use of technology" — [Awards](https://www.spaceappschallenge.org/2025/awards/).
- Galactic Impact: "The project with the most potential to improve life on Earth or in the universe" — [Awards](https://www.spaceappschallenge.org/2025/awards/).
- Best Mission Concept: "The project with the most plausible concept and design" — [Awards](https://www.spaceappschallenge.org/2025/awards/).
- Most Inspirational: "The project that captures our hearts" — [Awards](https://www.spaceappschallenge.org/2025/awards/).
- Global Connection: "The project that best connects people around the world through technology" — [Awards](https://www.spaceappschallenge.org/2025/awards/).
- Art & Technology: "The project that most effectively combines technical and creative skills" — [Awards](https://www.spaceappschallenge.org/2025/awards/).
- Local Impact: "The project that demonstrates the greatest potential for local impact" — [Awards](https://www.spaceappschallenge.org/2025/awards/).
- The Global Winners page data repeats the Best Use of Technology sentence under Art & Technology, which looks like a site data error — [Global Winners](https://www.spaceappschallenge.org/2025/awards/global-winners/).
- The only person quoted in NASA's announcement is Karen St. Germain, on the challenge in general, not on any winner — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/).

### Inferences
- "Why it won" can only be inferred from the fit between each project and the one-line award definition. Any stronger claim would be invention.

### Gaps
- Scores, judges' names, and written feedback for 2025 were not found.

## What is common to winners, and what differs between awards? Which could a data-storytelling app target?

### Takeaway
The shared pattern is one specific audience, one clear question, and one memorable thing the viewer can do or see, built on named NASA sources. Awards differ sharply in how much technical depth they show, and a data-storytelling app fits Best Use of Storytelling, Art & Technology and Best Use of Data best.

### Cited Findings
- Three of ten winners came from one challenge, Commercializing LEO, under three different awards — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/).
- That challenge explicitly asked for a business model with a prototype, and all three winners framed economic or national-infrastructure value — [team page](https://www.spaceappschallenge.org/2025/find-a-team/gaialeo/); [team page](https://www.spaceappschallenge.org/2025/find-a-team/photonic-force/); [team page](https://www.spaceappschallenge.org/2025/find-a-team/astro-sweepers-we-catch-what-space-leaves-behind/).
- The Storytelling winner came from a challenge that directly asked for a digital children's story, and the Art & Technology winner from one that asked for an educational game — [HerCode](https://www.spaceappschallenge.org/2025/find-a-team/hercode-space/); [Zumorroda-X](https://www.spaceappschallenge.org/2025/find-a-team/zumorroda-x/).
- Earth-observation data drove three winners (SkySense, Henry's Farm Adventure, Queñaris), and Gaia+LEO also used POWER — [Twisters](https://www.spaceappschallenge.org/2025/find-a-team/twisters/); [Zumorroda-X](https://www.spaceappschallenge.org/2025/find-a-team/zumorroda-x/); [Queñaris](https://www.spaceappschallenge.org/2025/find-a-team/watana-project/); [Gaia+LEO](https://www.spaceappschallenge.org/2025/find-a-team/gaialeo/).
- Team sizes in NASA's list run from 1 to 6 — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/).
- Generative or no-code tools are openly disclosed by winners, including Bolt, Lovable, ChatGPT, Gemini, Nano banana, Narakeet, Cursor and ElevenLabs — [SpaceGenes+](https://www.spaceappschallenge.org/2025/find-a-team/spacegenes/); [HerCode](https://www.spaceappschallenge.org/2025/find-a-team/hercode-space/); [Gaia+LEO](https://www.spaceappschallenge.org/2025/find-a-team/gaialeo/); [PureFlow](https://www.spaceappschallenge.org/2025/find-a-team/pureflow2/).
- Technical depth by award, from the entries above: heaviest in Best Use of Data, Galactic Impact and Global Connection; a simple statistic in Best Use of Science; none in Storytelling — [Resonant](https://www.spaceappschallenge.org/2025/find-a-team/resonant-exoplanets/); [Astro Sweepers](https://www.spaceappschallenge.org/2025/find-a-team/astro-sweepers-we-catch-what-space-leaves-behind/); [Gaia+LEO](https://www.spaceappschallenge.org/2025/find-a-team/gaialeo/); [SpaceGenes+](https://www.spaceappschallenge.org/2025/find-a-team/spacegenes/); [HerCode](https://www.spaceappschallenge.org/2025/find-a-team/hercode-space/).
- Three winners feature a named place or person at human scale: Arequipa's water, a child in Ladakh, and Henry the farmer — [Queñaris](https://www.spaceappschallenge.org/2025/find-a-team/watana-project/); [Meet the Winners](https://www.spaceappschallenge.org/2025/meet-the-2025-global-winners/); [Zumorroda-X](https://www.spaceappschallenge.org/2025/find-a-team/zumorroda-x/).
- No winner's listed sources mention SAR or NISAR data — [Global Winners team pages via Meet the Winners](https://www.spaceappschallenge.org/2025/meet-the-2025-global-winners/).

### Inferences

| Award | Fit for a data-storytelling app | Reasoning from 2025 evidence |
|---|---|---|
| Best Use of Storytelling | Strongest | The definition is about open data and story. A Solar Tale is a scrollytelling precedent, though it used no processed dataset, so a story on real processed data could exceed it. |
| Art & Technology | Strong | Henry's Farm Adventure paired real satellite imagery and before/after comparison with a narrative. |
| Best Use of Data | Strong if data work is real | "Makes space data accessible" is half the definition, but the 2025 winner was a deep pipeline. Accessibility alone may not match that depth. |
| Local Impact | Conditional | Fits only with a specific place, a stakeholder, and a concrete local stake, as with Queñaris. |
| Best Use of Science | Conditional | SpaceGenes+ shows a simple, transparent statistic plus good visualization can win if the science is valid. |
| Most Inspirational | Possible | Rests on emotional clarity, not build depth, per AakashNet. Hard to plan for. |
| Galactic Impact | Weak to moderate | The 2025 winner offered a quantified system-level benefit and a business case. |
| Global Connection | Weak | The criterion is connecting people through technology, and the 2025 winner was an optimization model, so the pattern is unclear. |
| Best Use of Technology | Weak | Rewards novelty of the build. |
| Best Mission Concept | Poor | Requires a plausible engineered concept. |

- Challenge choice appears to shape award fit. The Storytelling and Art & Technology winners answered challenges that asked for that form. This is based on one year and ten projects.
- The strongest copyable element is PureFlow's single test question, and Astro Sweepers' single worked before-and-after case.
- With ten awards, one example per award cannot establish what judges reward. These are patterns, not rules.

### Gaps
- Whether teams nominate themselves for a specific award or judges assign awards could not be confirmed, because the 2025 guide was unavailable.
- Finalist and Honorable Mention project lists load client-side and were not extracted, so I cannot say how these winners differ from the 58 near-misses.

## What were the 2025 judging criteria and scoring process?

### Takeaway
The funnel is well documented: 11,500+ submissions, 1,290+ Global Nominees, 45 Global Finalists plus 23 Honorable Mentions, then 10 winners. The exact 2025 rubric could not be read directly, because the guide page is no longer served. Earlier editions name five criteria, and the demo limit is 30 seconds or 7 slides, with 2025 winners matching that limit.

### Cited Findings
- Submissions: 11,500+, from 114,000+ participants at 551 local events in 167 countries and territories — [NASA](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/).
- Stage 1: Local Event and Universal Event judges choose the Global Nominees — [Awards](https://www.spaceappschallenge.org/2025/awards/).
- Nominees: "1,290+ projects", with the page placeholder giving 5 November as the announcement date — [Global Nominees](https://www.spaceappschallenge.org/2025/awards/global-nominees/).
- Stage 2: NASA and Space Agency Partner subject matter experts review all nominees to pick Finalists and Honorable Mentions — [Awards](https://www.spaceappschallenge.org/2025/awards/).
- Finalists: 45, announced 26 November 2025 — [Global Finalists](https://www.spaceappschallenge.org/2025/awards/global-finalists/).
- Honorable Mentions: 23, described as highly ranked but not advancing to Executive Judging — [Honorable Mentions](https://www.spaceappschallenge.org/2025/awards/honorable-mentions/).
- Stage 3: an executive committee of NASA and partner agency leaders picks 10 winners, announced 18 December 2025 — [Awards](https://www.spaceappschallenge.org/2025/awards/).
- Calculated rates: nominees about 11% of submissions; finalists about 3.5% of nominees; winners about 22% of finalists; winners about 0.09% of submissions — derived from [Global Nominees](https://www.spaceappschallenge.org/2025/awards/global-nominees/), [Global Finalists](https://www.spaceappschallenge.org/2025/awards/global-finalists/) and [Global Winners](https://www.spaceappschallenge.org/2025/awards/global-winners/).
- Hackathon dates and submission window: 4 to 5 October 2025, closing 11:59 PM local time on 5 October — [NASA Terra](https://terra.nasa.gov/news/terra-animation-celebration-2025-space-apps-challenge).
- Criteria from older guides, as reported by search summaries: impact, creativity, validity, relevance, presentation. Not read directly — [2021 guide](https://sa-2019.s3.amazonaws.com/media/documents/Space_Apps_2021_Judging_and_Awards_Guide.pdf).
- Older materials and third parties may say "influence" instead of "impact", for example a 2024 guide summary — [Scribd copy of 2024 guide](https://www.scribd.com/document/876777314/Judging-Awards-Guideline).
- A 2024 version of the guide is reported to tell teams to give presentation equal attention to the first four criteria — [Judging guide](https://spaceappschallenge.org/resources/judging-awards-guide).
- Demo limit: "7 slides or a 30-sec video", from an official post dated to the 2024 cycle by its ID, and in the 2022 guide as reported by search — [Space Apps on X](https://x.com/SpaceApps/status/1843038095727350234); [2022 guide](https://spaceapps-prod.s3.amazonaws.com/media/documents/Space_Apps_2022_Project_Submission_Guide.pdf).
- A 2025 winner's text carries a link fragment from the Project Submission Guide reading "This demo will be considered ... category of the judging rubric", which suggests the demo is scored — [Astro Sweepers](https://www.spaceappschallenge.org/2025/find-a-team/astro-sweepers-we-catch-what-space-leaves-behind/).
- 2025 winners match the limit on the evidence above: videos of 29, 29.2, 30, 30 and 30.5 seconds, and PDFs of 6 and 7 pages.
- Universal Event projects are compared only with other Universal Event projects, and teams are capped at six. This is stated in the 2026 FAQ, not a 2025 source — [Participant FAQs](https://www.spaceappschallenge.org/resources/participant-faqs/).

### Inferences
- Two of ten winners came through the Universal Event. If the 2026 FAQ's rule also held in 2025, those nominees were selected in a separate comparison pool.
- The headings in winners' text ("Creativity and Innovation", "Design Considerations", "What benefits does it have?") suggest shared 2025 submission form prompts, and teams writing to them.
- The 30-second limit makes the demo a hook. The long project page then has to carry the full argument, as Astro Sweepers' 27,000-character text does.

### Gaps
- The 2025 Judging and Awards Guide and Project Submission Guide were not obtainable. Their `/resources/` URLs now return the site's not-found page, and the 2026 FAQ says new guides arrive on 13 November 2026. The Wayback Machine could not be reached with WebFetch.
- The 2025 scoring scale, weights, and tie-breaking are unverified. I omit them instead of reporting unconfirmed figures.
- The 2021 and 2022 PDFs saved locally could not be parsed for text, so those older criteria rest on search summaries.
- The rule that NASA data is required for global awards appears only in a third-party 2026 starter kit, so it is unconfirmed for 2025 — [space-apps-kit](https://github.com/PA-Andries/space-apps-kit).
