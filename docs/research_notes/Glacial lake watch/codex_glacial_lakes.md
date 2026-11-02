# SARtale: glacial lake watch — research and problem case

Research checked against public web sources and the supplied [feasibility spike](spike_findings.md). This is a research assessment, not an operational hazard bulletin. No authenticated satellite access, field validation, or new image processing was performed for this report. No factual claims are intentionally based on memory; unresolved claims are marked **not found**, **unverified**, or **inference/proposal**. A source being published does not make its coordinates, classifications, or estimates error-free.

## Findings that change the app's scope

- **The defensible product is an administrator's lake-change watch and review queue.** It can supply dated evidence for inspection and preparedness; it cannot reliably announce an imminent breach. Shisper's major drainage episodes lasted **1–2 days**, shorter than a single NISAR geometry's **12-day** repeat. Processing and analyst review add further delay. [Shisper phases][PHASES]; [NISAR GCOV][GCOV]
- **There is an evidenced observation gap within an existing monitoring service.** SUPARCO reports cloud-limited assessment; see B2. SARtale must demonstrate additional usable observations and easier review. [SUPARCO update][SUPARCO]
- **The spike demonstrates access and a promising persistent-water detector, not warning accuracy.** Its temporal medians and opposite-look intersection can suppress transient lakes. Its Attabad control is landslide-dammed, not a validation set of hazardous glacial lakes. [Local spike](spike_findings.md)
- **Lake identity and coverage need work before a deployment.** The register below includes genuine lakes, ephemeral source systems and unresolved valley labels. It does not establish a fully georeferenced operational catalogue. “Station not found” means no sufficiently specific public evidence was found, not that equipment does not exist.

## Part A — lakes, SAR methods and useful signals

### A1. Candidate register

Coordinates are listed as **latitude, longitude**, north/east. Published precision is retained; no village or glacier-centre coordinate is silently substituted for a lake. “Size” means the reported observation, not a timeless typical size. Ephemeral lakes may be absent between filling episodes. Ground coverage distinguishes weather/discharge monitoring from a lake-level sensor and from current operational readiness.

The register has **fourteen candidate entries** selected for investigation; several are source systems rather than a uniquely verified individual lake. Missing data prevent treating it as fourteen ready-to-monitor lake polygons.

