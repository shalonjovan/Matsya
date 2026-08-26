# MATSYA — Project Context & Current Plan

## 1. Origin

The project came from **SH26085 — Urban Flood Nowcasting**.

The broader goal is to build a system that can understand and eventually predict urban flooding by combining rainfall, terrain, drainage, surface runoff, rivers/coastal boundaries, and other physical data.

The project was considered under several names, including Enlil, Manu, Noah, and finally **Matsya**.

> **MATSYA** is the current working name.

The name is inspired by Matsya and the idea of protecting/saving people from floods.

---

## 2. Core idea

MATSYA is **not just a drainage simulator**.

The key realization was:

> **The drainage network is only one component. The main problem is what happens to rainfall on the surface.**

The intended physical chain is:

```text
                         RAINFALL
                             ↓
                    ┌─────────────────┐
                    │     TERRAIN     │
                    │                 │
                    │ surface runoff  │
                    │      →→→→       │
                    │         →→→     │
                    │            ↓    │
                    │       LOW POINT  │
                    │          ↓      │
                    │        FLOOD     │
                    └────────┬────────┘
                             │
                        drain inlet
                             ↓
                    ┌─────────────────┐
                    │ DRAINAGE NETWORK│
                    └────────┬────────┘
                             ↓
                       RIVER / CANAL
                             ↓
                            SEA
```

The eventual goal is therefore an **urban hydrodynamic digital twin**, rather than simply a drain model.

---

## 3. What MATSYA should eventually do

The desired system should eventually be able to:

- ingest terrain/elevation data
- ingest drainage-network data
- ingest rainfall data
- model rainfall falling over terrain
- calculate surface runoff
- model water movement over the surface
- identify low-lying areas and accumulation
- model infiltration/ground absorption
- model drainage capacity
- model water entering drains
- model drainage-network flow
- detect overloaded drainage
- calculate water remaining on the surface
- potentially model rivers/canals
- potentially account for downstream/coastal boundary conditions
- produce flood-depth maps
- produce flood-extent maps
- estimate how long water remains
- eventually support flood nowcasting/forecasting
- eventually provide a custom MATSYA visualization interface

---

## 4. Why 1D alone is not enough

A 1D hydraulic model is naturally good for predefined flow paths:

```text
A ───── B ───── C ───── D
```

That makes it useful for pipes, drains, channels and rivers.

But surface runoff does not necessarily follow predefined paths:

```text
             ↓
        ↙    ↓    ↘
       ↙     ↓     ↘
      ↓      ↓      ↓
   ───────────────────
          terrain
       ↘ → → → ↙
          ↓↓↓
       low point
```

Therefore the main surface component needs at least a **2D spatial representation**.

---

## 5. Current proposed architecture

The current preferred architecture is:

> **2D surface hydrodynamics + drainage hydraulics + optional/localized 3D**

```text
                         MATSYA
                            │
             ┌──────────────┼──────────────┐
             │              │              │
             ▼              ▼              ▼
          2D SURFACE      DRAINAGE       3D
          HYDRODYNAMICS   NETWORK        HOTSPOTS
             │              │              │
             └──────────────┼──────────────┘
                            │
                            ▼
                     COUPLED MODEL
```

### 2D surface

This is the primary component.

A surface cell can conceptually contain:

- terrain elevation
- water depth
- water-surface elevation
- X velocity
- Y velocity
- rainfall
- infiltration
- surface roughness

A simplified mass-conservation relationship is:

\[
\frac{\partial h}{\partial t}
+
\nabla \cdot (h\mathbf{u})
=
R-I
\]

where:

- `h` = water depth
- `u` = depth-averaged velocity
- `R` = rainfall input
- `I` = infiltration

The exact governing equations and solver are still to be selected.

### Drainage

The drainage network can be represented as a hydraulic network.

A 1D model can still retain important vertical information because the drain can have a cross-sectional relationship:

\[
A(h)
\]

where cross-sectional area depends on water depth.

So 1D does **not** mean pretending the drain has no height. It means not resolving the complete 3D velocity field throughout every drain.

### 3D

3D is considered for locations where vertical flow genuinely matters:

- complicated drain inlets
- culverts
- junctions
- outfalls
- sharp contractions/expansions
- hydraulic structures
- strong vertical flow
- places where the 2D approximation needs validation

The current plan does **not** commit to full-city 3D CFD.

---

## 6. Why not make everything 3D?

3D has real advantages:

- vertical velocity
- pressure variation
- actual drain geometry
- bends
- junctions
- contractions/expansions
- inlet geometry
- turbulence
- hydraulic jumps
- complex structures
- complicated boundary conditions

A 3D model can represent:

\[
u(x,y,z),\quad v(x,y,z),\quad w(x,y,z)
\]

instead of only depth-averaged horizontal behaviour.

But city-scale 3D is extremely expensive.

For example:

```text
1000 × 1000 horizontal cells
=
1,000,000 cells
```

With 30 vertical layers:

```text
1,000 × 1,000 × 30
=
30,000,000 cells
```

and every cell requires multiple state variables and repeated numerical updates.

Therefore the current idea is:

> Use 2D for large-scale surface flooding, hydraulic-network modelling for drainage, and 3D only where high-fidelity local physics is needed.

---

# 7. Simulation engines investigated

## SWMM

**EPA Storm Water Management Model**

Useful for:

- urban drainage
- stormwater
- pipes
- channels
- storage
- pumps
- regulators
- rainfall/runoff

SWMM is a strong candidate for the **drainage-network baseline**, not the complete MATSYA surface engine.

Official page:

https://www.epa.gov/water-research/storm-water-management-model-swmm

Source:

https://github.com/USEPA/Stormwater-Management-Model

SWMM uses an `.inp` model file with sections such as:

```text
[TITLE]
[OPTIONS]
[JUNCTIONS]
[OUTFALLS]
[CONDUITS]
[XSECTIONS]
[SUBCATCHMENTS]
[RAINGAGES]
[TIMESERIES]
```

---

## TELEMAC

Important established hydrodynamic ecosystem.

Relevant components:

- TELEMAC-2D
- TELEMAC-3D

TELEMAC-2D is relevant to shallow-water/surface hydrodynamics.

TELEMAC-3D can represent vertical flow structure.

A major attraction is being able to investigate 2D and 3D within the same ecosystem.

---

## LISFLOOD-FP

Relevant to flood inundation and large-area surface flow.

Potentially strong for the MATSYA surface component.

---

## ANUGA

Open-source shallow-water simulation framework.

Relevant to:

- flooding
- coastal inundation
- tsunami/dam-break type flows
- terrain-driven surface water

Code-driven and useful for experimentation.

---

## Basilisk

Numerical fluid/free-surface framework.

Supports:

- 2D
- 3D
- adaptive mesh refinement
- sophisticated free-surface simulations

More of a numerical research framework than a ready-made Chennai urban-flood product.

---

## TRITON

Interesting for high-performance flood modelling.

Potentially useful if fast large-scale simulation becomes a major requirement.

---

## DualSPHysics

Particle-based hydrodynamics using Smoothed Particle Hydrodynamics.

Interesting for:

- free-surface flow
- complex 3D behaviour
- structures
- particle-based simulation

Potentially useful for high-fidelity local experiments.

---

## OpenFOAM

General-purpose CFD framework.

Can handle:

- 3D flow
- free-surface flow
- turbulence
- multiphase flow
- complex geometry
- structures

Very flexible, but not a ready-made urban flood simulator.

---

## HEC-RAS

Free hydraulic modelling software supporting 1D/2D hydraulic modelling and commonly used for river/flood modelling.

However, it is more GUI-oriented than the code-first tools currently being prioritized, and its source/licensing situation differs from genuinely open-source engines.

---

## Delft3D

Hydrodynamic ecosystem relevant to:

- rivers
- estuaries
- coastal systems
- 2D/3D hydrodynamics

---

## Iber

2D hydraulic/flood modelling software relevant to river and flood hydraulics.

---

# 8. Rust options

Rust is interesting for MATSYA, but:

> **Rust should not be a hard requirement if it compromises physics quality.**

A mature validated solver wrapped by Rust is preferable to a Rust solver with inadequate physics.

### Pravash

Rust implementation of 2D nonlinear shallow-water equations.

Potentially relevant to the **surface component**.

However, it is less mature as a complete flood-modelling ecosystem than established systems such as TELEMAC, LISFLOOD-FP or ANUGA.

It should be benchmarked before committing.

### Hydra

Rust project relevant to water infrastructure/urban drainage.

Potentially interesting for the drainage side.

It should be evaluated rather than assumed to be equivalent in maturity to SWMM.

---

# 9. Code-first requirement

The project explicitly wants a **code-based** workflow rather than a GUI-first workflow.

The intended structure is:

```text
                 MATSYA
                    │
        ┌───────────┴───────────┐
        │                       │
     Backend                   GIS
        │                       │
        └───────────┬───────────┘
                    ↓
             PHYSICS ENGINE
                    │
       ┌────────────┼────────────┐
       ↓            ↓            ↓
      2D           1D           3D
    surface      drainage      CFD
       │            │            │
       └────────────┼────────────┘
                    ↓
             simulation results
                    ↓
              MATSYA UI
```

The simulation engines should be programmable and automatable.

