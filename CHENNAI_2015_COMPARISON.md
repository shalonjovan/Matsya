# Chennai December 2015 vs MATSYA simulation — comparison

**Branch:** `comparison` · **Sim:** `chennai-2015-dec1` (`407c352a-…`) · **Date run:** 2026-09-06
**Method:** documented historical facts (sourced below) vs one 24h scenario sim. Qualitative — no observed depth rasters exist to score against, so this is structured comparison, not calibration.

## 1. Documented event facts (sources)

- **Rain, Dec 1 08:30 → Dec 2 08:30:** area-average 286mm; stations 77–494mm; Tambaram 490mm; Nungambakkam ~290mm; airport 266mm (WWA/IMD via World Weather Attribution; Wikipedia). November city total ~1200mm, ~3× average → saturated antecedent.
- **Chembarambakkam releases:** 29,000 cusecs × 21h (Dec 1 18:00 → Dec 2 15:00) into the Adyar; full tank 85.4 ft / 3645 mcft; warnings at 7,500 → 20,000 cusecs (CAG via The Hindu/Economic Times).
- **Poondi → Cooum:** 8,552 cusecs Dec 1 → 30,200 cusecs Dec 2 (CAG rapid assessment).
- **Depths:** ~4.5–5.5 ft (1.4–1.7m) in colonies around Chembarambakkam (assessment report); neck-deep water, rooftop rescues in Mudichur/Tambaram; Velachery devastated (built on old lake bed); Pallikaranai marsh acted as flood sink; Narayanapuram overflow cut the Velachery–Tambaram road; Saidapet/Adyar/Kotturpuram slums flooded (The Hindu, TNIE, VOA).

## 2. Scenario setup (what we simulated)

- **Bbox:** big square 80.15,13.08–80.20,13.13 (~30 km², Guindy–Velachery edge–Pallikaranai north). NOTE: Mudichur/Tambaram/Chembarambakkam lie outside it.
- **Rain:** 24h variable burst peaking overnight (~350mm total, peak ~110mm/hr) — matches the Dec 1 overnight-peak structure, Tambaram-scale totals.
- **Lakes:** `initialFillPct: 100` — encodes the saturated November + full-tank antecedent.
- Everything else: current `main` stack (SWMM engine, D8+storage flood, Muskingum rivers, observed lake beds).

## 3. Sim results

- 73 frames @ ~20min; mass error 0.108; maxDepth 5.0 (display clip); flooded 7.6/30 km².
- All 7 lakes overtop, 267,724 m³ shoreline spill; 4 rivers modeled, none overtop; SWMM coupling flag off for this run (open item — under investigation, see §5).
- Lake centers at t=70: ~1.06m (assumed bed) and ~1.20m (observed bathy bed).
- Street points (Velachery edge, Pallikaranai north): 0.01–0.03m — essentially dry.

## 4. Similarities (what matches)

| # | Documented | Simulated | Verdict |
|---|---|---|---|
| 1 | Lakes full before the cloudburst; spill-driven flooding | first-flooded 00:00 at lake centers, peak 23:40, duration 24h | **Match** — timeline shape is right |
| 2 | Lake-area depths ~1.4–1.7m (Chembarambakkam colonies) | ~1.1–1.2m at our lake centers | **Same order**, ~20–30% low (different lakes, no release forcing) |
| 3 | Low-lying marsh/old-lake-bed areas worst hit (Pallikaranai sink, Velachery) | 7.6 km² flooded concentrated in low spots + lake margins | **Pattern match** |
| 4 | Saturated antecedent as amplifier | fill=100% was required for major spill (75% absorbs the same storm) | **Mechanism match** |

## 5. Mismatches and missing mechanisms (honest gaps)

1. **Street flooding understated:** cm in-sim vs meters documented in worst zones. Causes: (a) bbox excludes Mudichur/Tambaram where the worst depths were; (b) no reservoir-release forcing — the 29k-cusecs Adyar pulse has no analog in the sim, yet CAG pins it as the dominant Adyar-corridor driver; (c) uniform sheet + 0.05m threshold spreads shallow water instead of concentrating it.
2. **Rivers quiet:** 0 spill — consistent with no release inflows (real Adyar carried 29k cusecs + upstream tanks). Our reaches only get local drain shares.
3. **SWMM uncoupled this run** (`swmmCoupled: False`): needs a follow-up probe — possibly the 24h/variable path. Drain overflow here is Manning-guess, not computed.
4. **Single scenario, no sensitivity sweep** (fill 75/100, other bboxes) and no ground-truth scoring — this is comparison, not calibration.

## 6. What would close the gaps (in order)

1. Tambaram/Mudichur bbox rerun (covers the documented worst depths).
2. Reservoir-release forcing: Chembarambakkam-style timed inflow hydrograph into Adyar reaches (uses the river routing + tidal/outfall work already on `slice-2`).
3. Fix/investigate the SWMM coupling flag on 24h variable runs.
4. Street-concentration physics (Slice 3 2D surface) for meter-scale street depths.
5. Ground-truth depth labels → real calibration gate.