| Candidate and location | Best-available lake coordinate and provenance | Lake type and reported size | Outburst history / present-status limitation | GLOF-I/II ground coverage evidence |
|---|---|---|---|---|
| **Shisper / Shishper–Mochowar, Hassanabad, Hunza, GB** | **36.39, 74.51**, Shrestha et al. inventory table, but **disputed as a locator for the modern lake**. Modern paper maps the lake/snout within **36°21′–36°22′ N, 74°34′–74°36′ E**; this is a map frame, not a measured centroid. Use the published lake polygons to resolve it. [Inventory][HMA]; [modern map][SHISPERMAP]; [polygon dataset][POLYGONS] | Ice-dammed. Reported area **0.26 km² on 17 April 2022**, **0.38 km² on 5 May 2022**. These are dated observations, not a stable typical size. [Case study][SHISPER22] | Documented breaches **22 June 2019**, **29 May 2020**, **7 May 2022**. [Event study][SHISPEREVENTS] No reformation observed through **6 September 2024** in the later study; current absence is unconfirmed here. [Phases][PHASES] | **Yes, documented project equipment:** Hassanabad AWS announced **19 July 2019**; project report also records low-altitude installations. Exact lake-level gauge and current uptime: **not found**. [UNDP announcement][AWS]; [project report][APR] |
| **Khurdopin impoundment, Shimshal, Hunza, GB** | **36.34, 75.47**, published lake-location point in Shrestha et al. [Inventory][HMA] | Ice-dammed. Stable typical area: **not found**. Modelled volume reached **2 million m³ on 28 June 2017**; do not relabel this as measured area. [Steiner et al.][KHURDOPIN] | Inventory records recurrent events during **1882–2021**. [Inventory][HMA] Observed drainage began around **21 July 2017**, with disappearance by **5 August 2017**. [Steiner et al.][KHURDOPIN] | Named-lake GLOF-I/II station commissioning: **not found**. Field studies are not proof of continuous telemetry. |
| **Passu / Pasu terminal lake, Hunza, GB** | **36.457, 74.879**, published event-table coordinate in the HMA area-change study; retrieved from indexed article text, not an independently checked polygon. [Coordinate source][PASSUCOORD] | Moraine-dammed. Reported **0.16 km²**, but a precise measurement date for that quoted value was **not found**. [Muneeb et al.][HUNZA] | **July 2007** outburst reported by Muneeb et al.; another event table gives **6 January 2008**. These are separate published entries, not a reconciled complete chronology. [Hunza study][HUNZA]; [event table][CPEC] | Historical AWS and lake-site discharge monitoring **since 2010** documented by PMD; further warning equipment was proposed. GLOF-I/II attribution and current operational status: **not found**. [PMD][PMDOLD] |
| **Ghulkin / Yaz-Sam supraglacial lake system, Hunza, GB** | **36.42, 74.88**, Shrestha et al. historical lake point; matching it to an active Yaz-Sam polygon remains necessary. [Inventory][HMA] | Supraglacial/ephemeral. Inventory lake **Hunz-gl 14: 1.39 ha** in the **2013** inventory. [Pakistan supraglacial study][SUPRA] | Historical Ghulkin events span **1980–2009** in the inventory. [Inventory][HMA] Yaz-Sam study reports flooding in **2008, 2010, 2013 and 2015**. [Supraglacial study][SUPRA] | **Yes, valley system documented:** **11** systems reported installed and functional in Ghulkin/Hussaini in the **2023** project report, including weather/rain/discharge equipment and warning posts. Named lake-depth gauge and current uptime: **not found**. [Project report][APR] |
| **Karambar / Karamber glacier-dammed impoundment, Ishkoman, GB** | **36.62, 74.08**, Shrestha et al. lake point. [Inventory][HMA] | Ice-dammed. Typical or dated area: **not found**. | Recurrent outbursts recorded during **1844–1994**. [Inventory][HMA] Do not automatically identify this historical glacier-dammed site with a tourist lake bearing the same name. Current impoundment status: **not found**. | Lake-specific GLOF-I/II station: **not found**. |
| **Unnamed Batura-associated lake, upper Hunza, GB** | **36.51, 74.85**, Shrestha et al. historical lake point. [Inventory][HMA] | Classified supraglacial in that inventory. Typical or dated area: **not found**. | Recorded recurrence during **1873–1974**. [Inventory][HMA] This supports historical investigation, not a claim of a presently filled or highly hazardous lake. | Lake-specific GLOF-I/II station: **not found**. |
| **Hinarchi / Barberi, Bagrot, GB** | Lake coordinate: **not found**. A glacier location or downstream settlement pin is insufficient. | Supraglacial/ephemeral **Gil-gl 656**, **0.29 ha** in the **2013** inventory. [Supraglacial study][SUPRA] PMD separately reports a pond growing from approximately **100 m² in 2008** to **1,100 m² in 2011**; identity/date differences must be reconciled. [PMD][PMDOLD] | Repeated filling/breaching described, but a reliable individual-event date list was **not found**. NDMA identifies Hinarchi as vulnerable. [Supraglacial study][SUPRA]; [NDMA][NDMAREPORT] | **GLOF-I valley coverage confirmed:** Bagrot AWS and downstream stream gauge documented in **May 2014**; evaluation criticised gauge placement below some villages. A Hinarchi lake-level gauge: **not found**. [Evaluation][MTE] |
| **Gargo / Gharko supraglacial lake, Bagrot, GB** | Lake coordinate: **not found**. | Supraglacial **Gil-gl 658**, **1.95 ha** in the **2013** inventory. [Supraglacial study][SUPRA] | Sudden breach reported in **September 2014**. [Supraglacial study][SUPRA] Current lake geometry: **not found**. | Bagrot GLOF-I valley monitoring applies as context; separate Gargo lake-level station or source-specific detection coverage: **not found**. [Evaluation][MTE] |
| **Badswat / Badsuwat cascade and downstream lake, Ishkoman, GB** | Verified lake point: **not found**. A recent paper provides a **study-area** coordinate; it is not accepted here as a source-lake centroid. [Event reconstruction][BADSWAT26] | The prominent downstream lake is **debris-flow-dammed**, outside a simple ice-/moraine-/supraglacial taxonomy. Reported average area **0.47 km² after the 2018 event**, subsequently **0.63 km²**; these describe the downstream impoundment. [Monitoring study][BADSWATSIZE] | **17 July 2018** debris flow blocked the river. [Reconstruction][BADSWAT26] Published analysis traces a glacier-water/debris cascade; it is unsafe to label every component a single surface-lake GLOF. [Disaster-chain study][BADSWATCHAIN] | Named-lake GLOF-I/II commissioning: **not found**. A separate sensor-development report describes proposed sites, not proof of a completed installation. [Implementer report][APNIC] |
| **Golen Gol / Dook Pal source basin, Chitral, KP** | Source-lake coordinate: **not found**. Do not use hydropower-plant coordinates. | PMD describes an **englacial** lake; reports **0.043 km² on 3 July 2019**. [PMD Update-II][GOLENPMD] WAPDA later observed an empty former basin with smaller supraglacial ponds. [WAPDA][WAPDA] | **7 July 2019** outburst; government audit records recurrence **13 July 2020**. [PMD][GOLENPMD]; [audit][GOLENAUDIT] The basin was empty during WAPDA's **2023** visit. [WAPDA][WAPDA] | Lake-level GLOF-I/II station: **not found**. WAPDA surveys and glacier stakes are not equivalent to a continuous lake-warning sensor. |
| **Reshun source lake/system, Chitral, KP** | Lake coordinate: **not found**. NDMA's vulnerable-site label does not resolve a polygon. | Dam type and dated size: **not found**. NDMA explicitly identifies a vulnerable Reshun glacial lake. [NDMA][NDMAREPORT] | The provincial climate plan records a **2013** GLOF; source-lake attribution remains incomplete. [KP plan][KPPLAN] | GLOF-II bases documented in **2023**; NDMA describes precipitation monitoring in “Reshun Booni” on **19 May 2026**. This does not establish a commissioned lake-level gauge. [Project report][APR]; [advisory][GAUGES] |
| **Booni Gol source system, Upper Chitral, KP** | Lake coordinate: **not found**. | PMD describes water stored **beneath the terminus**, not a securely identified permanent open lake. Dated surface area: **not found**. [PMD][PMDOLD] | PMD reports an outburst in **July 2010**; NDMA records a GLOF on **3 August 2024**. [PMD][PMDOLD]; [NDMA][NDMAREPORT] | Forecast/advisory and precipitation-gauge coverage documented; named lake-level GLOF-I/II station: **not found**. [NDMA][NDMAREPORT]; [gauged-valley advisory][GAUGES] |
| **Hispar / Hisper–Hoper candidate lake systems, Nagar, GB** | Individual lake coordinates: **not found**. This combined valley name must be split into actual lake IDs before ingestion. | Hispar has supraglacial ponds; published **2013** individual areas range **0.68–21.02 ha**. This is a population range, not one lake's size. [Supraglacial study][SUPRA] | Literature describes Hispar supraglacial outbursts; individually attributable dates for the proposed “Hisper-Hoper lake” were **not found**. [CPEC chapter][CPEC] | NDMA lists gauged “Hisper-Hooper” precipitation monitoring on **19 May 2026**. Lake-specific warning coverage: **not found**. [Advisory][GAUGES] |
| **Darkut / Darkot source systems, Ghizer/Gupis-Yasin, GB** | Lake coordinate: **not found**. | Exact source lake, dam type and dated size: **not found**. | Darkot/Barados event reported in **September 1978**; NDMA again identifies Darkut among vulnerable valleys on **25 June 2025**. Neither establishes a currently filled individual lake. [CPEC chapter][CPEC]; [NDMA advisory][PIDALERT] | Lake-specific GLOF-I/II station: **not found**. |

**Important exclusions and qualifications.** Bindo Gol is a valuable flood-warning case but should not be added merely to inflate a glacial-lake count: GLOF-I field evaluation identified ephemeral gorge impoundment behind avalanche/mass-movement debris, rather than a permanent proglacial, supraglacial or englacial lake. It confirms valley AWS coverage. [GLOF-I evaluation][MTE] Attabad is appropriate as a conspicuous water control, not proof of performance on glacial source lakes. [Local spike](spike_findings.md)

**Coordinate provenance and usable next step.** Shrestha et al.'s database distinguishes lake coordinates from downstream-impact coordinates; its point can be anywhere within a lake, not necessarily at a breach. [Metadata][HMAMETA] For actual implementation, obtain versioned polygons and agency lake IDs, then inspect them against contemporary imagery. The public development database is linked to an ICIMOD record and explicitly states its quality-control cutoff of **31 December 2025**. [Database][HMAGIT] Numerical values above are research locators, not field-navigation instructions.

### A2. What the feasibility spike does and does not establish

The supplied note reports GCOV **PROVISIONAL P05023**, mode **4005**, **HH/HV**, **10 m**, **EPSG:32643**; native **512 × 512** gzip chunks; a **7 km** window transferring **24–43 MB** from an approximately **7 GB** granule in **11–28 seconds**. These are **team-reported test measurements, not independently rerun here**, and not universal NISAR performance specifications. [Local spike](spike_findings.md)

The tested tracks were **055 ascending, 156 ascending and 063 descending**. Track **055** was almost empty over the Shisper box despite covering Attabad. The rule required both channels at least **4 dB below their scene medians**, in both ascending and descending temporal composites. It recovered approximately **3.0 km² within the Attabad window**; no independent optical-area validation was reported. [Local spike](spike_findings.md)

