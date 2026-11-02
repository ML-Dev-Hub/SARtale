# SAR entries in NASA Space Apps 2023–2025 and the 2026 "Dancing with the SARs" challenge

*How the data was collected (2 Nov 2026).* The challenge statements come from the Space Apps pages, decoded from the page payload. Team and project records come from the site's own public GraphQL endpoint (`https://api.spaceappschallenge.org/graphql`), which the site calls anonymously. The query shapes were copied from the site's JavaScript. Only team, project, badge and award fields were requested; member personal data was not. TLS verification stayed on throughout. certifi lacks the Comodo "AAA Certificate Services" root this site chains to, so Git's bundled CA file was added to the trust store. Team-page URLs follow the site pattern `/{year}/find-a-team/{slug}/`, which I confirmed for 2023 (`girl-power`), 2025 (`tengrispacers`) and 2024 (`/nasa-space-apps-2024/find-a-team/...`). Project descriptions are self-reported by teams. Where I say "the text says", I mean the team's claim, not something I checked independently. I did not watch the demo videos.

## Q1. Which SAR challenges ran in 2023, 2024 and 2025, and what did they ask for?

### Takeaway
There were two SAR-titled challenges: 2023's "Create a Work of SARt (Synthetic Aperture Radar Art)" (an art brief) and 2025's "Through the Radar Looking Glass: Revealing Earth Processes with SAR" (a science-interpretation brief). **2024 had no SAR challenge.** SAR appeared only as a listed resource in a few other challenges in 2023–2025. "Dancing with the SARs" (2026) is the third SAR challenge and the first built around NISAR data.