The GUI/dashboard will eventually be our own interface.

---

# 10. Immediate experiment

We do NOT want to build the entire MATSYA system immediately.

The next step is a small physical experiment:

```text
Small Chennai area
        ↓
DEM / terrain
        +
Drainage KML
        +
Synthetic rainfall
        ↓
Physics simulation
        ↓
Water depth / runoff / drainage
        ↓
Validation
```

The initial experiment should answer:

- How does water move over this terrain?
- Where does it accumulate?
- How much water enters the drain?
- How much can the drainage network carry?
- How much water remains on the surface?
- How long does water remain?
- What happens when the drainage network fills or overloads?

Start with a small area, not the entire ward.

---

# 11. Drainage KML

A drainage KML has been obtained for a Chennai area.

We need to inspect exactly what it contains.

Potential information includes:

- drain ID
- geometry
- coordinates
- length
- width
- depth
- invert/elevation
- material
- connectivity
- other attributes

We must not assume these fields exist.

---

# 12. KML is not directly accepted by SWMM

The intended pipeline is:

```text
Chennai drainage KML
        ↓
KML parser
        ↓
GeoPandas / Shapely
        ↓
geometry + attributes
        ↓
network reconstruction
        ↓
SWMM .inp
        ↓
SWMM engine
        ↓
simulation results
```

SWMM expects its own input model format, generally an `.inp` file.

---

# 13. KML → SWMM conversion

This is not merely a file-format conversion.

We need to reconstruct hydraulic topology.

For example:

```text
Drain A ──────────────┐
                      │
Drain B ──────────────┤
                      ↓
Drain C ──────────────┘
```

may become:

```text
        J1
       /        /        C1      C2
    /           J2────────J3
       C3
```

and the SWMM model could contain:

```text
[JUNCTIONS]
J1 ...
J2 ...
J3 ...

[CONDUITS]
C1 J1 J2 ...
C2 J1 J3 ...
C3 J2 J3 ...
```

Exact values must come from actual data or validated external sources.

---

# 14. Coordinate-system issue

KML generally stores geographic coordinates:

```text
longitude, latitude, altitude
```

We should not calculate physical distances directly from latitude/longitude.

Instead:

```text
WGS84 latitude/longitude
        ↓
appropriate projected CRS for Chennai
        ↓
coordinates in metres
        ↓
length / geometry calculations
```

This is important for correct hydraulic distances.

---

# 15. Missing hydraulic information

Important rule:

> **Do not invent missing physical parameters.**

If the KML does not contain:

- pipe/drain diameter
- width
- depth
- invert elevation
- Manning roughness
- cross-sectional shape
- slope

then we need to find appropriate external sources or explicitly document assumptions.

Possible sources may include:

- government drainage datasets
- engineering drawings
- Greater Chennai Corporation / municipal information
- survey data
- DEM/elevation datasets
- field measurements
- other public infrastructure datasets

Each missing parameter needs an identified source or a clearly documented assumption.

---

# 16. Rainfall experiment

Once the model is constructed, use controlled synthetic rainfall for the first test.

For example:

```text
50 mm/hr
60 minutes
```

This is only an example test scenario, not an assumed Chennai storm.

The simulation should calculate:

- rainfall volume
- runoff
- infiltration
- drainage flow
- surface storage
- water remaining

Basic mass balance:

\[
V_{rain}
=
V_{runoff}
+
V_{infiltration}
+
V_{drainage}
+
V_{storage}
\]

The model should be checked against this balance.

---

# 17. Initial engine choice

The immediate baseline is **SWMM for drainage**.

Reason:

- mature
- designed for urban stormwater/drainage
- code-based engine available
- established hydraulic baseline
- useful for testing KML → hydraulic-network conversion

The main surface engine is still undecided.

Surface candidates:

1. TELEMAC-2D
2. LISFLOOD-FP
3. ANUGA
4. Basilisk
5. TRITON
6. Pravash as an experimental Rust candidate

3D candidates:

1. TELEMAC-3D
2. OpenFOAM
3. Basilisk
4. DualSPHysics
5. Delft3D

---

# 18. How to choose the final engine

Do not choose based on language alone.

Give candidate engines the same toy problem:

```text
Area:
100 m × 100 m

Terrain:
gentle slope

Drain:
known geometry

Rainfall:
controlled synthetic storm

Boundary:
known downstream condition
```

Measure:

- mass conservation
- water depth
- flow direction
- flood arrival time
- drainage behaviour
- wetting/drying behaviour
- runtime
- memory usage
- GPU support
- ease of GIS integration
- licensing
- extensibility
- numerical stability
- documentation
- ease of validation

Then select based on evidence.

---

# 19. 2D vs 3D