The Shisper AOI was **74.56–74.64 E, 36.29–36.37 N**, observed **18 June–23 October 2026**. The historical inventory point in A1 is outside it, but the modern lake/snout map frame is inside it. Therefore the discrepancy **does not establish that the AOI was wrong**. The published Shisper lake shapefiles are the better reconciliation source; their bounds were not verified in this research. [Local spike](spike_findings.md); [modern map][SHISPERMAP]; [polygons][POLYGONS]

Published absence evidence extends through **6 September 2024**, not through the spike year; the study also places maximum lake extent in **May**, before the spike's summer–autumn window. [Phases][PHASES] The careful claim is:

> The composite identified persistent open-water-like backscatter at Attabad and no qualifying persistent dual-view candidate in the Shisper AOI. Current Shisper lake status remains unconfirmed.

**Technical deductions from the supplied algorithm:** a long temporal median can erase a brief filling/drainage event; opposite-look intersection can reject water visible in only one geometry; acquisitions on different dates can confuse real change with disagreement. Scene-relative thresholds also move when the surrounding snow/wetness or land-cover mixture changes. “Water does not depend on look direction” is too absolute: water's measured backscatter and visibility do change with surface state and geometry. A missing/invalid look must mean **unknown**, not dry.

### A3. Published SAR methods, performance and minimum size

These are study-specific results. They are not interchangeable measures of accuracy and are not validated performance promises for NISAR in GB/KP.

| Study / setting | Method and numerical results | What the result does not establish |
|---|---|---|
| **Upper Indus Basin, Sentinel-1 VV** | Initial candidate threshold **−13 dB**, followed by object-local Otsu thresholds ranging **−13 to −28 dB**, mean **−20 dB**. Minimum retained area **1,000 m²**. Against **100** manually delineated optical lakes: area MAE **0.009 km²**, MAPE **10.04%**. [Khan et al.][UIB] | Includes terrain/snow masks, speckle treatment and optical manual correction. An inclusion cutoff is not demonstrated reliable detection at that size. Ice/wet-snow confusion remains. |
| **Southeastern Tibetan Plateau, Sentinel-1 time series** | Temporal-median-regularized level-set segmentation; overall accuracy **96.54%**, kappa **0.95**, against Gaofen-derived outlines. SVM **92.13%**, ISODATA **88.87%** under the same study design. [Zhang et al.][ZHANG] | Pixel classification accuracy, not the probability of catching a dangerous change. No NISAR minimum reliable lake area follows from this result. |
| **GLakeMap, alpine optical/SAR fusion** | Sentinel-1/2, DEM, rules and random forest; SAR threshold **−14 dB**. Reported mapping scores **96.21–99.07%** across the study sites. [Wangchuk and Bolch][GLAKEMAP] | Multisensor, partly rule-constrained results; not SAR-only accuracy, and its mapping score differs from pixel accuracy or IoU. |
| **Glacial Lake Observatory, Nepal/transboundary catchments** | DeepLabV3 with annual summer Sentinel-1 VV composites. Sentinel-1 F1 **0.82**, Sentinel-2 F1 **0.92** in the **2020** manual validation. Although inventory inclusion starts at **0.001 km²**, robust F1 **≥0.85** was generally reached above **0.084 km²** for Sentinel-1 versus **0.028 km²** for Sentinel-2. [GLO][GLO] | These model/domain-specific robustness thresholds are not universal sensor limits. Annual composites do not demonstrate short-warning performance. |
| **Baltoro, Pakistan, multisensor supraglacial monitoring** | Separate random forests and harmonized Sentinel-1/TerraSAR-X plus optical observations. Fused sampling **2–4 days**, mean relative RSE **1.0%**. [Wendleder et al.][BALTORO] | SAR underestimated lake area and missed observations in undulating terrain. The favorable error metric belongs to the fused workflow. |
| **ALOS PALSAR comparative glacial-lake study** | Manual interpretation: PALSAR improved Imja Tsho distinction over ENVISAT; finer-resolution sensors better resolved small Tajikistan lakes. [Strozzi et al.][STROZZI] | Wavelength, resolution and conditions change together. A universal L-band threshold, accuracy or minimum size was **not found**. |
| **Bhutan PALSAR conference work** | RTC, radar-brightness thresholding, optical glacier masks and DEM constraints. [Author abstract][PALSAR]; [institutional publication record][RESTEC] | Numeric threshold, completed validation accuracy and reliable minimum area: **not found** in the accessible abstract; validation was described as planned. Smooth ice also mimicked water. |

**Failure modes and the meaning of L-band**

| Condition | Consequence for lake mapping | Treatment warranted by the evidence |
|---|---|---|
| Radar shadow / layover | Shadow can resemble dark water; layover can mix bright terrain into a shoreline. RTC normalizes radiometry but cannot recover an unobserved surface. | Use geometry/DEM visibility masks, each orbit separately and complementary looks. Preserve unknown areas. [Strozzi][STROZZI]; [GCOV specification][GCOV] |
| Frozen or snow-covered lakes | Ice changes scattering; smooth frozen surfaces can remain dark. | Separate water presence, lake basin and freeze state. “Dark” is not proof of liquid water. [GLakeMap][GLAKEMAP] |
| Wind and waves | Rough water becomes brighter, producing false negatives. | Inspect weather and repeat observations; do not treat threshold failure as lake disappearance. [Strozzi][STROZZI] |
| Wet snow / wet sediment | Can resemble low-backscatter water and inflate extent. | Snow/temperature context and independent labels; review uncertain margins. [Upper Indus study][UIB]; [Strozzi][STROZZI] |
| Debris-covered ice / icebergs | Roughness, pits and floating debris obscure water; glacier topography creates visibility gaps. | Validate against near-coincident optical/field evidence; retain observability metrics. [Baltoro study][BALTORO] |

**Is L-band better?** A controlled GB/KP benchmark was **not found**. Strozzi's comparison does not isolate wavelength. [Strozzi][STROZZI] **Inference:** test complementary L-band information, but assume no immunity to terrain, ice or rough water. Transfer neither a C-band VV threshold nor its reported accuracy directly to NISAR HH/HV.

**Proposed validation:** stratify independent labels by lake size/type, open versus frozen water, season and orbit. Measure lake-presence recall, polygon overlap and area error, shoreline visibility, missed change events and false review flags. Compare NISAR-only, Sentinel-only and combined evidence. Numerical acceptance thresholds remain **unknown pending agency requirements and representative validation**.

### A4. Signals that can help administrators

Area change is an observation, not a universal failure threshold. Evaluate absolute change and change rate, ΔA/Δt, relative to mapping uncertainty, season and observability. A rapid percentage change in a tiny uncertain polygon can be meaningless.