### Cited Findings
- The site's challenge catalogue lists 86 challenges across 2023–2026. Only three have SAR or radar in the title or excerpt: "Create a Work of SARt (Synthetic Aperture Radar Art)", "Through the Radar Looking Glass: Revealing Earth Processes with SAR" and "Dancing with the SARs". Per-year page counts: 2023 = 32, 2024 = 21, 2025 = 19, 2026 = 14. — [Space Apps 2025 challenges](https://www.spaceappschallenge.org/2025/challenges/); [2024 challenges](https://www.spaceappschallenge.org/nasa-space-apps-2024/challenges/); [2023 challenges](https://www.spaceappschallenge.org/2023/challenges/)
- I scanned the text of every challenge page for SAR terms. Outside the three SAR challenges, SAR appears only as background or resources:
  - 2023 "Be a Space Geologist" offers UAVSAR volcano warning as one option.
  - Several 2023 Earth challenges carry a stock paragraph about the Canadian RADARSAT Constellation Mission (Everything Starts with Water, GeoAI Reimagined, ISS VISION-aries, Managing Fire, NASA in Your Neighborhood).
  - 2024 "Leveraging Earth Observation Data for Informed Agricultural Decision-Making" lists "Floods: OPERA, Synthetic Aperture Radar (SAR)" as a resource.
  - 2024 "Imagine our Connected Earth" links a "Synthetic Aperture Radar Tutorial" (RADARSAT).
  - Several 2025 challenges carry a RADARSAT-1 paragraph.
  - Sources: [Be a Space Geologist (2023)](https://www.spaceappschallenge.org/2023/challenges/be-a-space-geologist/); [Leveraging EO for Agriculture (2024)](https://www.spaceappschallenge.org/nasa-space-apps-2024/challenges/leveraging-earth-observation-data-for-informed-agricultural-decision-making/); [Imagine our Connected Earth (2024)](https://www.spaceappschallenge.org/nasa-space-apps-2024/challenges/imagine-our-connected-earth/)
- **2023, "Create a Work of SARt":**
  - Event dates: 7–8 Oct 2023.
  - Summary: "Your challenge is to bring complex SAR data down to Earth by creating innovative artwork that highlights the unique perspective of SAR sensors. Create a digital art piece (image, video, 3D model, etc.) based on SAR imagery and related products—a work of SARt!"
  - Objective: "develop a publicly accessible work of SARt that portrays the radar imagery in a new, creative way". Accepted media: "imagery, video, 3D model, music, (a picture of) a diorama, etc."
  - Teams had to include "a text description the data you used, how the art piece was generated, and how it represents the data".
  - Data: teams were to use "datasets similar to those that NISAR will provide". It also says "Beginner SAR users may start with the … UAVSAR postcards".
  - It states the judging basis: "judged by NASA experts based on creativity, innovation, and clarity", with "Clarity: Does the SARt-work clearly depict the Earth process(es) being shown?"
  - Source: [2023 SARt challenge](https://www.spaceappschallenge.org/2023/challenges/create-a-work-of-sart-synthetic-aperture-radar-art/)
- **2025, "Through the Radar Looking Glass":**
  - Event dates: 4–5 Oct 2025.
  - Summary: "download multi-frequency or multi-polarization SAR data for an interesting study area of your choice … and use that data to develop hypotheses about the physical drivers operating there."
  - Objectives: "analyzing radar remote sensing data from SAR instruments that employ different polarizations and frequencies to reveal information about physical drivers on Earth". Also: "don't forget to use SAR data with different polarizations and frequencies in your project!" and "What can you hypothesize about the physical drivers behind what you see (or don't see) in the SAR data?"
  - Presentation: "any digital medium you prefer: a final report, video, presentation slides, StoryMap, or even a riddle!"
  - Background stresses that "sensors employing different frequencies/wavelengths (e.g., C-band, L-band, P-band, etc.) provide data from varying penetration depths".
  - Optional considerations: time series, optical/GIS context, human drivers, hometown stories, interactivity ("image sliders, web maps").
  - Source: [2025 Looking Glass challenge](https://www.spaceappschallenge.org/2025/challenges/through-the-radar-looking-glass-revealing-earth-processes-with-sar/)
- The 2025 page links these resources: ASF Vertex, NASA Earthdata Search, ARSET "Introduction to SAR and its Applications", NISAR ArcGIS StoryMaps and societal-benefit pages, UAVSAR postcards, the CONAE SAOCOM catalogue, CSA open data (RCM), INPE's catalogue, and Earthdata "SAR" basics. — [2025 Looking Glass challenge](https://www.spaceappschallenge.org/2025/challenges/through-the-radar-looking-glass-revealing-earth-processes-with-sar/)
- Participation:
  - 2023 SARt: 116 teams, of which 73 submitted projects.
  - 2025 Looking Glass: 306 teams, of which 200 submitted.
  - 2026 Dancing with the SARs: 605 teams registered as of 2 Nov 2026, with no submissions yet (the hackathon has not started).
  - Sources: [2023 SARt teams](https://www.spaceappschallenge.org/2023/challenges/create-a-work-of-sart-synthetic-aperture-radar-art/?tab=teams); [2025 teams](https://www.spaceappschallenge.org/2025/challenges/through-the-radar-looking-glass-revealing-earth-processes-with-sar/?tab=teams); [2026 teams](https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/?tab=teams)

### Inferences
- The three SAR challenges show a clear progression: art and communication (2023), then physical interpretation across polarisations and frequencies (2025), then an interactive change-tracking application on NISAR data (2026). The same author voice and paragraphs carry through all three, which suggests the same NASA challenge owner. The owner is not named on the pages.
- 2026 already has about twice 2025's team count two weeks before the event. The SAR challenge will be crowded, so differentiation matters more than in 2025.

### Gaps
- The challenge pages do not name the challenge-writing scientists or teams.
- The 2023 and 2025 "Resources" tabs are partly client-rendered. I recovered the resource URLs from the 2025 page, but not the full 2023 resource list.

## Q2. Full text of the 2026 "Dancing with the SARs" challenge, and how it differs

### Takeaway
2026 makes NISAR the mandatory data source and asks for an interactive, open-source application that tracks surface change over time. It keeps 2025's "hypothesize the physical drivers behind what you see (or don't see)" and the playful presentation options, but drops the requirement to compare multiple frequencies and polarisations. Resources open on Friday 13 November 2026.

### Cited Findings
- Full statement text, verbatim from the page payload:
  - **Summary:** "Earth's surface is an endless dance of natural processes and human activities, but these changes are often difficult to visualize, understand, and communicate. From wetland loss to forest wildfires, earthquakes, farming activities, glacier movement, and more, Earth is in a constant waltz of surface changes. Your challenge is to build an interactive application that uses radar remote sensing data from the NASA-ISRO Synthetic Aperture Radar (NISAR) mission to track and visualize one or more types of surface change at locations around the world."
  - **Background (1):** "Earth remote sensing helps us acquire information from a bird's eye view. Space-borne and airborne instruments image the planet and contribute to Earth observations that help decision makers in lieu of or supplement their field surveys. The most common source of energy that these instruments use is from the Sun, which reflects from objects and surfaces on the ground back to the instrument. The amount of this energy varies by the wavelength within the electromagnetic spectrum, and we can use this spectral fingerprint to identify water, rocks/minerals, vegetation, etc. These instruments that utilize the Sun's energy conduct passive remote sensing while radar instruments, such as those we'll use in this challenge, conduct active remote sensing."
  - **Background (2):** "Active instruments emit and receive their own source of energy, and in the case of radar, operate in the microwave band of the electromagnetic spectrum. Radar instruments can be used to study forest structure, soil moisture, wetlands, ocean topography, sea ice, and more. In this challenge, we will download data from SAR (synthetic aperture radar) satellites. SAR "synthesizes" a long antenna by combining a sequence of acquisitions from its actual, shorter antenna to provide higher spatial resolution data. SAR instruments send out a pulse of energy which reacts with the Earth's surface and is reflected back to the instrument. This collection can be done day or night and even in cloudy weather, which allows for critical data collection during disaster events like oil spills, wildfires, hurricanes, etc."
  - **Background (3):** "Radar data is most sensitive to two things: roughness and the dielectric constant. In other words, the radar images are more than just typical satellite images that you may see with your GPS app. This roughness information characterizes the backscatter from Earth's surface and different polarizations and can tell us something about structure, geometry, and material properties. Since water has a high dielectric constant, SAR data also highlights water bodies, flood inundation, and soil moisture. SAR can also measure fine surface movement on the centimeter scale, such as for earthquakes and land subsidence."
  - **Objectives (1):** "On Earth's surface there is an endless dance of natural processes and human activities in constant motion, but these changes are often difficult to visualize, understand and communicate. Wetlands and floodplains are constantly extending and retracting; forest footprints are shrinking from deforestation and wildfires; agricultural lands transform their crop types and health, moisture is swelling and shrinking in soils; glaciers and sea ice are in a constant waltz; and land surfaces are deforming from earthquakes and coastal subsidence. All of these changes have important implications for ecosystems, water resources, agriculture and infrastructures, ultimately impacting local communities."
  - **Objectives (2):** "In this challenge, participants will build an interactive application that leverages radar remote sensing data from NISAR to track and visualize one or more types of surface changes, at locations around the world. Participants are encouraged to design intuitive tools and innovative visualizations, such as interactive change-detection maps, time-series animations, or dashboards, that make NISAR data accessible to a broad audience. The desired outcome is an open-source, user-friendly solution that translates complex radar observations into actionable insights, helping scientists, resource managers, educators, decision-makers, and the public better understand the patterns and rhythms of Earth's surface at different time steps."
  - **Objectives (3):** "First, pick an interesting study area – this can be your hometown, a tropical wetland, ice sheet, forest wildfire, flooded neighborhood, volcano eruption, etc. - wherever the music calls you! Second, download freely available NISAR data using the list of resources provided. You may want to download supplemental data such as optical images or GIS (geographic information systems) layers to contextualize the SAR imagery. And lastly, present your findings in an interactive digital medium you prefer: a final report, video, presentation slides, story map - even an interpretive dance? Hypothesize the physical drivers behind what you see (or don't see) in the SAR data. For example, if you are looking at the Amazon Rainforest, why might the vegetation change over time? Which polarizations highlight these changes on land and ice? What future applications of NISAR are possible?"
  - **Potential Considerations:** "You may (but are not required to) consider the following:"
    - "Analyze NISAR data with different polarizations and/or different frequencies (from other sensors). Download data from different dates to show a time series and ancillary datasets (population, vegetation type, etc.) to contextualize the study area."
    - "Show how human drivers (agriculture, industry, etc.) are impacting Earth's natural resources."
    - "Focus on compelling storytelling through data visualizations. Your project summary can be in any digital medium you prefer: a final report, video, presentation slides, story map, etc."
    - "If you are familiar with your study area (e.g., it's your hometown), you can provide personal context and stories for the SAR imagery."
    - "Consider making your summary interactive (e.g., image sliders, web maps, etc.)."
  - Closing note: "For data and resources related to this challenge, refer to the Resources tab at the top of the page. More resources may be added before the hackathon begins."
  - Resources tab: "Resources will be available on Friday, November 13."
  - Hero image caption: "NISAR satellite illustration showing Mount Rainier on Nov. 10, 2025, with L‑band SAR revealing the surface through clouds."
  - Subject tag: "Earth Science". Page created 17 Sep 2026; last updated 28 Oct 2026.
  - Source: [2026 Dancing with the SARs](https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/)
- Differences from 2025, each from the two statement texts ([2026](https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/) vs [2025](https://www.spaceappschallenge.org/2025/challenges/through-the-radar-looking-glass-revealing-earth-processes-with-sar/)):
  - **Data:**
    - 2026 requires NISAR: "uses radar remote sensing data from the … NISAR mission" and "download freely available NISAR data".
    - 2025 allowed any public SAR (ASF, SAOCOM, RCM, INPE) and required "different polarizations and frequencies".
    - In 2026, multiple frequencies are optional and come "from other sensors".
  - **Deliverable:**
    - 2026 wants "an interactive application" and "an open-source, user-friendly solution". It names "interactive change-detection maps, time-series animations, or dashboards".
    - 2025 asked teams to "present your findings" in any medium (report, video, slides, StoryMap, riddle).
    - 2023 asked for an art piece.
  - **Core task:**
    - 2026 is change tracking "at different time steps", with one or more change types: wetlands and floodplains, deforestation and fire, crops, soil moisture, glaciers and sea ice, earthquake and subsidence deformation.
    - In 2025 the core was polarisation and frequency contrast ("data in each frequency reveals a different clue"). Time series were only an option.
  - **Kept from 2025:**
    - "Hypothesize the physical drivers behind what you see (or don't see)".
    - The Amazon example.
    - "Which polarizations highlight these changes…?"
    - Hometown stories, optical/GIS context, human drivers, interactivity, storytelling.
  - **New in 2026:**
    - "What future applications of NISAR are possible?"
    - The explicit audience list: "scientists, resource managers, educators, decision-makers, and the public".
    - "actionable insights".
    - The InSAR hint: "SAR can also measure fine surface movement on the centimeter scale, such as for earthquakes and land subsidence".
  - **Dropped from 2025:**
    - The wavelength and penetration-depth paragraph (C-, L-, P-band; canopy layers).
    - The "Alice" riddles, "why does the city look pink and white? The rivers black?".

### Inferences
- "Interactive application", "open-source" and "time steps" together mean a static story map or video will match the 2026 brief less well than it matched 2025's. The brief still allows "a final report, video … story map" as the medium of the *summary*. Judges will likely expect a working app plus a summary.
- NISAR is single-platform (L-band, plus S-band over some areas). Teams that want frequency contrast must bring in a second sensor, such as Sentinel-1 C-band, and say why.

### Gaps
- The 2026 Resources list was not published as of 2 Nov 2026. I therefore cannot say which NISAR products (e.g., GCOV, GSLC, GUNW) or which time span will be recommended.
- I did not verify which NISAR science products are public right now. The NISAR launch date and product release schedule were not checked in this session.

## Q3. Strongest entries: team, country, level, award, method, data, validation, demo, repo

### Takeaway
No SAR-challenge team won a global award in 2023, 2024 or 2025. The highest SAR-challenge results were Global Finalist:
- 2023: SARcologists (USA), a physical robot model of the NISAR spacecraft.
- 2025: TengriSpacers (Kyrgyzstan), a Sentinel-1 glacier-change pipeline.

Global Honorable Mentions:
- 2023: SARtists (South Africa) and Scientist-Astronauts (USA).
- 2025: FarmHubGlobal (France).

In 2024, with no SAR challenge, SAR-based flood entries in "Community Mapping" earned a People's Choice award and an Honorable Mention.

### Cited Findings
**Global winners.** The award pages list 10 award categories with 3 winning teams each, 30 teams in all. None is from a SAR challenge.
- Examples: Best Use of Data went to GaamaRamma (Leveraging EO for Agriculture), Resonant Exoplanets (A World Away) and Storm Prophet (Oracle of DSCOVR). Local Impact went to $quality_over_quantity, QUEÑARIS and Team I.O. (Community Mapping).
- A keyword scan of all 30 winners' project text found no mention of SAR, Sentinel-1, NISAR, UAVSAR, backscatter or InSAR.
- Sources: [2025 Global Winners](https://www.spaceappschallenge.org/2025/awards/global-winners/); [2023 awards](https://www.spaceappschallenge.org/2023/awards/)

**Badge counts.**
- 2023 SARt: 7 Global Nominees. Of these, 1 became a Global Finalist and 2 received "Global Finalist Honorable Mention".
- 2025 Looking Glass: 36 Global Nominees. Of these, 1 became a Global Finalist and 1 received an Honorable Mention.
- Source: team records behind the [2023](https://www.spaceappschallenge.org/2023/challenges/create-a-work-of-sart-synthetic-aperture-radar-art/?tab=teams) and [2025](https://www.spaceappschallenge.org/2025/challenges/through-the-radar-looking-glass-revealing-earth-processes-with-sar/?tab=teams) teams tabs.

**2025 Global Finalist: TengriSpacers (Kyrgyzstan), "Project TengriSpacers".** Source: [team page](https://www.spaceappschallenge.org/2025/find-a-team/tengrispacers/); repo [Apelsinovich/GlacierSAR-Kyrgyzstan](https://github.com/Apelsinovich/GlacierSAR-Kyrgyzstan); demo: Google Slides.
- What it is: "An APP (no UI) that shows how Kyrgyzstan's glaciers are melting now - and how they may change next".
- Method, as stated: "We process Sentinel-1 time series to get change maps, trends, and confidence bands. A trained LSTM … model adds short-term forecasts." Also: "Ingest Sentinel-1 scenes → clean, align, terrain-correct. Compute backscatter/coherence change and basic masks (elevation/aspect). Output maps, charts, % loss, and a GLOF watchlist."
- Stack: Python CLI (NumPy, SciPy, rasterio), QGIS, SNAP. Outputs are GeoTIFF/GeoJSON/CSV.
- Results claimed for Golubin Glacier: "2016–2025: glacier tongue shrank by ~1–2% (tongue section only). Forecast to 2050 (pessimistic): up to ~30% loss vs 2015." Caveat stated: "real loss is higher due to thinning and side retreat."
- The repo README (8 commits) describes things the project text doesn't:
  - The README itself mentions DINOv3 segmentation, GMM clustering, Random Walker boundaries, and polynomial / Random-Forest per-pixel prediction, rather than LSTM.
  - It gives no quantitative results and no validation method.
  - Source: [repo](https://github.com/Apelsinovich/GlacierSAR-Kyrgyzstan)

**2025 Honorable Mention: FarmHubGlobal (France).** Source: [team page](https://www.spaceappschallenge.org/2025/find-a-team/farmhubglobal/); app built with Lovable at field-insight-cloud.lovable.app; YouTube demo.
- What it is: a mobile web app where farmers draw fields and get irrigation, compaction and fertilisation maps "by analyzing SAR data".
- Its only SAR reference is one Earthdata collection link (ASF collection C1214470488). It names no processing steps or polarisations and describes no validation.
- It credits Lovable.ai and AI code generation ("AI also supported the generation of our TypeScript and HTML code").

**2023 Global Finalist: SARcologists (USA), "SAR Satellite Building Kit".** Source: [team page](https://www.spaceappschallenge.org/2023/find-a-team/girl-power/).
- What it is: "Inspired by the NISAR … satellite", the team built a VEX IQ robot model of the spacecraft and a Studio 2.0 3D model with build instructions, "so that every child could assemble and build the robot".
- No SAR imagery was processed. The data cited is educational pages (Earthdata "What is SAR?", UAVSAR postcards, ARSET).

**2023 Global Finalist Honorable Mention: SARtists (South Africa), "Dragon of the East".** Source: [team page](https://www.spaceappschallenge.org/2023/find-a-team/sartists/); site sartists.netlify.app.
- What it is: a digital art piece over the Karbala region of Iraq, plus "a time-lapse video [of] SAR data from 2018 to 2023". It highlights centre-pivot irrigation growth, water levels and urban change.
- Data: EO Browser / Copernicus.
- Presentation: a website, a video and a PowerPoint.

**2023 Global Finalist Honorable Mention: Scientist-Astronauts (USA), "Scientist-Astronauts Make SARt".** Source: [team page](https://www.spaceappschallenge.org/2023/find-a-team/scientist-astronauts/); repo [meryemberradauwo/SARt](https://github.com/meryemberradauwo/SARt); YouTube video.
- Data and processing: Sentinel-1 processed in Google Earth Engine ("calibration and transformation"), with "different polarization layers". Examples include the Galápagos as a seahorse and Kantubek as a heart, Himalayan melt, and the Kedarnath landslide.
- Outputs: a 3D Earth model, an "advertisement video", and downloadable postcards with QR codes linking to a SAR map.

**2025 Global Nominees with the deepest SAR content.** None advanced past nominee.
- **Arapua Labs (Brazil), Lençóis Maranhenses.** Source: [team](https://www.spaceappschallenge.org/2025/find-a-team/arapua-labs/); arapualabs.com; YouTube.
  - Sentinel-1 GRD in GEE: wet- and dry-season median mosaics, "Otsu thresholding … directly to the linear VV polarization" for water versus sand, and focal-mode speckle cleanup.
  - VV amplitude prepared for a Python step that computes "2D displacement vectors of the dunes (m/yr)".
  - Lagoon area was correlated with rainfall and dune movement with wind "for the scientific validation and attribution". Reported lagoon change: 169.6 km² (623.4 km² wet season vs. [dry]).
- **SAR Monsters (USA), "The DryPath Map".** Source: [team](https://www.spaceappschallenge.org/2025/find-a-team/sar-monsters/); drypathmap.com.
  - Fuses GPM IMERG rain, Sentinel-1 VV/VH and elevation to find flooded roads, then routes around them with OSRM. Demo case: Kerrville, Texas.
  - "Where available, we add L-band and UAVSAR overlays to distinguish open water from flooded vegetation under canopy."
  - "We validate the flood mask with IoU and precision/recall, measure lead time from IMERG triggers to SAR confirmation".
- **UpIT (Uruguay), "InSAR Monitor".** Source: [team](https://www.spaceappschallenge.org/2025/find-a-team/upit/); nasa-insar.streamlit.app.
  - Sentinel-1 via `asf_search`, PS-InSAR, "coherence thresholds (minimum 0.3)", 8 years over Montevideo, and "40+ GB real Sentinel-1 imagery from Bangkok, CDMX, Montevideo".
  - Interface: Streamlit/Plotly 3D dashboard.
- **Brave New World (Vietnam), InSAR subsidence and erosion in northern Vietnam.** Source: [team](https://www.spaceappschallenge.org/2025/find-a-team/brave-new-world/); repo [ltkdt/sparc_sar_demo](https://github.com/ltkdt/sparc_sar_demo).
  - Uses ASF Search API with InSAR and GIS. Cites GMTSAR Sentinel time-series documentation.
- **Surface Sleuths ("Anywhere in the World"), Reykjanes volcano.** Source: [team](https://www.spaceappschallenge.org/2025/find-a-team/surface-sleuths/); repo [Yasaswini-ch/reykjanes-sar-analysis](https://github.com/Yasaswini-ch/reykjanes-sar-analysis).
  - 9 Sentinel-1 scenes via ASF HyP3 RTC, May 2024 to Sept 2025, covering 6 eruption episodes. Uses VH/VV ratio classes and roughening/smoothing change maps.
  - Statistics: "mean change 0.00 dB" scene-wide versus "Up to ±28 dB where eruptions occurred".
  - The README states limitations: "Small lava flows (<5% of scene) result in subtle overall statistics"; "Single orbit track; ascending and descending would improve coverage"; C-band sees only the surface.
  - It claims ">90% accuracy" with no test design.
  - Interface: interactive web map (reykjanes.netlify.app).
- **Yekta (Turkey), Denizli.** Source: [team](https://www.spaceappschallenge.org/2025/find-a-team/yekta/).
  - "Sentinel-1 GRD data (Denizli-focused, 150 scenes)" over 2014–2025, processed with SNAP and Python, speckle filtering, "Change vectors (±0.5 dB threshold)" and Random Forest hypotheses.
  - Findings: VV −12 to −13.5 dB and VH −20 to −23 dB; "ΔVV = -0.8 dB" linked to drought; "-0.3 dB drop after the 2019 Acıpayam (Mw 5.5) earthquake due to micro-cracks".
  - Limitations stated: "C-band penetration and 10m resolution. InSAR integration is recommended."
  - Interface: Leaflet, Flask and PostgreSQL.
- **Cea-SAR (Ireland), "The Shannon Pulse".** Source: [team](https://www.spaceappschallenge.org/2025/find-a-team/moonalisa/); repo [Mogboella/CeeSAR](https://github.com/Mogboella/CeeSAR).
  - Sentinel-1 VV/VH in GEE and QGIS over 2015–2024: flood extent, persistent inundation, "backscatter threshold analysis", and "real-time data from ground-truth sensors" planned for AI forecasting.
- **npSAR (Nepal), glacial-lake GLOF watch.** Source: [team](https://www.spaceappschallenge.org/2025/find-a-team/pns/); np-sar-web.vercel.app; YouTube.
  - Sentinel-1A/B via ASF and HyP3 RTC with speckle filtering. About 250–300 image-mask pairs train an EfficientNet-B3 CNN, which tracks lake area over years.
- **Lost Frequencies (Spain), Mar Menor pollution sources.** Source: [team](https://www.spaceappschallenge.org/2025/find-a-team/lost-frequencies/); repo linked on page.
  - VH dB difference between two periods for agricultural change: "Water pixels (VH < -22 dB) are masked to prevent differences caused by water." Uses flood/dry reference-image comparison.
  - Interface: React and Leaflet multilayer viewer.
- **Explorer_J1K2R1 (Canada), Magdalen Islands erosion.** Source: [team](https://www.spaceappschallenge.org/2025/find-a-team/explorer_j1k2r1/); repo [MrCreeperman147/NASASpaceApp2025](https://github.com/MrCreeperman147/NASASpaceApp2025).
  - Sentinel-2 timeline plus an InSAR map using Liège's AMSTer toolbox.
  - States that the InSAR widget cannot show the selected island without RADARSAT-2 and more processing time.
- **Hacker Mates (Argentina), Andes snow state.** Source: [team](https://www.spaceappschallenge.org/2025/find-a-team/hacker-mates/); live GEE app.
  - Sentinel-1 VV per pixel classes dry snow, wet snow and ice; optical NDSI > 0.4 masks the snow.
- **Tigris Bilsem (Turkey), "ASMAN".** Source: [team](https://www.spaceappschallenge.org/2025/find-a-team/tigris-bilsem/); repo [tigris-bilsem/asman](https://github.com/tigris-bilsem/asman).
  - Random Forest regressor forecasting a post-fire "impact profile" (NDVI, LST and "SAR backscatter"), with pyroSAR, SNAP and GEE.
- **Astroos (Egypt), 2023 Derna flood story.** Source: [team](https://www.spaceappschallenge.org/2025/find-a-team/astroos1/).
  - SNAP flood-extent and "coherence-change maps" before, during and after the flood, with an optical-vs-radar side-by-side.

**2024 SAR entries in non-SAR challenges.** A scan of 6 Earth challenges (about 3,366 submissions) found 35 projects mentioning SAR terms. Most were passing mentions.
- **Team_CoolMappings (Brazil), "FloodMapRS".** Community Mapping; **2024 People's Choice**. Source: [team](https://www.spaceappschallenge.org/nasa-space-apps-2024/find-a-team/team_coolmappings_maceio/); kikosmoura.github.io/nasa_2024; YouTube.
  - "Leveraging Synthetic Aperture Radar (SAR) satellite data from Sentinel-1, the model accurately delineates flooded regions". Builds a flood probability map for Rio Grande do Sul.
- **Urban Utopians (Bangladesh), "GeoAID".** Community Mapping; **2024 Global Nominee and Honorable Mention**. Source: [team](https://www.spaceappschallenge.org/nasa-space-apps-2024/find-a-team/urban-utopians/); repo [Mustaqeem01/GeoAID](https://github.com/Mustaqeem01/GeoAID).
  - Uses "Flood Intensity Data From Sentinel-1 SAR GRD" with poverty and built-up layers for fair aid distribution.
- Others:
  - Hansa (USA), "Mobile Flood Map": Sentinel-1 and AWS Lambda; repo [labwhisper/FloodView](https://github.com/labwhisper/FloodView).
  - Making waves (India), "SAR Image Colorization using Deep Learning": Create Your Own Challenge.
  - A Knight of Change (Australia): InSAR plus deep learning for glaciers.
  - Source: team pages under `/nasa-space-apps-2024/find-a-team/` ([hansa](https://www.spaceappschallenge.org/nasa-space-apps-2024/find-a-team/hansa/), [making-waves](https://www.spaceappschallenge.org/nasa-space-apps-2024/find-a-team/making-waves/), [a-knight-of-change1](https://www.spaceappschallenge.org/nasa-space-apps-2024/find-a-team/a-knight-of-change1/))

### Inferences
- Every SAR-challenge entry that advanced past nominee did so on presentation and audience design, not processing depth:
  - 2023: a physical NISAR model, a time-lapse art piece, and postcards with QR codes.
  - 2025: a local-impact glacier story, and a slick farmer app with thin SAR content.
- The technically deepest 2025 entries (Arapua Labs, SAR Monsters, UpIT, Surface Sleuths, Yekta) all stopped at nominee.
- This fits criteria weighted on impact, creativity and presentation. It does not prove judges ignored SAR depth: only 1 of 36 SAR nominees advanced, across all challenges.
- TengriSpacers' advance despite "no UI" suggests a clear, specific, high-stakes local story (glaciers as "Kyrgyzstan's Gold", water and hydropower, GLOF risk) with concrete numbers carried weight. The mismatch between its claims and its README was not penalised at that stage.

### Gaps
- No public judge comments or scoring sheets exist for any of these teams. Why a team advanced is not documented.
- I could not find news or LinkedIn coverage of TengriSpacers or the other SAR finalists. One web search returned nothing relevant.
- I did not open the demo videos or slide decks, and I did not check most repos beyond the two summarised above. The GitHub CLI was not authenticated.
- Team country comes from the team's registered location. "Anywhere in the World" means a team registered for the universal (virtual) event.

## Q4. What SAR-specific depth impressed, and what did weak SAR entries get wrong?

### Takeaway
Awards cannot show what impressed the judges, since no SAR-challenge entry won and no comments are public. What the strongest nominees share is physical reasoning in SAR terms:
- dB values tied to scattering mechanisms;
- polarisation choices with a reason;
- masks for water and terrain;
- multi-year stacks;
- an explicit statement of SAR's own limits.

Common weaknesses among nominees:
- unverifiable near-perfect accuracy claims;
- NISAR listed as a data source when it wasn't used;
- SAR named but never processed;
- SAR-to-optical "colourisation";
- nominal "validation" with no reference data.

### Cited Findings
- Keyword census over all submitted 2025 Looking Glass projects (n = 200) versus the 36 nominees, by self-described text:
  - Sentinel-1: 61% overall vs 64% of nominees.
  - NISAR: 20.5% vs 36%. Mostly reference links; see Q5.
  - ALOS/PALSAR: 10% vs 11%.
  - UAVSAR: 4% vs 8%.
  - VV/VH: 28% vs 25%.
  - Polarimetry or decomposition words: 4.5% vs 8%.
  - InSAR/coherence: 18% vs 28%.
  - RTC/terrain correction: 15% vs 17%.
  - Speckle: 12% vs 8%.
  - Time series: 27% vs 33%.
  - "change detection": 14.5% vs 8%.
  - Uncertainty/confidence: 10% vs 14%.
  - Any validation word: 36% vs 50%.
  - GEE: 33.5% vs 33%.
  - ASF/HyP3/Vertex: 50% vs 44%.
  - LLM/chatbot: 10% vs 17%.
  - StoryMap: 12.5% vs 14%.
  - Source: project records of the [2025 teams](https://www.spaceappschallenge.org/2025/challenges/through-the-radar-looking-glass-revealing-earth-processes-with-sar/?tab=teams)
- With stricter patterns over the same 200 submissions:
  - Formal statistical change tests (CUSUM, p-value, likelihood ratio, Wishart, Mann-Kendall, KS, CFAR, false-alarm, change-point): 5 projects. Nominees among them: Arkivators (lists "Bayesian Change Point Detection" among its models) and UpIT.
  - Otsu thresholding: 4 projects. Only Arapua Labs was nominated.
  - Explicit dB thresholds: 5 projects, including Surface Sleuths and Yekta.
  - Uncertainty or confidence terms: 12 projects, including TengriSpacers ("confidence bands") and NARO ("confidence intervals").
  - Named reference data (ground truth, in situ, field, Copernicus EMS): 7 projects, including Cea-SAR and FloodyHell.
  - Source: as above
- 2023 SARt (n = 73): Sentinel-1 19%, UAVSAR 29%, NISAR 12%, InSAR 8%, time series 3%. No project mentioned uncertainty, Otsu, dB thresholds or a formal statistical test. — [2023 teams](https://www.spaceappschallenge.org/2023/challenges/create-a-work-of-sart-synthetic-aperture-radar-art/?tab=teams)
- Unverifiable accuracy claims among 2025 nominees:
  - NARO / ClearScan: "99.7% accuracy in seconds", "Training accuracy: 100%", "Testing accuracy: 99.7%" (Random Forest on SAR and biomass). — [team](https://www.spaceappschallenge.org/2025/find-a-team/naro/)
  - Panggau Libau / TerraShield: "99% accuracy in testing". Its only SAR-related input is the ALOS PALSAR RTC *DEM*, used for slope and curvature. — [team](https://www.spaceappschallenge.org/2025/find-a-team/panggau-libau/)
  - Arkivators: "LSTM forecasting predicts flood spread … with up to 90% accuracy". — [team](https://www.spaceappschallenge.org/2025/find-a-team/arkivators/)
  - IOT AVENGERS: "Data fusion improves detection accuracy to 85-95%", from "6 Active Satellites (Sentinel-1, RISAT-2B, NISAR, ALOS-2, TerraSAR-X, RADARSAT-2)". — [team](https://www.spaceappschallenge.org/2025/find-a-team/iot-avengers/)
- Nominated in the SAR challenge with no SAR processing described in the project text (by my scan):
  - Los Alpha (CultivAI soil sensors).
  - LOS QUE APRUEBAN MILAGROSAMENTE (red palm weevil acoustic sensor; its "SAR" link is an Earthdata project).
  - Impact Crew (renewable siting from CERES).
  - EchoSpace (FIRMS and optical references only).
  - Sources: [Los Alpha](https://www.spaceappschallenge.org/2025/find-a-team/los-alpha/); [LOS QUE APRUEBAN…](https://www.spaceappschallenge.org/2025/find-a-team/los-que-aprueban-milagrosamente/); [Impact Crew](https://www.spaceappschallenge.org/2025/find-a-team/impact-crew/); [EchoSpace](https://www.spaceappschallenge.org/2025/find-a-team/birutas-fc/)
- The 2025 HM FarmHubGlobal gives no SAR processing, polarisation or validation detail. — [team](https://www.spaceappschallenge.org/2025/find-a-team/farmhubglobal/)
- 2024 "Making waves" framed its project as "SAR Image Colorization using Deep Learning". — [team](https://www.spaceappschallenge.org/nasa-space-apps-2024/find-a-team/making-waves/)
- Examples of SAR-literate detail among nominees:
  - Lost Frequencies masks "Water pixels (VH < -22 dB) … to prevent differences caused by water". — [team](https://www.spaceappschallenge.org/2025/find-a-team/lost-frequencies/)
  - SAR Monsters uses L-band "to distinguish open water from flooded vegetation under canopy" and validates with "IoU and precision/recall". — [team](https://www.spaceappschallenge.org/2025/find-a-team/sar-monsters/)
  - Arapua Labs applies Otsu "to the linear VV polarization". — [team](https://www.spaceappschallenge.org/2025/find-a-team/arapua-labs/)
  - Surface Sleuths: "Surface separation is based on backscatter characteristics rather than visual appearance". — [team](https://www.spaceappschallenge.org/2025/find-a-team/surface-sleuths/)
- Judging context: the 2023 SARt brief names its criteria as "creativity, innovation, and clarity". — [2023 SARt](https://www.spaceappschallenge.org/2023/challenges/create-a-work-of-sart-synthetic-aperture-radar-art/). The current Judging & Awards Guide page did not return content when fetched. Secondary sources report impact, creativity, validity, relevance and presentation as the general criteria, with validity and relevance gating Global Judging (based on a 2020 team page and a Bahrain news report). This is not verified for 2025 or 2026. — [Judging & Awards Guide (link)](https://spaceappschallenge.org/resources/judging-awards-guide); [2022 guide PDF](https://spaceapps-prod.s3.amazonaws.com/media/documents/Space_Apps_2022_Judging_and_Awards_Guide.pdf)

### Inferences
- **Errors weaker entries made (my assessment, not the judges'):**
  - **Accuracy without a test design.** 99–100% accuracy with no independent reference, no class balance and no spatial hold-out is a red flag to any SAR reviewer.
  - **"NISAR" or "six satellites" in a data stack** with no granule IDs or processing.
  - **Sub-noise attribution.** Yekta reads −0.3 dB as earthquake "micro-cracks". From general Sentinel-1 knowledge (not verified here), changes of a few tenths of a dB are within speckle and calibration noise unless averaged over large areas. A test against a no-change distribution would have been needed.
  - **Treating SAR as a picture.** Colourising SAR to look optical, or choosing art regions by shape (seahorse, heart), uses backscatter as an image rather than a measurement. That suited the 2023 art brief but would not suit 2026's "actionable insights".
  - **"Validation" meaning a plan**, e.g. "will train an AI model", rather than a comparison with reference data.
- **Depth that stands out:**
  - Linear-versus-dB awareness.
  - Water and terrain masks.
  - L-band versus C-band reasoning for flooded vegetation.
  - Explicit dB ranges per surface class.
  - Multi-year stacks.
  - Metric-based validation (IoU, precision/recall).
  - Stated limitations: single track, small-area dilution, C-band surface-only sensitivity.
- **What is missing everywhere:** no 2025 entry combined these in an interactive app with uncertainty shown to the user. That gap fits the 2026 brief exactly.

### Gaps
- No primary statement from NASA judges about what they valued in SAR entries.
- The census uses keywords on self-reported text. A keyword hit does not prove the method was carried out. "Precision" and "validation" in particular produce false positives.

## Q5. Did any entry use NISAR? Time series, statistical change tests, "what cannot be seen"?

### Takeaway
I found no evidence that any 2023 or 2025 entry processed real NISAR science data.
- In 2023 NISAR had not launched. The brief offered "datasets similar to those that NISAR will provide".
- In 2025, NISAR mentions were mostly links to NISAR StoryMaps and white papers. A few cited NISAR *sample* products or documentation. Some claimed NISAR data with no evidence.

Time series were common among the stronger entries. Formal statistical change tests were nearly absent: thresholds such as Otsu, fixed dB and coherence ≥ 0.3 stood in for tests. Explicit "what SAR cannot see" treatment was rare but present (Surface Sleuths, Yekta, Explorer_J1K2R1).

### Cited Findings
- **NISAR:**
  - 2023 brief: "The upcoming NISAR … mission … will collect data", and teams "will work with datasets similar to those that NISAR will provide". — [2023 SARt](https://www.spaceappschallenge.org/2023/challenges/create-a-work-of-sart-synthetic-aperture-radar-art/)
  - Of 2025 submissions mentioning NISAR (41/200, 13 of them nominees), most hits were reference links to NISAR StoryMaps or applications white papers. — [2025 teams](https://www.spaceappschallenge.org/2025/challenges/through-the-radar-looking-glass-revealing-earth-processes-with-sar/?tab=teams)
  - **Team_JSR (India), "SAR Earth Visualizer"** (not nominated):
    - It links a NISAR sample product, "NISAR_L2_PR_GSLC_001_030_A_019_2800_SHNA_A_20081012T060911…", and a "Level 3 Global Soil Moisture Product" sample.
    - Its visualiser runs on "a large CSV dataset of SAR-simulated values".
    - Source: [team](https://www.spaceappschallenge.org/2025/find-a-team/team_jsr/)
  - **SARvadarshi (India)** links the "NISAR … Product Specification L1 ROFF" document hosted in the NISAR sample-data bucket. — [team](https://www.spaceappschallenge.org/2025/find-a-team/sarvadarshi/)
  - **Beyond unseen** lists "Copernicus Sentinel-1, NISAR simulation data". — [2025 teams](https://www.spaceappschallenge.org/2025/challenges/through-the-radar-looking-glass-revealing-earth-processes-with-sar/?tab=teams)
  - **Galaxy pirates (Egypt), "EGYSAR"** claims "NISAR sends radar signals of the site every ~12 days" for monitoring Abu Simbel. It shows no product or granule. — [team](https://www.spaceappschallenge.org/2025/find-a-team/galaxy-pirates/)
  - Nominees that list NISAR among inputs without processing detail:
    - Arkivators: "Powered by NASA's Sentinel-1, UAVSAR, SRTM, GPM, and NISAR data".
    - IOT AVENGERS.
    - npSAR, which calls NISAR "recently launched L,S-band SAR" as a future input.
    - NARO, which calls it a "Long-Term Vision".
    - Mi6, which calls it the "upcoming NISAR dual-frequency SAR mission".
    - Sources: [Arkivators](https://www.spaceappschallenge.org/2025/find-a-team/arkivators/); [npSAR](https://www.spaceappschallenge.org/2025/find-a-team/pns/); [NARO](https://www.spaceappschallenge.org/2025/find-a-team/naro/)
  - The 2026 page shows NISAR L-band imagery of Mount Rainier dated "Nov. 10, 2025". — [2026 challenge](https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/)
- **Time series** (as described by the teams):
  - SARtists: 2018–2023 time-lapse.
  - Arapua Labs: dense S1 stack with seasonal medians and rainfall/wind correlation.
  - Cea-SAR: 2015–2024.
  - UpIT: 8-year PS-InSAR.
  - Yekta: 150 scenes, 2014–2025.
  - Surface Sleuths: 9 scenes, May 2024 to Sept 2025.
  - TengriSpacers: 2016–2025.
  - MicroOndeados: Tabasco floods from 2014.
  - npSAR: lake area by year.
  - Sources: team pages cited in Q3
- **Statistical change tests:**
  - No nominee describes a formal per-pixel change test with false-alarm control (no CUSUM, likelihood ratio or Wishart test).
  - Nearest equivalents: Otsu on linear VV (Arapua Labs), ±0.5 dB change vectors (Yekta), coherence ≥ 0.3 (UpIT), VH < −22 dB water mask (Lost Frequencies), and "Bayesian Change Point Detection" named in a model list (Arkivators).
  - Across all 200 submissions, only 5 used any formal-test vocabulary.
  - Sources: team pages cited in Q3/Q4; [2025 teams](https://www.spaceappschallenge.org/2025/challenges/through-the-radar-looking-glass-revealing-earth-processes-with-sar/?tab=teams)
- **"What cannot be seen":**
  - Both the 2025 and 2026 briefs ask teams to explain "what you see (or don't see)". — [2025](https://www.spaceappschallenge.org/2025/challenges/through-the-radar-looking-glass-revealing-earth-processes-with-sar/); [2026](https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/)
  - Explicit treatments of SAR's own limits:
    - Surface Sleuths: small-flow dilution, single orbit track, C-band surface-only. — [repo](https://github.com/Yasaswini-ch/reykjanes-sar-analysis)
    - Yekta: "limitations include C-band penetration and 10m resolution". — [team](https://www.spaceappschallenge.org/2025/find-a-team/yekta/)
    - Explorer_J1K2R1: InSAR not possible for the island without RADARSAT-2. — [team](https://www.spaceappschallenge.org/2025/find-a-team/explorer_j1k2r1/)
    - SAR Monsters: C-band cannot see water under canopy, so it adds L-band where available. — [team](https://www.spaceappschallenge.org/2025/find-a-team/sar-monsters/)
  - Most other "limitation" language concerns optical sensors and clouds, not SAR.
  - In 2023, only one of 73 projects (Weballin) used limitation language at all.

### Inferences
- Showing real NISAR products would itself be new in 2026, since no earlier entry did it convincingly.
- Other combinations no previous entry has shown together:
  - a NISAR time series with a statistical change test and visible uncertainty;
  - an explicit "what NISAR cannot see here" layer (layover/shadow, single-track geometry, dense-canopy saturation, sub-noise changes);
  - honest validation against reference data.
- The Team_JSR sample-product filename embeds a 2008-10-12 acquisition time. That suggests the NISAR sample products were simulated from older L-band data, likely ALOS-1 PALSAR. This is my reading of the filename and is not verified.

### Gaps
- I did not verify whether real NISAR science data was publicly downloadable during the 4–5 Oct 2025 hackathon. I did not check the release timeline in this session.
- I did not open any linked repo or video to check whether the NISAR or time-series claims are implemented.
- Layover, shadow and foreshortening treatment appears in only one 2025 submission by keyword (0 nominees). That entry's content was not reviewed.
