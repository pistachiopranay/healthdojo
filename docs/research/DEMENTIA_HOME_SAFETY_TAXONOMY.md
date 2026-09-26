---
title: "HomeDojo Dementia Home-Safety Taxonomy and Evidence Base"
tags: [homedojo, dementia, alzheimers, home-safety, hazard-taxonomy, benchmark, ground-truth]
status: active
created: 2026-09-26
---

# HomeDojo Dementia Home-Safety Taxonomy and Evidence Base

Machine-readable taxonomy: `data/benchmarks/dementia/hazard_taxonomy.json` (15 hazards, 4 rooms). This document covers the instruments and guidance behind it, why dementia hazards differ from fall hazards, and what we left out.

**How to read the citations.** Claims marked **[verified]** were checked against the primary source during this session (2026-09-26). **[secondary]** means the claim came from a search summary or secondary page and the primary source was not opened. **[unverified]** means the claim is from memory and must be checked before it goes into a paper or pitch. All guideline lines below are **paraphrased in our own words**; no item text is reproduced.

---

## 1. Dementia home-safety instruments and checklists

| Instrument | Items / structure | Who uses it | Licensing / reuse |
|---|---|---|---|
| **HEAP, Home Environmental Assessment Protocol** (Gitlin, Schinfeld, Winter, Corcoran, Boyce, Hauck 2002) | Observational, room-by-room (entrance, living room, dining, kitchen, hallway, bathroom, bedroom). Per room: potential hazards (tripping/falling, electrical, accessible objects such as sharps and medications), adaptations (locks, latches, colour contrast to highlight objects), a clutter rating, and comfort. Bedroom section asks whether a mirror is present and visible. [verified, 2007 form PDF]. Search summaries report 192 items summed into hazard, adaptation and clutter indices [secondary]. **Note: published in *Disability and Rehabilitation* 24(1-3):59-71, not *The Gerontologist*.** [verified, reference line on the form] | OTs and trained research interviewers, in homes of people with dementia (built for the Gitlin environmental-skill-building trials) | Form states "All rights reserved", Gitlin and Corcoran [verified]. A copy is hosted by EHHI as part of a toolkit. **Cite and paraphrase; do not reproduce items.** |
| **SAS, Safety Assessment Scale for people with dementia living at home** (Poulin de Courval et al. 2006, *Can J Occup Ther* 73(2)) | Long form 32 questions, short screening form 19. Caregiver-answered frequency ratings (always / most of the time / occasionally / never), administered by a clinician. Validated in English and French on ~176 community-dwelling people with dementia in QC, AB, BC; good test-retest and inter-rater reliability [secondary, search summary of abstract]. Risks named include burns, falls, malnutrition and medication errors [verified, McGill newsroom]. | Home-care clinicians: OTs, nurses, physicians, social workers, physios | McGill says it was made publicly available online via CLSC Côte-des-Neiges [verified, McGill newsroom]. Still copyrighted; cite only. |
| **SAFER-HOME v3** (Chiu, Oliver; COTA Health) | 74 items in 12 domains rated 0-3; one domain is **wandering** [verified, NCOA/USC inventory, see `CLINICAL_HAZARD_TAXONOMY.md`]. Wandering-domain item wording not checked this session [unverified]. | OTs | Commercial manual; cite only. |
| **Alzheimer's Association Home Safety Checklist** (Rev. Aug 2025, with Procter & Gamble) | 2 pages, ~35 checkbox tips in sections: General, Kitchen, Laundry Room, Bathroom, Bedroom, Garage and Basement [verified, PDF] | Family caregivers | "© 2025 Alzheimer's Association. All rights reserved." [verified]. Paraphrase with attribution. |
| **NIA "Alzheimer's Caregiving: Home Safety Tips"** | Web page organised by room and topic, plus a depth-perception explainer [verified] | Family caregivers | US federal work, generally public domain [unverified for this page]; attribute anyway. |
| **Alzheimer's Society (UK) booklet 819 "Keeping safe and independent at home" / "Making your home dementia friendly"** | Booklet with sections on lighting, furniture and flooring, bathroom, kitchen; last reviewed March 2026 [verified, PDF] | People with dementia and families | "© Alzheimer's Society 2026. All rights reserved." [verified]. Paraphrase only. |