| Signal | Decision it can support | Time scale / constraint |
|---|---|---|
| New impoundment; confirmed growth or pond coalescence beyond uncertainty | Prioritize analyst review, request a local check, assess exposed infrastructure and possible access routes. | Watch development across successive valid acquisitions. Khurdopin filled over the melt season before drainage; Shisper demonstrates substantial pre-event growth. [Khurdopin][KHURDOPIN]; [Shisper case][SHISPER22] |
| Water-level rise and reduced freeboard | Escalate site assessment under a lake-specific response plan. | Requires gauges, surveyed elevations or validated lake hypsometry. GCOV intensity is not a direct water-level measurement; area alone does not yield trustworthy volume or remaining freeboard. **Inference from measurement limitations.** |
| Ice-dam advance, blockage or surge acceleration | Inspect a new obstruction, upgrade monitoring and assess impoundment potential. | Glacier evolution can be observed before filling, but velocity alone cannot specify breach time. [Khurdopin][KHURDOPIN] |
| Sudden lake shrinkage / downstream flood evidence | Seek immediate corroboration and support response or damage assessment. | May mean drainage is already underway or finished; also may be freeze/wind/visibility error. It must not be marketed as guaranteed advance warning. |
| Weather plus lake/river telemetry | Existing official vigilance, preparedness and warning procedures. | PMD combines hydrometeorological stations, models and field work. This is the appropriate immediate-warning chain. [PMD unit][PMDUNIT] |

**Proposed operating rule:** a satellite flag should say what changed, where, over which acquisition interval, how much of the lake was observable, and why a human should review it. It should not produce an unsupported breach probability. Multiple looks can improve opportunities, but awaiting corroboration can also delay a decision. Show the date of each contributing look, not one deceptively current composite timestamp.

## Part B — problem, existing practice and case for the app

### B1. What exactly is the problem, and who suffers?

The affected systems are settlements, farms and irrigation, bridges and access roads, hydropower, and the people depending on them. Exposure includes residents and people travelling through isolated valleys. GLOFs are one part of the region's flood problem; rain-driven flash floods, river floods, landslides and infrastructure failures are different mechanisms.

UNDP's **2025** brief describes **more than 3,000 glacial lakes**, **33 hazardous lakes**, and **over 7.1 million people at risk** in GB/KP. Similar exposure language was already used in **2018**. This is a programme-level vulnerability estimate, not an annual affected population, current sensor gap, or number of people this app would protect. [UNDP brief][BRIEF]; [earlier launch][LAUNCH]

**Regional disaster burden — all reported flood/monsoon causes, not GLOF-only**

| Event period and source | Khyber Pakhtunkhwa | Gilgit-Baltistan | Interpretation |
|---|---|---|---|
| **2010 floods**, NDMA figures as of **24 February 2011**, retrospective Table 35. [NDMA][FLOOD2010] | **3.80 million affected; 1,156 deaths; 257,294 houses damaged.** | **100,000 affected; 183 deaths; 3,157 houses damaged.** | Historical rain/flood disaster totals. KP boundaries differ from later statistics explicitly including merged areas. |
| **2022 monsoon**, FFC Table 3.15. [FFC][FLOOD2022] | **4,350,490 affected; 309 deaths; 91,464 houses; 1,575 km roads; 107 bridges damaged.** | **51,500 affected; 23 deaths; 1,793 houses; 33 km roads; 61 bridges damaged.** | Torrential-rain/flash-flood compilation. These are not losses caused exclusively by glacial lakes. |
| **2025 monsoon**, cumulative **26 June–1 October**, final report **2 October 2025**. [NDMA][FLOOD2025] | **509 deaths; 218 injured; 3,222 houses; 513.49 km roads; 52 bridges damaged.** | **31 deaths; 52 injured; 1,260 houses; 290.17 km roads; 92 bridges damaged.** | Multiple monsoon-related causes. Deaths are partly assigned by home province: the report reassigns **10 tourist deaths** previously counted in GB. |
| **2025 affected-population estimates**, year-end humanitarian report. [UNICEF][UNICEF2025] | Approximately **1.2 million** people. | Approximately **0.2 million** people. | Retrospective estimates, distinct from exposure or cumulative casualties. |

For monetary context, the government-led **2022** PDNA estimated KP physical damage at **PKR 201 billion**, economic losses at **PKR 141 billion**, and recovery needs at **PKR 168 billion**. These are different accounting categories and all-flood totals; they should not be added into a purported GLOF loss or claimed as losses SARtale could avoid. A separate comparable GB figure was **not found** in that table. [PDNA Table 1][PDNA]

**GLOF-specific recurrence and concrete disruption**

- GLOF-II reported **75 incidents — 64 in GB and 11 in KP — during June–August 2022**. Its annex includes nullahs, grouped locations and repeated incidents. This is a **project-reported incident count**, not independently established release events from distinct lake polygons. A consistent annual GB/KP GLOF series for **2010–2025** was **not found**; no annual average or trend is inferred. [GLOF-II report][GLOF2022]
- Golen's **7 July 2019** outburst damaged access and hydropower infrastructure. An audit records **PKR 43 million** in temporary restoration subsequently washed away on **13 July 2020**, followed by further flash-flood damage on **26 August 2020**. This is an audited repair-loss example, not total valley damage. [Audit][GOLENAUDIT]
- Shisper's **7 May 2022** event damaged the Hassanabad Karakoram Highway bridge and caused route diversion. [Government broadcaster][SHISPERBRIDGE]
- NDMA records the Booni GLOF on **3 August 2024** and prior advisories. A humanitarian report describes damage to bridge, power and irrigation infrastructure. A defensible event-specific population or monetary total was **not found** here. [NDMA][NDMAREPORT]; [responder][BOONIIMC]

These records establish recurrent disruption and administrative responsibility. They do **not** establish that a satellite lake-watch would have prevented the reported casualties or losses.

### B2. What administrators use today, and the actual gap

| Existing actor/resource | Documented function | Implication for SARtale |
|---|---|---|
| **PMD Glacier Monitoring Unit** | Weather/rain stations, level/discharge gauges, models, field measurements and advisories. [PMD][PMDUNIT] | Complement point telemetry and field expertise; do not replace them. |
| **GLOF-II community and ground systems** | The project brief describes work across **24 valleys** and installation of **292 EWS**. [UNDP][BRIEF] A procurement notice dated **10 September 2026** states equipment ownership/operations transferred to PMD and seeks repairs/replacements. [Procurement][REPAIR] | EWS counts are not counts of individually instrumented lakes. A maintenance need is evidenced; exact offline stations, working lake gauges and per-lake coverage remain unknown. |
| **SUPARCO / Space4Climate** | Publishes observed lake status, area, frozen/cloudy status and comparisons with past extent; receives locations from disaster agencies and WAPDA. [SUPARCO][SUPARCO] | A map and area chart alone duplicate existing capability. |
| **NDMA / NEOC, PDMAs and districts** | Hazard monitoring, forecasts, preparedness/response coordination; official warning dissemination through established agency channels. [NEOC][NEOC]; [warning chain][WARNINGCHAIN] | Analyst flags should feed that chain. A public prototype has no authority to issue official evacuation instructions. |
| **ICIMOD and research inventories** | Historical event/source records and mapped lake baselines. [Database][HMAGIT]; [inventory methodology][HMAMETA] | Useful provenance and identifiers, not live lake-condition telemetry. Avoid treating one inventory snapshot as a current hazard map. |
| **Sentinel-based research products** | GLakeMap and regional Sentinel studies already delineate lakes; GLO publishes time-series lake datasets. [GLakeMap][GLAKEMAP]; [GLO][GLO] | NISAR needs a measured incremental contribution, not a claim that SAR lake mapping is new. |
| **UNOSAT** | Sentinel-derived flood maps and downloadable GIS exposure products; a Punjab map used **10 July 2025** Sentinel-1 imagery and was published **15 July 2025**. [UNOSAT][UNOSAT] | Demonstrates existing event-response SAR products. It does not document a continuous GB/KP glacial-source-lake watch. |

