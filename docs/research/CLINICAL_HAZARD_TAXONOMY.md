---
title: "HomeDojo Clinical Home Fall-Hazard Taxonomy and Evidence Base"
tags: [homedojo, fall-prevention, home-safety, hazard-taxonomy, benchmark, arthroplasty, ground-truth]
status: active
created: 2026-09-26
---

# HomeDojo Clinical Home Fall-Hazard Taxonomy and Evidence Base

Machine-readable taxonomy: `data/hazard_taxonomy.json` (35 hazards, 6 rooms). This document covers the instruments behind it, the evidence, and the design choices.

**How to read the citations.** Claims marked **[verified]** were checked against the primary source during this session (2026-09-26). **[secondary]** means the claim came from a search summary or secondary page and the primary source was not opened. **[unverified]** means the claim is from memory or from a vendor, and must be checked before it goes into a paper or pitch.

---

## 1. Validated home-hazard instruments

| Instrument | Items / structure | Categories | Who uses it | Licensing / reuse |
|---|---|---|---|---|
| **CDC STEADI "Check for Safety"** (2017 brochure) | About 16 yes/no questions, each with a fix. [verified, counted from the PDF] | Stairs & Steps (indoor/outdoor), Floors, Kitchen, Bedrooms, Bathrooms, plus an "other things you can do" section (exercise, vision, meds) | Older adults and families, handed out by clinicians inside the STEADI workflow | US federal work, so the text is generally public domain. **But the brochure includes a Getty Images photo (seen in the PDF metadata), which is *not* public domain.** Quote or adapt the text with attribution; do not reuse the images. [verified PDF; public-domain status is general CDC policy, unverified for this file] |
| **HOME FAST** (Mackenzie, Byles, Higginbotham 2000) | 25 dichotomous items (hazard present / absent). A higher score means higher risk. | 7 domains: flooring, furniture, lighting, bathroom, storage, stairways/steps, mobility [verified, PMC8942624] | OTs and other health professionals. There is also a "Non-OT HOME FAST" version, plus a self-report online version (stopfallsathome.com.au) | The University of Sydney repository lists it as **"Copyright All Rights Reserved"** with open access to the PDF [verified]. Items are described in peer-reviewed papers. Cite and paraphrase freely; get permission from L. Mackenzie before reproducing item wording verbatim. |
| **Westmead Home Safety Assessment (WeHSA)** (Clemson 1997) | 72 items with detailed descriptors. Short and long forms. Takes about 1 hour. Content validity index 0.80 [secondary] | Sections include Internal/External Trafficways, Seating, Bedroom, Footwear, Medication Management (full section list not verified) | OTs and other professionals. It was the assessment used in the Pighills 2011 RCT | Commercial manual (Clemson, *Home Fall Hazards*, Co-ordinates Therapy Services, 1997, ISBN 9780646317137). **Copyrighted; cite, do not reproduce.** [secondary] |
| **HSSAT** (Tomita, Univ. at Buffalo; v5.0 2017) | Checklist covering ~10 indoor and outdoor areas (v5 added the garage), plus a solutions booklet and a professional hazard checklist. Content validity index 0.98, test-retest ICC 0.97, inter-rater 0.89; r = 0.65 against the CDC checklist [secondary, AJOT 2014] | Areas of the home (entrance, living room, kitchen, bedroom, bathroom, stairs, outdoor, garage, and others) | Community-dwelling older adults and informal caregivers (self-assessment) | **Free download.** UB states it is "available free of charge" [verified]. Still copyrighted: cite it, and ask UB before redistributing item text. |
| **SAFER-HOME v3** (Chiu, Oliver; COTA Health, Toronto) | 74 items in 12 domains, each rated for safety concern on a 0–3 scale. Interview plus observation [verified, NCOA/USC inventory] | Living situation, mobility, environmental hazards, kitchen, household, eating, personal care, bathroom/toilet, medications, addiction/abuse, leisure, communication & scheduling, wandering | OTs, typically as a pre-discharge or rehab outcome measure. Originally for older adults with physical or mental-health needs | Commercial manual (VHA Home HealthCare/COTA, on sale via Amazon). **Copyrighted; cite only.** [secondary] |
| **Housing Enabler** (Iwarsson, Slaug) | Environmental component has 188 items in the full version and 61 in the screening tool, plus a personal functional-limitation component. It calculates a person-environment fit "accessibility" score [secondary] | Outdoor, entrance, indoor, communication barriers | OTs and researchers doing accessibility (not fall-specific) assessment | **Commercial.** Sold by Veten & Skapen HB / Slaug Enabling Development; copyright held by Iwarsson & Slaug. Cite only; a license is needed to use the items. [secondary] |