Sources: [HEAP form PDF (EHHI)](https://ehhi.com/sites/default/files/Toolkit/HEAP_Tool.pdf); [HEAP paper, PubMed 11827156](https://pubmed.ncbi.nlm.nih.gov/11827156/); [SAS paper, PubMed 16680910](https://pubmed.ncbi.nlm.nih.gov/16680910/); [SAS McGill newsroom](https://www.mcgill.ca/newsroom/channels/news/new-home-safety-assessment-scale-people-dementia-living-home-9966); [Alz Assoc home safety page](https://www.alz.org/help-support/caregiving/safety/home-safety); [Alz Assoc checklist PDF](https://www.alz.org/getmedia/dc740fbd-9cdc-4b64-b274-9fc9ee4ec64e/alzheimers-dementia-home-safety-checklist.pdf); [Alz Assoc wandering](https://www.alz.org/help-support/caregiving/stages-behaviors/wandering); [NIA home safety tips](https://www.nia.nih.gov/health/safety/alzheimers-caregiving-home-safety-tips); [Alzheimer's Society booklet 819 PDF](https://www.alzheimers.org.uk/sites/default/files/migrate/downloads/making_your_home_dementia_friendly.pdf).


**Stove / fire evidence.** Both US guides tell caregivers to disable or guard the stove (knob covers, knob removal, auto shut-off, gas off) [verified]. We did not open a primary epidemiological source on cooking-fire rates in dementia this session [unverified].

---

## 2. Why dementia hazards differ from falls-only hazards

The fall taxonomy (`CLINICAL_HAZARD_TAXONOMY.md`) asks: *can a person with limited mobility trip, slip or fail a transfer here?* Dementia adds two different failure modes, so the same object can be a different hazard, or a hazard only in this population:

1. **Judgement and memory (misuse).** The person may no longer recognise danger: leaving a burner on, swallowing a detergent pod or toiletries that look like food, taking pills twice, using a knife, gun or car unsafely, or walking out of an open door. NIA lists toothpaste, lotions and soap as items that may look and smell like food [verified]. Alz Assoc notes a person may forget they can no longer drive safely [verified, wandering page]. These hazards are about **access**, so the visual cue is "item is out and reachable" rather than "item is in the walkway".
2. **Perception (misreading the scene).** NIA says people with Alzheimer's often have changed depth perception, and gives the example of a change in floor pattern being taken for a step [verified]. Alzheimer's Society says stripes and patterns can make a surface look deeper or textured, dark rugs can look like obstacles or holes, shiny floors can look wet, and mirrors and artwork may become confusing as dementia progresses; a carer quoted in the booklet describes a parent taking her own reflection for someone else in the house [verified]. Low-contrast fixtures (white seat on white toilet on white floor) are hard to find; both NIA and Alzheimer's Society recommend contrasting colours [verified]. Contrast-sensitivity loss in Alzheimer's is well documented in the vision literature [unverified this session].

Consequence for the benchmark: a black bath mat is a *fall-prevention good* (non-slip mat) but a *dementia hazard* (read as a hole). A mirror is neutral in a falls audit but can trigger distress in dementia. A model must reason about the occupant, not only the object.

---

## 3. Benchmark taxonomy mapped to guidance

Guideline lines are paraphrased. "AA" = Alzheimer's Association, "AS" = Alzheimer's Society (UK).

| ID | Room | Hazard (visual) | Guidance (paraphrased) | Source | Status |
|---|---|---|---|---|---|
| DEM-K01 | Kitchen | Burner on / exposed stove knobs, no covers or auto-shutoff | Fit stove knob covers or remove knobs, shut off gas when not cooking, prefer auto shut-off appliances (AA). Add safety knobs and an automatic shut-off to the stove (NIA). | [AA checklist](https://www.alz.org/getmedia/dc740fbd-9cdc-4b64-b274-9fc9ee4ec64e/alzheimers-dementia-home-safety-checklist.pdf); [NIA](https://www.nia.nih.gov/health/safety/alzheimers-caregiving-home-safety-tips) | [verified] |
| DEM-K02 | Kitchen | Knives / sharps out on counter | Keep scissors, knives and other dangerous items locked away or out of the home (NIA); lock up sharp objects (AA). HEAP probes for sharp knives in the kitchen. | [NIA](https://www.nia.nih.gov/health/safety/alzheimers-caregiving-home-safety-tips); [AA checklist](https://www.alz.org/getmedia/dc740fbd-9cdc-4b64-b274-9fc9ee4ec64e/alzheimers-dementia-home-safety-checklist.pdf) | [verified] |
| DEM-K03 | Kitchen | Bleach / detergent pods out and unlocked | Store cleaning products including laundry pods and bleach out of sight, secured, in original containers, to prevent ingestion (AA); lock up household products including detergent pods (NIA). | [AA checklist](https://www.alz.org/getmedia/dc740fbd-9cdc-4b64-b274-9fc9ee4ec64e/alzheimers-dementia-home-safety-checklist.pdf); [NIA](https://www.nia.nih.gov/health/safety/alzheimers-caregiving-home-safety-tips) | [verified] |
| DEM-K04 | Kitchen | Medication bottles out on counter | Clear prescription drugs and vitamins off kitchen tables and counters; keep medications in a locked drawer or cabinet (AA). HEAP asks whether medications are accessible to the care recipient. | [AA checklist](https://www.alz.org/getmedia/dc740fbd-9cdc-4b64-b274-9fc9ee4ec64e/alzheimers-dementia-home-safety-checklist.pdf); [AA home safety](https://www.alz.org/help-support/caregiving/safety/home-safety) | [verified] |
| DEM-B01 | Bathroom | Razor and medications on sink counter | Lock away medicines and sharp items (NIA); HEAP's bathroom/bedroom probes cover razors, sharps and accessible medications. An NIA grooming page suggests an electric razor [secondary]. | [NIA](https://www.nia.nih.gov/health/safety/alzheimers-caregiving-home-safety-tips); [HEAP form](https://ehhi.com/sites/default/files/Toolkit/HEAP_Tool.pdf) | [verified] (razor-specific NIA line [secondary]) |
| DEM-B02 | Bathroom | White seat on white toilet on white floor | Pick bathroom fittings, including the toilet seat, in a colour that contrasts with wall and floor so they can be identified (AS). NIA recommends contrast for grab bars and walls vs floor. | [AS booklet 819](https://www.alzheimers.org.uk/sites/default/files/migrate/downloads/making_your_home_dementia_friendly.pdf); [NIA](https://www.nia.nih.gov/health/safety/alzheimers-caregiving-home-safety-tips) | [verified] |
| DEM-B03 | Bathroom | Dark / black mat on light floor | Dark rugs may be seen as obstacles or holes in the floor (AS). | [AS booklet 819](https://www.alzheimers.org.uk/sites/default/files/migrate/downloads/making_your_home_dementia_friendly.pdf) | [verified] |
| DEM-B04 | Bathroom | Plugged-in hair dryer by sink | Take small electrical appliances out of the bathroom and cover outlets (NIA). | [NIA](https://www.nia.nih.gov/health/safety/alzheimers-caregiving-home-safety-tips) | [verified] |
| DEM-R01 | Bedroom | Large mirror facing the bed | Limit the size and number of mirrors and place them deliberately, since reflections can confuse (NIA). Remove or cover mirrors if they confuse; carer describes a reflection being taken for an intruder (AS). HEAP bedroom item checks for a visible mirror. | [NIA](https://www.nia.nih.gov/health/safety/alzheimers-caregiving-home-safety-tips); [AS booklet 819](https://www.alzheimers.org.uk/sites/default/files/migrate/downloads/making_your_home_dementia_friendly.pdf) | [verified] |
| DEM-R02 | Bedroom | Bold high-contrast patterned rug | Avoid busy patterns; a floor-pattern change may be read as a step (NIA). Stripes and patterns can make surfaces look deeper and cause falls (AS). | [NIA](https://www.nia.nih.gov/health/safety/alzheimers-caregiving-home-safety-tips); [AS booklet 819](https://www.alzheimers.org.uk/sites/default/files/migrate/downloads/making_your_home_dementia_friendly.pdf) | [verified] |
| DEM-R04 | Bedroom | Space heater next to bedding | Remove portable space heaters (NIA); closely supervise heaters, electric blankets and heating pads in the bedroom to prevent burns (AA). | [NIA](https://www.nia.nih.gov/health/safety/alzheimers-caregiving-home-safety-tips); [AA checklist](https://www.alz.org/getmedia/dc740fbd-9cdc-4b64-b274-9fc9ee4ec64e/alzheimers-dementia-home-safety-checklist.pdf) | [verified] |
| DEM-E01 | Entry | Car keys hanging by the door | Take away access to car keys once the person has stopped driving (AA checklist); the person may forget they can no longer drive safely (AA wandering). | [AA checklist](https://www.alz.org/getmedia/dc740fbd-9cdc-4b64-b274-9fc9ee4ec64e/alzheimers-dementia-home-safety-checklist.pdf); [AA wandering](https://www.alz.org/help-support/caregiving/stages-behaviors/wandering) | [verified] |
| DEM-E02 | Entry | Front door open to outside / unsecured exit | Put deadbolts on exterior doors high or low, out of sight; camouflage or signal exits (AA wandering, AA checklist). SAFER-HOME has a wandering domain. | [AA wandering](https://www.alz.org/help-support/caregiving/stages-behaviors/wandering); [AA checklist](https://www.alz.org/getmedia/dc740fbd-9cdc-4b64-b274-9fc9ee4ec64e/alzheimers-dementia-home-safety-checklist.pdf) | [verified] |
| DEM-E03 | Entry | Clutter piles in walkway | Remove throw rugs, cords and excess clutter (AA); keep floors clear and ordered (AS). HEAP rates clutter per room. | [AA checklist](https://www.alz.org/getmedia/dc740fbd-9cdc-4b64-b274-9fc9ee4ec64e/alzheimers-dementia-home-safety-checklist.pdf); [HEAP form](https://ehhi.com/sites/default/files/Toolkit/HEAP_Tool.pdf) | [verified] |

---

## 4. Deliberately excluded (not visually renderable or not judgeable from one image)

These appear in the guidance but a still image cannot establish presence or absence, so they are out of the benchmark:

- **Water heater at 120 °F or below / anti-scald valves** (AA checklist, NIA): a setting, not a visible state.
- **Smoke, CO and natural-gas detectors working** (AA, NIA): a ceiling unit can be seen, but not whether it works; NIA notes people with Alzheimer's may not smell smoke or gas.
- **Door alarms, chimes, motion sensors, pressure mats, GPS/ID bracelets** (AA wandering): often hidden or indistinguishable from ordinary hardware.
- **Locked vs unlocked cabinets**: a closed cabinet does not show whether it is locked. We only score items that are visibly *out*.
- **Garbage disposal disconnected, washer/dryer locks, lint screens** (AA checklist): internal state.
- **Expired food, toxic plants or decorative fruit mistaken for food** (AA checklist): hard to judge reliably from renders.
- **Removed interior-door locks** (AA checklist): the risk (locking oneself in) is behavioural; lock hardware looks the same either way.
- **Behavioural and care-plan items** (routines, peak wandering times, poison-control number, supervision): not environmental.
- **Garage and basement items** (power tools, gasoline, ladders): out of the four rooms in scope.

---

## 5. Limitations

- **Not clinically validated.** The 15 hazards are chosen from caregiver guidance and instrument topics. None of HEAP, SAS or SAFER-HOME was administered, and no item-level crosswalk with permission exists.
- **Needs OT review.** Before any clinical claim, a dementia-specialist OT should review hazard definitions, severity ranking and the perceptual hazards (B02, B03, R01, R02), which are stage-dependent and person-specific. A mirror or patterned rug is not a hazard for everyone with dementia.
- **Guidance, not trials.** Most lines come from advocacy and government caregiver guidance, not RCT evidence per hazard. Gitlin's environmental interventions have trial evidence as bundles, not item by item [unverified this session].
- **Some primary sources not opened.** PubMed pages for HEAP and SAS were blocked by a captcha; item counts and reliability numbers for those are [secondary]. Betz firearm papers were not opened [secondary].
- **Copyright.** HEAP, SAS, SAFER-HOME, the AA checklist and the Alzheimer's Society booklet are all "all rights reserved". This file and the JSON use paraphrase and citation only.