**Strongest documented gap:** SUPARCO's **2 July 2026** bulletin reported monitoring **131 potentially dangerous locations**, using imagery acquired **16 June 2026**, and explicitly said persistent clouds restricted recent lake-area assessment. [SUPARCO][SUPARCO] This is a specific opportunity to test radar during optical gaps. It is **not evidence that SUPARCO lacks SAR capability**: its own glacier service describes both radar and optical data. [Capabilities][SUPARCOCAP]

**Other gaps require user research, not assumption.**

- **Unsensored lakes:** public records establish selected-valley coverage, not a complete lake-to-sensor mapping. The number of target lakes lacking functioning relevant sensors is **not found**.
- **Revisit and latency:** orbital coverage, radar visibility, usable acquisition and delivery are separate constraints. More tracks do not guarantee more valid lake observations.
- **Cost:** open imagery removes a licensing barrier; operations, compute, validation, staff and maintenance still cost money. An agency-specific budget or cost saving is **unknown**.
- **Access/integration:** public reports exist. Whether target analysts lack raw polygons, APIs, timely processing or permissions is **unknown** until workflow interviews.
- **Language/connectivity:** no evidence reviewed establishes English as the blocking issue for target administrators or identifies their preferred local languages. Language and offline-export requirements should be validated, not asserted as a discovered need.

Differences between operational watchlists and inventory counts are not automatically trends. In particular, the widely cited ICIMOD **2020** inventory of **47 potentially dangerous lakes** covers Nepal, China and India, not Pakistan. [ICIMOD announcement][ICIMOD47]

### B3. Why NISAR specifically, and why now?

**NISAR is mandatory in the user's challenge brief.** The accessible local-organizer challenge page describes an interactive, open-source surface-change application using NISAR. The official challenge page was found but could not be fetched reliably, so detailed rules beyond the supplied brief are not independently verified here. [Organizer challenge][CHALLENGE]; [official URL][NASAChallenge]

The scientific case is complementary radar observations: cloud penetration and day/night operation, L-band scattering information, repeat coverage and already-geocoded terrain-corrected backscatter. Cloud independence is shared with Sentinel-1; it is not uniquely NISAR. NASA documents free/open access and an exact **12-day** repeat, with combined ascending/descending observations averaging approximately **6 days** globally; this is not a per-lake guarantee. [NASA overview][NASAOVERVIEW]

GCOV supplies calibrated RTC **gamma-0 power**, with HH/HV intensities represented by diagonal datasets **HHHH/HVHV**. Most land frequency-A products have **10 or 20 m** spacing depending on mode; frequency B is **80 m**. Inspect the actual granule rather than assume all target lakes receive the spike's mode. [ASF GCOV][GCOV]

**Why now is concrete:** calibrated, partially validated PROVISIONAL data were released **20 July 2026**, covering acquisitions from **17 June 2026** onward. ASF gives nominal Level 1–3 delivery latency of **36–72 hours**. Earlier BETA products differ in calibration/maturity, so mixing them can create apparent change. [ASF availability][AVAILABILITY] The team's real-data partial-read test makes a small prototype plausible, but operating costs and province-wide coverage have not been benchmarked. [Local spike](spike_findings.md)

**What remains unproven:** a net advantage over Sentinel-1 at these lakes; operational accuracy through snow/freeze/wind; dependable multiple-look coverage across upper KP; and the ability to distinguish meaningful change from processor/calibration changes. These should be measured, not claimed from wavelength alone.

### B4. Administrative decisions, effectiveness and limits

The following is a **proposed workflow**, grounded in the monitoring gaps above; it has not been validated with GBDMA, PDMA KP, NDMA or district users.

| Decision | Evidence the app should supply | What determines whether it helped |
|---|---|---|
| **Which lake requires analyst review?** | Source ID/polygon, date-specific area trend, uncertainty, quality masks, disagreement between looks, observation age and station status. | Valid changes found during previous observation gaps; manageable false-review workload. |
| **Where should a field team or camera/gauge check go?** | Confirmed new impoundment/growth, lack of adequate observation, downstream exposure and safe-access information supplied by the agency. | Analyst accepts/rejects rationale; inspection confirms the concern; travel saved or better prioritized. |
| **Which villages or infrastructure operators should be briefed?** | Existing validated flow-path/exposure layers linked to the source lake, affected access routes and agency contacts. | Correct recipients and timely briefing under official procedures. Proximity circles alone are not inundation modelling. |
| **When should expedited NISAR delivery be requested?** | Decision deadline, next suitable planned observation, current evidence gap and a documented reason faster delivery would matter. | Authorized liaison can act; delivered data are usable before the decision deadline. |
| **What happened after a possible release?** | Dated changes and corroborating downstream observations, with uncertainty retained. | Faster documented assessment; no misrepresentation of post-event detection as advance warning. |

**Urgent Response is not an on-demand orbit.** ASF describes expedited downlink/processing, normally for planned acquisitions, with estimated Level-2 availability of **6 hours** after acquisition. Requests are restricted to authorized users; public documentation does not establish NDMA's direct eligibility or a public GLOF activation form. Faster products can use less precise ancillary information. [ASF Urgent Response][UR] The app should prepare an evidence packet for an authorized liaison, not promise to “task NISAR” or deliver imagery within a fixed time after a user clicks. NASA documents a formal request/operations chain. [NASA workflow][URFLOW]

**Success measures — proposed, with targets to be agreed**

- Independent lake-presence recall by size, type, surface state and geometry; area/change error against dated reference polygons.
- Missed filling/drainage episodes, false review flags per lake-season, and uncertainty calibration.
- Fraction of the lake actually observable; additional valid observations during optical gaps; age of the oldest required look.
- Acquisition-to-availability, availability-to-review and review-to-action times measured separately.
- Analyst time required to reach a documented decision, field-check usefulness and acceptance of exported evidence.
- Performance against an existing Sentinel/optical workflow, including cases where NISAR contributes nothing.

There is no justified numerical success target or claim of lives saved yet. Historical event reconstruction and NISAR validation also require different datasets: the satellite cannot retroactively provide observations of pre-mission GLOFs.