Sources: [CDC Check for Safety PDF](https://www.cdc.gov/steadi/pdf/STEADI-Brochure-CheckForSafety-508.pdf); [NCOA/USC Home Assessment Inventory (2021)](https://homemods.org/wp-content/uploads/2021/06/USC.NCOA_.HomeAssessment.Inventory.2.-1.pdf); [HOME FAST repository, Univ. Sydney](https://ses.library.usyd.edu.au/handle/2123/14750); [HOME FAST photo/video reliability, PMC8942624](https://pmc.ncbi.nlm.nih.gov/articles/PMC8942624/); [HOME FAST Vietnamese validation, PMC10203153](https://pmc.ncbi.nlm.nih.gov/articles/PMC10203153/); [WeHSA content validity, Clemson 1999](https://journals.sagepub.com/doi/10.1177/030802269906200407); [HSSAT, Univ. at Buffalo](https://publichealth.buffalo.edu/rehabilitation-science/research-and-facilities/core-facilities/aging/home-safety-self-assessment-tool.html); [HSSAT psychometrics, AJOT 2014](https://research.aota.org/ajot/article/68/6/711/5911/Psychometrics-of-the-Home-Safety-Self-Assessment); [SAFER-HOME factor analysis, Chiu & Oliver 2006](https://journals.sagepub.com/doi/10.1177/153944920602600403); [Housing Enabler developments, Iwarsson 2012](https://journals.sagepub.com/doi/10.4276/030802212X13522194759978); [Housing Enabler manual, Lund](https://portal.research.lu.se/en/publications/housing-enabler-a-method-for-ratingscreening-and-analysing-access/).

### HOME FAST item topics (paraphrased)

These are the closest thing to a validated, compact, fall-focused item set. HomeDojo's `instrument_map.HOMEFAST` field uses these numbers. The item wording below is paraphrased. [verified, PMC8942624 Table 3/4]

1 Walkways free of clutter/cords · 2 Floor coverings in good condition · 3 Non-slip floor surfaces · 4 Loose mats secured · 5 Bed transfers · 6 Lounge chair transfers · 7 Adequate lighting · 8 Bedside light reachable · 9 Outdoor path lighting · 10 Toilet transfers · 11 Bath transfers · 12 Shower transfers · 13 Grab rail in bath/shower · 14 Slip-resistant bathroom mats · 15 Toilet close to bedroom · 16 Kitchen reach without climbing/bending · 17 Carrying meals · 18 Indoor stair rails · 19 Outdoor step rails · 20 Using stairs · 21 Step edges identifiable · 22 Entrance doors · 23 Outdoor paths in good repair · 24 Footwear · 25 Pets

**Directly relevant to HomeDojo:** a 2022 study rated HOME FAST from **photos and videos** instead of in person. Inter-rater agreement was Gwet's AC1 = 0.91 and test-retest was 0.92 (video) / 0.93 (photo). The sample was small: 18 stroke survivors and 20 OTs [verified, PMC8942624]. This supports image-based hazard rating as a clinically meaningful task, and shows OT agreement from images is a realistic ceiling to benchmark against.

### Licensing takeaways for HomeDojo (not legal advice)

- Hazard **concepts** (for example "loose rug on walkway") are ideas, not protected expression. HomeDojo's taxonomy uses **original wording** and cites the instruments through a crosswalk (`instrument_map`). This is the safe pattern.
- **Do not** ship verbatim item text from WeHSA, SAFER-HOME, Housing Enabler, or HOME FAST without written permission. The HSSAT is free but still copyrighted, so ask UB before redistributing it.
- CDC text can be quoted with attribution; exclude the brochure's stock photos.
- To claim "aligned with HOME FAST", ask Prof. Lynette Mackenzie (Univ. Sydney) for permission and ideally for OT raters. Her group has already published photo/video reliability work.

---

## 2. Evidence base

### 2.1 How many falls involve the environment

- **Rubenstein 2006 (Age & Ageing):** pooled 12 studies of carefully evaluated falls. "Accident/environment-related" was the most common attributed cause, with a **mean of 31% (range 1–53%)**. The text says "accounting for 30–50% in most series", and notes that many "accidental" falls come from an environmental hazard interacting with individual susceptibility. [verified, PDF Table 1] <https://pubmed.ncbi.nlm.nih.gov/16926202/>
- **Song et al. 2026, "Are We Missing the Environmental Factors in AI-Based Fall Risk Models?: A Systematic Review"** (PMC12889826). **This is a Research Square preprint (2 Feb 2026), not peer-reviewed.** [verified]
  - Of >20,000 records, **9 studies** met the inclusion criteria: 6 supervised ML on structured data and 3 computer vision/robotics.
  - Environmental factors are "underemphasized". Where they were included, AUC-ROC was 0.67–0.76.
  - It cites **79.2% of fall-related ED visits occurring at home**.
  - Hazards named: lighting, slippery surfaces, loose rugs, handrails, clutter, stairs, doorways, showers, lack of grab bars.
  - This is HomeDojo's clearest "gap" citation. <https://pmc.ncbi.nlm.nih.gov/articles/PMC12889826/>
- **Rugs and carpets:** a US NEISS analysis of ED-treated fall injuries involving rugs and carpets found the highest injury rates in older adults [secondary; exact counts unverified]. <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3591732/>

### 2.2 Does fixing the home work?

| Study | Design | Result | Status |
|---|---|---|---|
| **Clemson et al. 2023, Cochrane CD013258** (environmental interventions) | 22 RCTs, 8,463 people; 14 studies (5,830) on home fall-hazard reduction | Overall rate of falls **RaR 0.74 (0.61–0.91), −26%, moderate certainty**. In people **selected for higher fall risk: RaR 0.62 (0.56–0.70), −38%, high certainty**. In people **not** selected for risk: RaR 1.05 (0.96–1.16), no effect. Number of fallers overall RR 0.89; high-risk RR 0.74. Little evidence on serious injury. | [verified] <https://www.cochrane.org/evidence/CD013258_reducing-fall-hazards-within-environment> |
| **Gillespie et al. 2012, Cochrane CD007146** | 6 trials, 4,208 participants (home safety arm) | RaR 0.81 (0.68–0.97). More effective in higher-risk people and when delivered by an OT. | [secondary] <https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.CD007146.pub3/full> |
| **Pighills et al. 2011, JAGS** | 3-arm pilot RCT, n = 238, age 70+, prior fallers; used the WeHSA | OT-delivered: **IRR 0.54 (0.36–0.83)**. Trained non-OT assessor: IRR 0.78, not significant. | [secondary] <https://pubmed.ncbi.nlm.nih.gov/21226674/> |
| **Keall et al. 2015, Lancet (HIPI)** | Cluster RCT, 842 NZ households, all ages | Builder-installed rails, grab bars, outside lighting, step edging and slip-resistant surfacing gave **−26% medically treated home fall injuries (RR 0.74, 0.58–0.94)**. Benefit/cost ratio ≥ 6. | [secondary] <https://pubmed.ncbi.nlm.nih.gov/25255696/> |
| **OTIS RCT (UK, HTA 2021)** | OT home assessment and modification, age 65+ | Did not show a significant reduction in falls (details not re-verified). A useful negative result: implementation and targeting matter. | [secondary] <https://www.ncbi.nlm.nih.gov/books/NBK571969/> |
| Pre-discharge home assessment (integrative review) | 8 RCTs | Insufficient evidence of effect on falls, ADLs, or readmissions | [secondary, from local HomeReady research] <https://pmc.ncbi.nlm.nih.gov/articles/PMC8170965/> |

**Takeaway for HomeDojo:** the benefit comes from **detection plus remediation in high-risk people**, and it is strongest when a clinician (an OT) is involved. That argues for severity labels that are conditioned on the occupant's risk and post-op status (see `post_op_escalation_rule`). Hazard presence alone is not enough.

### 2.3 Falls after hip and knee replacement

- **Alasbali et al. 2025 (Cureus) meta-analysis:** 7 studies, follow-up 6–45.6 months. TKA fall findings were mixed, with a pooled RR of 0.49 versus pre-op across high heterogeneity. The single THA study reported **11.7%** fall incidence. Living alone was associated with **OR 3.63** for falls post-TKA, and female sex with about 3.7×. [verified, PMC12103641]
- Reported fall rates range from **0.8–2.7% in the first days** after surgery to **3.1–51.8% within 24 months**. Roughly a third of patients fall in the year after arthroplasty, and **most falls happen after discharge, at home**. [secondary, search summary of arthroplasty fall literature; exact primary not opened]
- Hip precautions after posterior-approach THA: no flexion past 90°, no adduction past midline, no internal rotation, typically for 6–12 weeks. Newer evidence suggests precautions may add little. Always follow the individual order. [secondary] <https://pmc.ncbi.nlm.nih.gov/articles/PMC6778163/>, <https://www.physio-pedia.com/Hip_Precautions>
- Walker width: standard walkers are about 25–29 in and narrow models 17.5–24.5 in, per vendor/consumer sources [unverified]. The ADA minimum door clear width is 32 in [secondary]. Many US bathroom doors are 24–28 in [unverified]. Kaiser's joint-replacement checklist says: "Ensure your walker fits through doorways, in your bathroom." [from local research, verified 2026-07-29]

### 2.4 Costs

- **CDC:** about **$80 billion** a year in medical costs for non-fatal older adult falls (2020); Medicare pays about two-thirds. Falls cause about 41,000 deaths, 3.6M ED visits, and 1.2M hospital stays a year among adults 65+ (the reference year for these counts is not confirmed). [secondary] <https://cdc.gov/falls/pdf/CDC-DIP_At-a-Glance_Falls_508.pdf>
- **Florence et al. 2018 (JAGS):** medical costs of fatal and non-fatal falls, about $50B in 2015 (from memory). [unverified] <https://pubmed.ncbi.nlm.nih.gov/29512120/>
- **AHRQ:** average 30-day readmission cost was **$16,300 (2020)**. [from local HomeReady research; source AHRQ] <https://www.ahrq.gov/data/infographics/hospital-readmission-costs.html>
- **CMS THA/TKA:** Medicare 30-day readmission fell from 4.4% to 4.1% (2016–2020). The Hospital Readmissions Reduction Program penalty is capped at 3% of base DRG payments. [from local research] <https://www.cms.gov/files/document/2024-national-impact-assessment-report.pdf>
- **TJA 90-day readmissions:** about 5.6%, with an average claim of about **$62,173**; periprosthetic fracture admissions average about **$100,845**. [secondary; attribution to specific papers not confirmed, possibly J Arthroplasty 2019 and Bido et al. 2024 HSS J] <https://www.arthroplastyjournal.org/article/S0883-5403(19)30074-9/abstract>, <https://pmc.ncbi.nlm.nih.gov/articles/PMC11393636/>

---

## 3. Taxonomy design

**Scope.** 35 hazards that can be detected from photos or video of a home, grouped into 6 rooms: bathroom 8, bedroom 5, stairs 6, kitchen 4, living/general floors 7, entry 5. Cross-room hazards carry an `also_in` list.

**Derivation.** I took the union of hazard concepts across CDC Check for Safety, HOME FAST, HSSAT, and WeHSA. I kept only those with a visual signature and added arthroplasty-specific checks from discharge checklists: walker clearance, seat and toilet heights, and tub step-over. Non-visual items (medications, footwear behavior, cognition, SAFER-HOME's addiction/wandering domains) were dropped.

**Fields per hazard (JSON):**

| Field | Contents |
|---|---|
| `id` | Hazard identifier |
| `room`, `also_in` | Primary room, plus other rooms where it applies |
| `name` | Short hazard name |
| `visual_description`, `detection_cues` | What an annotator or model should look for |
| `visual_detectability` | `full`, `partial` (needs scale, depth, or night images), or `absence reasoning required` |
| `severity.low/medium/high` | Hazard-specific rubric |
| `post_op` | `walker`, `hip_precautions`, `weight_bearing` notes, plus an `escalate` flag |
| `recommended_fix`, `dme` | Remediation |
| `instrument_map` | Crosswalk to CDC section, HOME FAST item number, HSSAT area, WeHSA section |
| `evidence` | URLs |

**Global severity scale.**

- **High:** likely to cause a fall or injury during ordinary use, or blocks a task the post-op plan requires.
- **Medium:** risk depends on conditions such as darkness, wet floors, or carrying things.
- **Low:** minor contributor.

**Escalation rule:** if the occupant uses a walker, has hip precautions, or has restricted weight-bearing, escalate hazards where `escalate` is true by one level.

**Benchmark implications.**

1. **Absence hazards.** Many high-severity labels are *absences*, such as no grab bar or no rail. Models that detect only objects will miss them. Evaluate them separately.
2. **Measurement hazards.** Door width, bed height, toilet height, and path width need a scale reference such as a tape-measure photo, a known object, or LiDAR/RoomPlan depth. Label them `partial` and report them as a separate track.
3. **Person-conditioned severity.** Condition severity on a patient profile (walker, THA posterior with precautions, WB status). This matches the Cochrane finding that benefit concentrates in high-risk people.
4. **Human ceiling.** OT agreement from images (AC1 about 0.91 on HOME FAST) is the reference ceiling for the benchmark.

---

## 4. Taxonomy

Post-op constants used below:

- Walker outer width: 24–26 in typical.
- Door clear width: 32 in (ADA 404.2.3). Path clear width: 36 in (ADA 403.5.1). The ADA section numbers are from memory [unverified].
- Raised toilet seat: adds 3–4 in.
- Hip precautions: ≤90° flexion, no adduction past midline, no internal rotation.
- Grab bar height: 33–36 in [unverified].
- Toilet seat height: 17–19 in [unverified].

"Maps to" gives the CDC section and HOME FAST item number(s). Full crosswalk, including HSSAT and WeHSA, is in the JSON.

### Bathroom

| ID | Hazard | Visual description | Severity (low / med / high) | Post-op relevance | Fix / DME | Maps to |
|---|---|---|---|---|---|---|
| BATH-01 | No grab bar at tub/shower | Tub or shower enclosure with no wall-mounted, load-rated grab bar on entry wall or back wall; bare tile/surround at hand height. | L: Walk-in shower with bench and fixed support elsewhere within reach / M: Walk-in shower, no bar, occupant ambulatory without device / H: Tub-shower combo requiring step-over with no bar, or any occupant using walker | **walker**: Walker cannot enter tub; transfer needs fixed support; **hip precautions**: Step-over flexes hip; bar needed for controlled transfer; **weight bearing**: NWB/TDWB cannot step over tub wall safely without bar + transfer bench (escalate +1) | Install wall-anchored grab bar(s) (entry vertical + back horizontal); Clamp-on tub rail as temporary measure | CDC: Bathrooms; HOME FAST #13 |
| BATH-02 | No support at toilet | Toilet with no grab bar, toilet safety frame, or sturdy fixed support within reach on either side. | L: Sturdy vanity edge within reach and occupant independent / M: No support, occupant independent / H: No support and occupant post-op, uses walker, or has hip precautions | **walker**: Walker is not a stable push-off for sit-to-stand on toilet; **hip precautions**: Needs armrests to lower without flexing >90 degrees; **weight bearing**: Arm support offloads operated leg (escalate +1) | Toilet safety frame or raised seat with arms; Wall grab bar beside toilet | CDC: Bathrooms; HOME FAST #10 |
| BATH-03 | Non-load-rated fixture positioned as support | Towel bar, toilet-paper holder, soap dish, shower door handle, or glass door in the location a person would grab during a transfer, with no grab bar present. | L: Fixture present but a proper grab bar also within reach / M: Fixture is only thing within reach, occupant independent / H: Fixture is only support and occupant uses walker / post-op | **walker**: Walker users reach for nearest fixed object; **hip precautions**: Uncontrolled descent risks flexion >90 degrees; **weight bearing**: Offloading onto fixture that fails -> fall onto operated side (escalate +1) | Replace/supplement with anchored grab bar; Remove suction-cup handles for load-bearing use | CDC: Bathrooms; HOME FAST #13 |
| BATH-04 | Slippery tub/shower floor | Glossy tub or shower base with no non-slip mat, adhesive strips, or textured surface. | L: Textured base, no strips / M: Smooth base, no strips, walk-in shower / H: Smooth tub base with step-over, no strips | **walker**: Cannot use walker inside wet area; **hip precautions**: Slip causes uncontrolled flexion/adduction; **weight bearing**: Restricted-WB patient cannot recover balance on operated leg (escalate +1) | Non-slip mat or adhesive strips; Anti-slip treatment | CDC: Bathrooms; HOME FAST #14 |
| BATH-05 | High tub step-over without transfer aid | Bathtub (or tub-shower combo) with side wall typically ~14-20 in high that must be stepped over to shower; no transfer bench or shower chair present. | L: Walk-in shower also available / M: Tub is only bathing option, occupant independent / H: Tub is only bathing option and occupant post-op (hip/knee) or uses walker | **walker**: Walker cannot be used across tub wall; **hip precautions**: Stepping over tub wall commonly exceeds 90 degree flexion; **weight bearing**: Requires single-leg stance on one limb (escalate +1) | Tub transfer bench + handheld shower; Sponge-bathe until cleared; Long-term: tub-to-shower conversion | CDC: Bathrooms; HOME FAST #11 |
| BATH-06 | Low toilet seat | Standard-height toilet (about 15 in seat) with no raised seat, riser, or frame; seat noticeably below user knee height. | L: Comfort-height (17-19 in) toilet / M: Standard low toilet, occupant not post-op / H: Low toilet and occupant has hip precautions or post-TKA limited knee flexion | **walker**: Sit-to-stand from low seat is hardest transfer with walker; **hip precautions**: Low seat forces hip flexion >90 degrees; **weight bearing**: Stand-up loads operated leg heavily (escalate +1) | Raised toilet seat (3-4 in) with arms; Toilet safety frame; Bedside commode over toilet | CDC: Bathrooms; HOME FAST #10 |
| BATH-07 | Loose bath mat or rug on bathroom floor | Fabric bath mat, towel, or small rug on hard/wet floor, without rubber backing; curled or bunched edges. | L: Rubber-backed flat mat outside wet zone / M: Unbacked mat outside shower / H: Curled/bunched mat in walker path or at shower exit | **walker**: Walker legs catch mat edges; **hip precautions**: Trip leads to uncontrolled twisting (escalate +1) | Remove mat; Replace with low-profile rubber-backed mat; Double-sided rug tape | CDC: Floors; HOME FAST #4,14 |
| BATH-08 | No shower seat or handheld shower | Shower area with fixed overhead showerhead only and no shower chair/bench or built-in seat. | L: Occupant can stand long periods and has grab bars / M: No seat, occupant has balance/endurance limits / H: No seat and occupant post-op / uses walker | **walker**: Cannot stand unsupported for bathing; **hip precautions**: Washing feet/legs while standing requires bending past 90 degrees; **weight bearing**: Prolonged standing on restricted limb (escalate +1) | Shower chair with back; Handheld shower on slide bar; Long-handled sponge | CDC: Bathrooms; HOME FAST #12 |

### Bedroom

| ID | Hazard | Visual description | Severity (low / med / high) | Post-op relevance | Fix / DME | Maps to |
|---|---|---|---|---|---|---|
| BED-01 | Bed height inappropriate | Mattress top well below knee height (low platform/futon, deep soft mattress) or so high that feet cannot reach floor when seated. | L: Slightly low, firm edge / M: Clearly low or high, occupant not post-op / H: Low bed with hip precautions, or high bed requiring hop-down | **walker**: Walker needs level stand-up from bed edge; **hip precautions**: Hip must stay above knee when seated; **weight bearing**: Hop-down from high bed loads operated leg (escalate +1) | Bed risers or remove box spring to target knee-height seat; Firm mattress edge; Bed rail/assist handle | CDC: Bedrooms; HOME FAST #5 |
| BED-02 | No reachable bedside light | No lamp or switch within arm's reach of the bed; nightstand absent or bare; wall switch only at door. | L: Lamp present but awkward to reach / M: No bedside light, room has nightlight / H: No bedside light and path to bathroom dark | **walker**: Getting up in dark while positioning walker; **hip precautions**: Reaching across bed may rotate/adduct hip; **weight bearing**: Nocturia + opioid use increases night risk (escalate +1) | Bedside lamp or touch lamp; Remote/smart switch; Motion-sensor light | CDC: Bedrooms; HOME FAST #8 |
| BED-03 | Dark bed-to-bathroom path | Hallway/route from bed to toilet without nightlights or motion lighting; unlit hallway. | L: Short route with partial ambient light / M: Unlit route, no obstacles / H: Unlit route with obstacles, level change, or rug | **walker**: Night trips with walker; **weight bearing**: Opioids/sedation, nocturia (escalate +1) | Plug-in or motion-sensor nightlights along route; Bedside commode for early post-op nights | CDC: Bedrooms; HOME FAST #7,15 |
| BED-04 | Floor clutter around bed | Clothes, shoes, bags, boxes, or laundry on floor beside bed or in the path to the door. | L: Small items against wall, not in path / M: Items near bed edge / H: Items directly in stand-up zone or walker path | **walker**: Walker legs snag; **hip precautions**: Picking items up requires bending past 90 degrees (escalate +1) | Clear floor; bins at waist height; Reacher for dropped items | CDC: Floors; HOME FAST #1 |
| BED-05 | Insufficient walker clearance around bed | Bed pushed against wall or furniture leaving a narrow gap (less than about 30-36 in) on the exit side; no room to position a walker. | L: Gap tight but occupant not using device / M: Gap <36 in, device user can still pass / H: Gap narrower than walker width | **walker**: Walker (24-26 in) plus feet needs ~30-36 in; **hip precautions**: Exit on correct side may be dictated by surgery side (escalate +1) | Rearrange furniture for clear exit side; Move bed to first floor if needed | CDC: Floors; HOME FAST #1,5 |

### Stairs

| ID | Hazard | Visual description | Severity (low / med / high) | Post-op relevance | Fix / DME | Maps to |
|---|---|---|---|---|---|---|
| STAIR-01 | Missing handrail or rail on one side only | Indoor staircase with no handrail, or a rail on only one side. | L: One rail, 1-2 steps / M: One rail on full flight / H: No rail, or one rail on the side opposite the stronger hand/unoperated leg for a post-op user | **walker**: Walker cannot be used on stairs; rail + cane/crutch technique required; **weight bearing**: Restricted WB requires rail for step-to pattern ('up with good, down with bad') (escalate +1) | Install rails both sides, full length; Relocate bedroom to ground floor during recovery | CDC: Stairs & Steps; HOME FAST #18 |
| STAIR-02 | Handrail loose, short, or not graspable | Rail that stops before top/bottom step, is wobbly or detached, is a wide flat board, or is obstructed by objects. | L: Minor gap at end / M: Rail short by one or more steps / H: Loose/broken or ungraspable rail on only rail | **weight bearing**: Rail bears substantial load in restricted-WB stair climbing (escalate +1) | Repair/secure rail; Extend rail full length; Add round graspable rail | CDC: Stairs & Steps; HOME FAST #18,19 |
| STAIR-03 | Objects on stairs | Shoes, papers, laundry baskets, books or other items resting on treads. | L: Item against wall on wide stair / M: Item on a tread / H: Items on multiple treads or at top step | **hip precautions**: Picking up requires bending (escalate +1) | Clear stairs; never store items on treads | CDC: Stairs & Steps; HOME FAST #1 |
| STAIR-04 | Poor stair lighting | Stairway without overhead light, burned-out bulb, or light switch only at one end. | L: Lit but dim / M: Switch at one end only / H: No working light on regularly used stairs |  (escalate +1) | Overhead light with switches at top and bottom; Illuminated switches; LED stair lights | CDC: Stairs & Steps; HOME FAST #7 |
| STAIR-05 | Undefined step edges / loose stair covering | Patterned or same-color carpet hiding tread edges; loose, torn or worn carpet; no contrasting nosing strip. | L: Low contrast only / M: Worn carpet or no edge marking on full flight / H: Loose/torn carpet on tread | **weight bearing**: Misjudged step loads operated leg suddenly (escalate +1) | Secure/replace carpet; Contrasting anti-slip nosing strips | CDC: Stairs & Steps; HOME FAST #21 |
| STAIR-06 | Broken or uneven steps | Cracked, missing, sloped or inconsistent-height treads/risers. | L: Cosmetic damage / M: Noticeable unevenness / H: Broken/missing tread or large riser variation |  (escalate +1) | Repair steps; Temporary ramp at entry | CDC: Stairs & Steps; HOME FAST #20,23 |

### Kitchen

| ID | Hazard | Visual description | Severity (low / med / high) | Post-op relevance | Fix / DME | Maps to |
|---|---|---|---|---|---|---|
| KIT-01 | Frequently used items stored high | Everyday dishes, food, or cookware on upper shelves/cabinets above shoulder height; step stool nearby. | L: Occasional items high / M: Daily items high / H: Daily items high and step stool/chair used to reach | **walker**: Reaching overhead while holding walker destabilizes (escalate +1) | Move daily items to waist-to-shoulder height; Reacher | CDC: Kitchen; HOME FAST #16 |
| KIT-02 | Frequently used items stored low | Daily-use pots, pet food, or supplies in floor-level cabinets, low drawers, or on the floor. | L: Occasional items low / M: Daily items low, not post-op / H: Daily items low and hip precautions active | **hip precautions**: Retrieval requires hip flexion >90 degrees; **weight bearing**: Squatting loads operated knee (escalate +1) | Relocate to counter height; Reacher | CDC: Kitchen; HOME FAST #16 |
| KIT-03 | Unstable step stool or chair used for reaching | Step stool without handrail, folding stool, or kitchen chair positioned under upper cabinets. | L: Sturdy stool with rail, stored away / M: Stool without rail / H: Chair or wobbly stool used as ladder | **walker**: Any climbing contraindicated early post-op; **hip precautions**: Stepping up flexes hip; **weight bearing**: Contraindicated under restricted WB (escalate +1) | Remove stool during recovery; Stool with handle bar; Relocate items | CDC: Kitchen; HOME FAST #16 |
| KIT-04 | Slippery floor / loose mat at sink or stove | Glossy floor, visible spills, or unbacked runner mat in front of sink/stove. | L: Backed flat mat / M: Unbacked mat or glossy floor / H: Curled mat or visible wet floor in walker path | **walker**: Walker wheels/glides skid or catch (escalate +1) | Remove or secure mat; Clean spills; non-slip floor finish | CDC: Floors; HOME FAST #3,4 |

### Living areas / general floors

| ID | Hazard | Visual description | Severity (low / med / high) | Post-op relevance | Fix / DME | Maps to |
|---|---|---|---|---|---|---|
| LIV-01 | Throw rug / loose mat on walkway | Area rug, runner, or throw rug with curled or lifted edges, no visible anchoring, on a common walking route. | L: Large flat rug under furniture / M: Small unsecured rug off main path / H: Curled/bunched rug on main route or at doorway | **walker**: Walker legs/wheels catch rug edges; **hip precautions**: Trip-induced twist risks dislocation (escalate +1) | Remove rug; Double-sided tape or non-slip underlay | CDC: Floors; HOME FAST #4 |
| LIV-02 | Cords or wires across walkway | Extension, lamp, phone, or charging cords crossing a floor path rather than routed along walls. | L: Cord along wall edge / M: Cord crossing low-traffic area / H: Cord crossing main route or doorway | **walker**: Wheels/legs catch cords (escalate +1) | Reroute along walls; Cord covers; Add outlet | CDC: Floors; HOME FAST #1 |
| LIV-03 | Cluttered or narrowed walking path | Furniture, coffee tables, ottomans, boxes, or piles narrowing a route so the person must weave; items on floor. | L: Minor clutter, path >36 in / M: Must walk around furniture / H: Path narrower than walker or objects underfoot | **walker**: Walker requires straight, clear path ~30-36 in; **hip precautions**: Pivoting/twisting around obstacles risks rotation (escalate +1) | Rearrange/remove furniture; Clear floor items | CDC: Floors; HOME FAST #1 |
| LIV-04 | Low or soft seating without armrests | Deep sofa, recliner, or low chair without firm arms; seat well below knee height. | L: Firm armchair available too / M: Only low/soft seating / H: Only low/soft seating and hip precautions or post-TKA | **walker**: Hard sit-to-stand with walker; **hip precautions**: Low seat forces >90 degree flexion; **weight bearing**: Push-up loads operated leg (escalate +1) | Firm chair with arms at knee height or higher; Furniture risers; Firm cushion | CDC: -; HOME FAST #6 |
| LIV-05 | Poor lighting or glare | Dim room, dark corners, bare bulbs causing glare, or strong window glare on glossy floor. | L: Dim corners only / M: Room generally dim / H: Main route dark or glare obscures floor edges/level changes |  | Brighter/diffuse bulbs; Switches at room entrances; Blinds for glare | CDC: -; HOME FAST #7 |
| LIV-06 | Unmarked level change / step-down between rooms | Sunken living room, single step between rooms, or raised floor transition strip without contrast or rail. | L: Small (<0.5 in) beveled transition / M: Single marked step / H: Single unmarked step on main route | **walker**: Walker must be lifted over step; front wheels catch; **weight bearing**: Unexpected step loads operated limb (escalate +1) | Contrasting edge tape; Threshold ramp; Rail or grab pole at step | CDC: -; HOME FAST #21 |
| LIV-07 | Pets and pet items underfoot | Pet beds, bowls, toys, or the pet itself in walking routes. | L: Items against wall / M: Items in secondary path / H: Items on main route or large active dog | **walker**: Pets tangle in walker; **hip precautions**: Feeding pet at floor level requires bending (escalate +1) | Relocate bowls/beds out of paths; Elevated feeder; Pet care help during recovery | CDC: -; HOME FAST #25 |

### Entry / exterior

| ID | Hazard | Visual description | Severity (low / med / high) | Post-op relevance | Fix / DME | Maps to |
|---|---|---|---|---|---|---|
| ENT-01 | Exterior steps without handrail | Porch or entry steps (one or more) without a handrail on either side. | L: Single low step with door frame support / M: 2-3 steps, no rail / H: 3+ steps, no rail, or occupant post-op | **walker**: Walker unusable on steps; entry is required at discharge; **weight bearing**: Restricted-WB stair technique needs rail (escalate +1) | Install exterior rail(s); Temporary modular ramp | CDC: Stairs & Steps; HOME FAST #19 |
| ENT-02 | Raised threshold or door sill | Raised door sill, sliding-door track, or shower curb at a doorway that must be stepped over. | L: Beveled low threshold / M: Raised sill 0.5-1 in / H: Sill >1 in or sliding track on required route | **walker**: Front wheels/legs catch (escalate +1) | Threshold ramp; Replace sill | CDC: -; HOME FAST #22 |
| ENT-03 | Uneven or damaged outdoor path | Cracked, heaved, or sloped walkway; loose pavers; gravel; debris or leaves on path to door. | L: Minor cracks / M: Uneven pavers or gravel / H: Heaves/trip lips or slippery surface on only access route | **walker**: Walker wheels stick in gravel/cracks (escalate +1) | Repair path; Clear debris; Slip-resistant surfacing | CDC: -; HOME FAST #23 |
| ENT-04 | Poor exterior lighting | No porch light, burned-out fixture, or unlit steps/path to the door. | L: Porch light only / M: Steps unlit / H: Steps and path unlit on regular route |  | Motion-sensor exterior lights; Step lights | CDC: Stairs & Steps; HOME FAST #9 |
| ENT-05 | Doorway too narrow for walker | Door opening (often bathroom or older interior doors, ~24-28 in) where clear width with door open is less than prescribed walker width plus hand clearance; door that cannot open fully. | L: Clear width >= 32 in / M: Clear width 28-32 in with walker 24-26 in / H: Clear width < walker width + 2 in on required route (bathroom/bedroom/entry) | **walker**: Core walker clearance check (24-26 in walker; 32 in ADA door); **hip precautions**: Side-stepping through narrow door encourages twisting; **weight bearing**: Leaving walker to pass through violates WB orders (escalate +1) | Offset (swing-clear) hinges (+~1.5-2 in); Remove door temporarily; Narrower walker model; Use alternate bathroom / bedside commode | CDC: -; HOME FAST #22 |


---

## 5. Open items before using this as ground truth

1. **OT/PT review** of the severity rubrics and the post-op notes. The taxonomy is authored from the literature and is not clinically validated.
2. **Permissions:** contact L. Mackenzie (HOME FAST) and UB (HSSAT) if we want to publish a crosswalk that uses item wording.
3. **Verify** the numbers marked [secondary] or [unverified] against primary sources: ADA section numbers and heights, CDC cost/death year, TJA readmission cost attributions, OTIS results.
4. Consider a small **inter-rater study** (2–3 OTs × ~100 home images) to set a human ceiling for HomeDojo labels, reusing the HOME FAST photo/video method (PMC8942624).

## Related local research

- `/Users/pranayatz/.buzz/RESEARCH/HOMEREADY_APPENDIX_RESEARCH_2026_07_29.md`: readmission, TEAM, and remote-assessment sources
- `/Users/pranayatz/.buzz/RESEARCH/HOMEREADY_STORYHOUSE_CURRENT_BURDEN_AND_SLIDE2_REVISION_2026_08_10.md`: Cochrane 2023 and MedPAC figures