A major discussion was whether 2D is too inaccurate because water is fundamentally 3D.

The conclusion was:

2D shallow-water models do not claim that water is literally two-dimensional.

They represent the horizontal distribution and depth of a water layer while approximating the internal vertical structure using depth-averaged quantities.

The model still knows:

```text
ground elevation
+
water depth
=
water-surface elevation
```

A 3D model additionally resolves vertical flow structure.

The current position is:

> **Test the difference rather than arguing about it theoretically.**

A small drain/structure can eventually be simulated in both lower-dimensional and 3D models and compared for:

- water depth
- velocity
- discharge
- arrival time
- pressure/flow behaviour

This will show whether lost 3D information actually matters for MATSYA.

---

# 20. Why the hybrid architecture is preferred

### City surface

2D because we need large-area coverage and surface water can move in arbitrary directions.

### Drainage

Hydraulic-network modelling because drains naturally form connected paths and cross-sectional geometry can be represented through hydraulic relationships.

### Localized 3D

3D where vertical flow structure genuinely matters.

This is potentially far more efficient than full-city 3D CFD.

---

# 21. Immediate next action

**Inspect the actual drainage KML.**

Before writing a generic converter, determine:

1. What layers it contains
2. What geometries it contains
3. What attributes it contains
4. Whether drains are lines or polygons
5. Whether elevations exist
6. Whether depth/width/cross-section data exists
7. Whether connectivity can be reconstructed
8. What data is missing
9. What coordinate reference system it uses
10. What can be converted directly into a hydraulic model

Then build the smallest possible working experiment.

---

# 22. Project principles

### Physics first

Do not build an attractive interface around incorrect physics.

### Data first

Do not invent infrastructure parameters.

### Validate everything

Use mass balance, analytical calculations, known hydraulic behaviour and eventually real observations.

### Code first

Prefer programmable, automatable simulation engines.

### Modular architecture

Keep GIS ingestion, preprocessing, surface physics, drainage physics, 3D hotspot modelling, orchestration and visualization separable.

### Benchmark before committing

Test multiple engines on the same physical scenario.

### Start small

Use a small Chennai test area first, then scale.

---

# 23. Current one-line definition

> **MATSYA is intended to become a code-first urban flood hydrodynamic digital twin that simulates rainfall-driven surface runoff and flooding over real terrain, couples that surface water with urban drainage infrastructure, and can use localized high-fidelity 3D modelling where necessary.**

---

# 24. Roadmap

```text
PHASE 0
Inspect KML
    ↓
Understand data
    ↓
Identify missing parameters

PHASE 1
KML → hydraulic network
    ↓
SWMM baseline
    ↓
Synthetic rainfall
    ↓
Validate drainage behaviour

PHASE 2
Select 2D surface engine
    ↓
DEM + rainfall
    ↓
Surface runoff
    ↓
Flood depth

PHASE 3
Couple surface + drainage
    ↓
Water enters drains
    ↕
Drain overflow/backflow
    ↓
Flood result

PHASE 4
Add rivers/coastal boundaries
    ↓
More realistic urban hydrology

PHASE 5
3D hotspot experiments
    ↓
Compare lower-dimensional and 3D models
    ↓
Determine where 3D is actually necessary

PHASE 6
Build MATSYA orchestration/API
    ↓
Automated simulations
    ↓
GIS integration
    ↓
Visualization/dashboard

PHASE 7
Validation + nowcasting
    ↓
Real rainfall/weather data
    ↓
Real observations
    ↓
Operational flood predictions
```

---

# 25. Decision status

## Decided

- Working name: **MATSYA**
- Code-first approach
- Surface runoff is the primary problem
- Drainage is a subsystem
- 1D alone is not sufficient
- Do not automatically make the entire system 3D
- Prefer a hybrid architecture
- Rust is not a hard requirement
- Start with a small physical experiment
- Inspect the actual KML before writing the converter
- Validate simulations rather than trusting visual output

## Not decided yet

- final 2D engine
- final drainage engine
- whether/how 3D will be integrated
- coupling method
- exact Rust role
- DEM/elevation source
- infiltration model
- roughness/Manning values
- rainfall source
- river/coastal boundary data
- final MATSYA software architecture

---

# 26. Immediate task

**Upload/inspect the drainage KML.**

Then build:

```text
KML
 ↓
parsed GIS data
 ↓
network topology
 ↓
hydraulic parameters
 ↓
SWMM .inp
 ↓
small synthetic rainfall test
 ↓
results
 ↓
mass-balance validation
```

After that, evaluate the 2D surface engines.

The guiding principle is:

> **We are not trying to build all of MATSYA at once. We are building a small, physically defensible simulation and progressively expanding it into the full urban flood digital twin.**