**Limits:** this app cannot predict a cloudburst from a lake polygon, detect every hidden englacial water pocket, guarantee warning for an hours-scale breach, determine dam strength from dark pixels, or replace evacuation protocols. It also cannot turn partial terrain visibility into a reliable “safe/no lake” label. It can improve an evidence review only when the observations are relevant, timely and validated.

### B5. Draft problem statement and pitch

**Problem statement.** District and disaster-management teams in Gilgit-Baltistan and upper Khyber Pakhtunkhwa must decide which changing glacial-lake systems need inspection and which downstream communities or infrastructure operators need preparedness briefings. They already use ground stations, weather advisories and satellite monitoring, yet SUPARCO has documented cloud-related interruptions to lake-area assessment, and publicly available station records do not establish complete lake-specific coverage. [SUPARCO][SUPARCO]; [PMD][PMDUNIT] SARtale proposes an interactive, open-source NISAR lake-change watch that makes dated observations, uncertainty, viewing limitations and existing exposure information easy to review together. Its purpose is to improve inspection and preparedness decisions, with effectiveness tested against current workflows; it is not an automatic breach or cloudburst alarm.

**One-sentence pitch.** SARtale turns NISAR observations into a traceable glacial-lake review queue, helping disaster teams decide where to look next when cloud cover obscures optical imagery.

### B6. Ten hard questions and best available answers

1. **What does this add to SUPARCO's existing lake monitoring?** A testable contribution is additional usable radar evidence during documented optical gaps and reduced review effort. Area charts are already available; a net benefit has not yet been demonstrated. [SUPARCO][SUPARCO]

2. **Why NISAR rather than just Sentinel-1?** It satisfies the challenge and adds another wavelength and observation opportunities. Superior local lake accuracy is **unknown**. Benchmark it against Sentinel-1 and fusion, not against having no satellite data. [NISAR overview][NASAOVERVIEW]

3. **Which exact lakes will the first version monitor?** This report is a candidate register, not a finalized deployment list. Passu is a documented open-lake candidate; Shisper is a historical/status-validation case; small supraglacial sites are challenging tests. KP source polygons and several coordinate matches are **unresolved**. Agencies must confirm IDs and current status.

4. **Does the spike prove there is no Shisper lake?** No. It shows no persistent candidate satisfying the chosen composite rule within the tested AOI/window. Transient water, invalid views and the important filling season were not fully tested. Resolve the published polygon and validate individual dates. [Spike](spike_findings.md); [polygons][POLYGONS]; [phases][PHASES]

5. **How small a lake can you reliably detect?** **Unknown for this NISAR workflow.** Published Sentinel-1 inclusion thresholds are not reliability thresholds; GLO found much stronger performance only at larger lake sizes. Small hazardous ponds cannot be excluded just because the model misses them. [GLO][GLO]

6. **Can it give enough notice to evacuate?** No guaranteed lead time. A lake watch may support advance preparedness, but rapid drainage, orbital timing, processing and review can exceed the available interval. Immediate warnings remain with telemetry, field observations and official procedures. [PMD][PMDUNIT]; [ASF availability][AVAILABILITY]

7. **Can NDMA press a button to activate NISAR Urgent Response?** Direct eligibility is **not established**. A named authorized liaison and request route must be confirmed. Expedited processing cannot eliminate the wait for a suitable observation. [ASF Urgent Response][UR]

8. **Who authorizes an alert and handles a false positive?** Proposed answer: an agency-designated analyst owns review and existing authorities own public warning. No partner agreement or approved escalation protocol has been demonstrated. [Official warning chain][WARNINGCHAIN]

9. **What does it cost, and who maintains it after the hackathon?** Imagery is free/open and partial access was tested, but hosting, QA, staff, field validation and maintenance costs are **unknown**. No sustained funding or operating owner is established. [NASA][NASAOVERVIEW]; [spike](spike_findings.md)

10. **What evidence would convince an administrator to keep using it?** A prospective pilot showing validated additional observations, useful inspection prioritization and lower review burden without excessive false flags. Language, export formats, offline needs and acceptable error rates must be agreed with users; those requirements are **unknown**, not assumed.

## Appendix C — retained data-access research

**Yes: partial remote GCOV reads are supported.** ASF documents authenticated HTTPS streaming through earthaccess/fsspec and direct S3 access. Direct S3 is restricted to resources in **AWS us-west-2**, and NISAR requires its dedicated credential endpoint, https://nisar.asf.earthdatacloud.nasa.gov/s3credentials, rather than assuming the generic ASF endpoint. Discover asset URLs from catalogue results. [ASF earthaccess guide][EARTHACCESS]

Use a seekable remote file object with h5py, inspect the dataset metadata, and read only the lake's row/column slice. A bare remote URL is not the same as a configured h5py remote reader. Do not materialize the complete dataset and crop afterward. MAAP documents cloud-optimized HDF5 access and cache tuning; ASF's streaming notebook demonstrates spatial subsets. [MAAP][MAAP]; [ASF cookbook][STREAM]

HDF5 chunks, transport-cache blocks and computational chunks are different. Partial reads still fetch intersected chunks and metadata, so transfer volume exceeds the raw pixels and depends on layout/access pattern. Inspect chunks, compression, shape and datatype on each product; the spike's layout is not a universal guarantee. [h5py documentation][H5PY]; [spike](spike_findings.md)

The approximately **7 GB** file size and **24–43 MB** transfer are local test findings, not a universal GCOV specification. [Spike](spike_findings.md) Default earthaccess authentication searches for a netrc; an explicitly selected environment strategy with persistence disabled is the documented alternative for a no-netrc workflow. **No authentication was run and no netrc was read in this research.** [Authentication documentation][AUTH]

ASF's roadmap marks individual GCOV-layer extraction to Cloud-Optimized GeoTIFF as complete with a **June 2026** target/release entry, while layer spatial subsetting/reprojection remains marked pending for **Q4 2026**, and full HDF5 spatial subsetting for **2027**. These are roadmap statuses, not an independently tested service guarantee. Distinguish layer extraction from geographic cropping. [ASF roadmap][ROADMAP]

## Appendix D — prior art and defensible novelty claims

| Project | What can be established | What was missing, or cannot be assessed |
|---|---|---|
| **TengriSpacers, Space Apps 2025** | Official team record exists, but its indexed page reports administrator-hidden content; an author profile self-reports a Sentinel-1/OPERA RTC glacier-melt workflow. [Team][TENGRI]; [self-report][TENGRIPROFILE] | Source code, validation, lake-change uncertainty, NISAR implementation and agency workflow: **not verified**. Do not claim these were absent simply because the submission is inaccessible. |
| **Ice Exped, Space Apps 2021** | Official indexed submission describes automatic glacial-lake detection using Sentinel-1A from Earth Engine. [Submission][ICEEXPED] | Detailed implementation and operational validation **not verified**. It is sufficient to reject “first SAR glacial-lake app” as a safe novelty claim. |
| **GLakeMap** | Published Python workflow combines radar, optical data, terrain and random forest for lake mapping. [Paper][GLAKEMAP] | It is mapping prior art; a Pakistan operational warning integration is **not established** in the reviewed paper. |
| **CryoSentinel** | Public code/model project combines Sentinel-1, Sentinel-2 and DEM inputs. [Repository][CRYO] | Its README explicitly states single-snapshot segmentation, no explicit temporal model, no emitted confidence map and no GLOF-event prediction by the segmenter. It states no agency integration. Those limitations should not be generalized to all linked projects. |
| **AGFM** | Open-source SAR glacier-flow pipeline; README documents Sentinel-1 support. [Repository][AGFM] | NISAR support is outside its documented current support; lake delineation is outside its glacier-velocity scope, not a failed feature. |

The defensible proposed distinction is **traceable NISAR evidence tailored to GB/KP administrator decisions**, including missing-data handling, source identity, uncertainty and current-workflow integration. Whether that distinction is useful remains a pilot question.

## Evidence boundaries and remaining work

- Best missing dataset: an authoritative current lake-polygon/ID register joined to working sensor locations, measurement type, telemetry freshness and responsible office.
- Best missing validation: near-coincident reference outlines and frozen/open-water state for the actual NISAR target lakes, plus dated short-lived filling/drainage cases.
- Best missing user evidence: which monitoring interruption delayed a decision, what Sentinel products already cover it, and which additional observation would change that decision.
- No complete, consistently defined annual GB/KP GLOF series or GLOF-only economic-loss total for the requested historical period was found.
- Some publisher pages blocked full retrieval; coordinate or table facts available only through indexed text are identified where especially consequential. Published map frames are not fabricated centroids, and lake-source points are not substitutes for validated modern polygons.

## Sources

[HMA]: https://essd.copernicus.org/articles/15/3941/2023/essd-15-3941-2023.pdf "Shrestha et al. (2023), Earth System Science Data, Table 3"
[HMAMETA]: https://raw.githubusercontent.com/fidelsteiner/HMAGLOFDB/main/HMAGLOFDB_Metadata.yml "HMAGLOFDB field definitions"
[HMAGIT]: https://github.com/fidelsteiner/HMAGLOFDB "HMAGLOFDB development database and ICIMOD link"
[SHISPERMAP]: https://www.tandfonline.com/doi/pdf/10.1080/19475705.2021.1975833 "Muhammad et al., modern Shisper lake mapping, Figure 2"
[POLYGONS]: https://researchportal.port.ac.uk/en/datasets/dataset-for-multiple-phases-of-ice-dammed-lake-formation-and-drai/ "Lovell and Muhammad, published Shisper lake polygons"
[PHASES]: https://doi.org/10.1017/jog.2024.80 "Lovell and Muhammad, Multiple phases of ice-dammed lake formation and drainage, Journal of Glaciology"
[SHISPER22]: https://www.tandfonline.com/doi/full/10.1080/19475705.2023.2264460 "Causes and effects of Shisper glacial lake outburst flood event in Karakoram in 2022"
[SHISPEREVENTS]: https://pmc.ncbi.nlm.nih.gov/articles/PMC11369478/ "Assessing climate-driven impacts on Karakoram glacier surge"
[KHURDOPIN]: https://tc.copernicus.org/articles/12/95/2018/ "Steiner et al. (2018), The Cryosphere"
[PASSUCOORD]: https://doi.org/10.1016/j.rcar.2025.03.005 "Are area changes the primary indicator for predicting glacial lake outburst risks? Event table"
[HUNZA]: https://www.mdpi.com/2072-4292/13/9/1794 "Muneeb et al. (2021), Remote Sensing"
[SUPRA]: https://www.nepjol.info/index.php/IJE/article/view/27587/22804 "Monitoring Supraglacial Lakes Formation and Risk of Outburst Flooding in the Himalayan Cryosphere of Pakistan, International Journal of Environment"
[CPEC]: https://www.intechopen.com/chapters/73124 "Saifullah et al. (2020), Risks of Glaciers Lakes Outburst Flood along CPEC"
[PMDOLD]: https://www.pmd.gov.pk/rnd/rnd_files/vol8_issue15/1_Glaciers%20and%20Glacial%20Lakes%20under%20Changing%20Climate%20in%20Pakistan.pdf "Rasul et al., Glaciers and Glacial Lakes under Changing Climate in Pakistan"
[AWS]: https://www.undp.org/pakistan/press-releases/glof-ii-project-installs-automated-weather-system-aws-gilgit-baltistan-reduce-impact-flash-floods "UNDP Hassanabad AWS announcement"
[APR]: https://glof2pakistan.com/wp-content/uploads/2025/07/APR_2023.pdf "GLOF-II annual progress report 2023"
[MTE]: https://www.adaptation-fund.org/wp-content/uploads/2011/06/MTE-Report-GLOF-final-1.pdf "GLOF-I mid-term evaluation, May 2014"
[NDMAREPORT]: https://ndma.gov.pk/public/storage/publications/February2025/FzRu7mkrhqClBflmp9ni.pdf "NDMA report: vulnerable lakes and Booni event"
[GAUGES]: https://www.ndma.gov.pk/storage/advisories/May2026/6a0c3bbcd5ced.pdf "NDMA gauged-valley advisory, 19 May 2026"
[PIDALERT]: https://pid.gov.pk/site/press_detail/29492 "NDMA/NEOC GLOF advisory, 25 June 2025"
[BADSWAT26]: https://www.mdpi.com/2073-4441/18/19/2440 "Badswat debris-flow/river-blockage reconstruction"
[BADSWATSIZE]: https://www.mdpi.com/2072-4292/18/1/75 "Monitoring Glacier Debris Flows and Dammed Lakes in Badswat"
[BADSWATCHAIN]: https://orbit.dtu.dk/en/publications/determining-the-events-in-a-glacial-disaster-chain-at-badswat-gla/ "Determining the events in a glacial disaster chain at Badswat"
[APNIC]: https://apnic.foundation/technical-report/a-scalable-off-grid-early-warning-and-communication-system-for-glof-risk-reduction-in-climate-vulnerable-communities-in-pakistan/ "Implementer report on planned flood sensors"
[GOLENPMD]: https://www.pmd.gov.pk/rnd/rndweb/rnd_new/glof_alerts_advisories.php/R%20%26%20D.php "PMD Golen GLOF Update-II"
[GOLENAUDIT]: https://agp.gov.pk/SiteImage/Policy/PAR%20Golen%20Gole%20Hydropower%20Project.pdf "Auditor-General performance audit, Golen Gol Hydropower"
[WAPDA]: https://wapda.gov.pk/wp-content/uploads/2025/12/Annual-Report-2022-23_compressed-latest.pdf "WAPDA Annual Report 2022–23"
[KPPLAN]: https://epakp.gov.pk/wp-content/uploads/2025/03/Final-CCAAP-25-1-25.pdf "KP Climate Change Action Plan"
[UIB]: https://www.mdpi.com/2813-8740/2/4/13 "Khan et al., Upper Indus Sentinel-1 lake inventory"
[ZHANG]: https://pmc.ncbi.nlm.nih.gov/articles/PMC7037291/ "Zhang et al. (2020), International Journal of Environmental Research and Public Health"
[GLAKEMAP]: https://research-repository.st-andrews.ac.uk/bitstream/handle/10023/20441/Wangchuk_2020_SRS_Mapping_CC.pdf "Wangchuk and Bolch (2020), Science of Remote Sensing"
[GLO]: https://essd.copernicus.org/articles/18/5143/2026/ "Glacial Lake Observatory, Earth System Science Data"
[BALTORO]: https://tc.copernicus.org/articles/18/1085/2024/tc-18-1085-2024.html "Wendleder et al., Baltoro multisensor lake mapping"
[STROZZI]: https://nhess.copernicus.org/articles/12/2487/2012/nhess-12-2487-2012.html "Strozzi et al. (2012), Natural Hazards and Earth System Sciences"
[PALSAR]: https://www.researchgate.net/publication/241449869_Detection_of_glacier_lake_using_ALOS_PALSAR_data_at_Bhutan "Author abstract, Bhutan PALSAR lake detection"
[RESTEC]: https://www.restec.or.jp/about/publication-2010.html "RESTEC publication record"
[BRIEF]: https://www.undp.org/sites/g/files/zskgke326/files/2025-09/glof-ii-project-brief.pdf "UNDP GLOF-II Project Brief 2025"
[LAUNCH]: https://www.undp.org/pakistan/press-releases/provincial-launch-event-us37-million-undp-supported-glof-ii-project "UNDP GLOF-II provincial launch"
[FLOOD2010]: https://www.ndma.gov.pk/storage/publications/September2025/5a7DeS9RPoaFUxreIcmm.pdf "NDMA retrospective, Table 35"
[FLOOD2022]: https://ffc.gov.pk/wp-content/uploads/2023/11/Final-Annual-Report-2022-Oo-CEA-CFFC.pdf "Federal Flood Commission Annual Report 2022, Table 3.15"
[FLOOD2025]: https://www.ndma.gov.pk/storage/sitreps/October2025/oztOSIiYIDcY1OCXxsBV.pdf "NDMA final consolidated monsoon report, 2 October 2025"
[UNICEF2025]: https://www.unicef.org/media/179011/file/Pakistan-Humanitarian-Situation-Report-No.3-%28End-of-Year%29-31-December-2025.pdf.pdf "UNICEF year-end Pakistan situation report"
[PDNA]: https://thedocs.worldbank.org/en/doc/4a0114eb7d1cecbbbf2f65c5ce0789db-0310012022/original/Pakistan-Floods-2022-PDNA-Main-Report.pdf "Government-led Pakistan Floods 2022 PDNA, Table 1"
[GLOF2022]: https://www.adaptation-undp.org/sites/default/files/resources/glof-ii-flood_report.pdf "UNDP GLOF-II flood report, Annex B"
[SHISPERBRIDGE]: https://www.radio.gov.pk/07-05-2022/high-flood-in-shishper-glacier-damages-rcc-bridge-on-karakorum-highway-in-hunza "Radio Pakistan, Hassanabad bridge damage"
[BOONIIMC]: https://cdn1.internationalmedicalcorps.org/wp-content/uploads/2024/08/IntlMedCorps-Aug2024FloodResponsePakistan-SitRep01.pdf "International Medical Corps flood response report"
[PMDUNIT]: https://www.weather.gov.pk/rnd/page/46/about-glacier-monitoring-unit "PMD Glacier Monitoring Unit"
[REPAIR]: https://pa.epads.gov.pk/procurement/goods/107028/sbd "Government procurement: GLOF-II hydro-meteorological equipment repairs"
[SUPARCO]: https://space4climate.gov.pk/glof-status-update/ "SUPARCO GLOF status update, 2 July 2026"
[SUPARCOCAP]: https://space4climate.gov.pk/glaciers/ "SUPARCO glacier-monitoring capabilities"
[NEOC]: https://pid.gov.pk/site/press_detail/33290 "Government description of NEOC operations"
[WARNINGCHAIN]: https://library.ndma.gov.pk/storage/uploads/doc-files/NDMA___WINTER_CONTINGENCY_PLAN__JANUARY_TO_MARCH_2026_.pdf "NDMA official warning dissemination chain"
[UNOSAT]: https://unosat.org/products/4147 "UNOSAT Sentinel-1 Punjab flood map"
[ICIMOD47]: https://www.icimod.org/new-glacial-lake-inventory-report-released-47-potentially-dangerous-glacial-lakes-ranked/ "ICIMOD inventory geographic scope"
[CHALLENGE]: https://hackathlone.com/challenges/dancing-with-the-sars "Local organizer's Dancing with the SARs challenge page"
[NASAChallenge]: https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/ "Official challenge URL, retrieval incomplete"
[NASAOVERVIEW]: https://science.nasa.gov/mission/nisar/mission-overview/ "NASA NISAR mission overview"
[GCOV]: https://nisar-docs.asf.alaska.edu/gcov/ "ASF GCOV product guide and schema"
[AVAILABILITY]: https://nisar-docs.asf.alaska.edu/availability-overview/ "ASF data availability and processing latency"
[UR]: https://hyp3-docs.asf.alaska.edu/nisar-docs/urgent-response/ "ASF NISAR Urgent Response guide"
[URFLOW]: https://wwao.jpl.nasa.gov/documents/169/NASA_WWAO_2025_KA.pdf "NASA NISAR urgent-response request workflow"
[EARTHACCESS]: https://nisar-docs.asf.alaska.edu/earthaccess/ "ASF earthaccess streaming guide"
[MAAP]: https://docs.maap-project.org/en/ogc/science/NISAR/NISAR_access.html "MAAP NISAR access and cloud-optimized HDF5"
[STREAM]: https://asfopensarlab.github.io/NISAR_Cookbook/search-stream-nisar-asf-search/ "ASF spatial-subset streaming notebook"
[H5PY]: https://docs.h5py.org/en/stable/high/dataset.html "h5py datasets, slicing and chunks"
[AUTH]: https://earthaccess.readthedocs.io/en/v0.16.0/howto/authenticate/ "earthaccess explicit authentication strategies"
[ROADMAP]: https://hyp3-docs.asf.alaska.edu/nisar-docs/roadmap/ "ASF service roadmap"
[TENGRI]: https://www.spaceappschallenge.org/2025/find-a-team/tengrispacers/ "TengriSpacers official team record"
[TENGRIPROFILE]: https://kg.linkedin.com/in/dmitriipecherkin "Project author's self-reported work"
[ICEEXPED]: https://2021.spaceappschallenge.org/challenges/statements/space-for-change/teams/ice-exped/ "Ice Exped official submission"
[CRYO]: https://github.com/abzalabdrash/cryosentinel "CryoSentinel repository and stated limitations"
[AGFM]: https://github.com/ayush12gupta/AGFM "Automated Glacier Flow Mapping repository"
