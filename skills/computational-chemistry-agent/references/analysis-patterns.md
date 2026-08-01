# Computational Chemistry Analysis Patterns

Use these scaffolds to prompt large models (or yourself) when analyzing computational chemistry problems. Mix and match as needed.

## 1. Descriptor Exploration
- Identify the physical observable being predicted (PLQY, rate constant, selectivity, etc.).
- Enumerate candidate descriptors along three axes:
  1. **Electronic** (orbital energies, excitation energies, charge localization).
  2. **Geometric** (torsions, planarity, intermolecular distances).
  3. **Environmental** (dielectric, embedding field, defect states).
- For each descriptor, specify: definition, how to compute (method, level of theory), why it might correlate with the observable, and practical measurement strategy.

### Prompt Template
```
Act as a senior computational chemist. Given [system + target property], recommend descriptor families that could separate performant and non-performant samples. For each descriptor, provide the controlling physics and the minimal calculation needed to obtain it.
```

## 2. Mechanism Hypothesis & Validation Loop
1. Translate symbolic or empirical formulas into qualitative relationships.
2. Map each term to real-space processes: localization, charge transfer, conical intersections, etc.
3. Propose mechanistic stories consistent with both formula structure and known photophysics (Kasha, energy-gap law, CT quenching).
4. Outline validation paths: excited-state scans, constrained optimizations, non-adiabatic couplings.

### Prompt Template
```
Given the expression [formula] that separates two regimes, infer the physical process behind each term and propose theoretical/experimental checks that could falsify it.
```

## 3. Cross-Model Hypothesis Synthesis
- Collect hypotheses from multiple sources.
- Normalize them into canonical mechanism buckets (e.g., **charge transfer loss**, **vibrational dissipation**, **exciton trapping**).
- Score each hypothesis by level of agreement and evidence.
- Produce a distilled mechanism set plus traceability matrix.

### Prompt Template
```
Here are N mechanism summaries. Group them by physical principle, merge duplicates, and output 2-3 consensus hypotheses with supporting sources and reasoning chains.
```

## 4. Theoretical Verification Workflow Design
- Inventory candidate levels of theory (DFT, TDDFT, GW/BSE, QM/MM).
- Trade off fidelity vs. cost: low-cost screening, high-accuracy refinement.
- Map each hypothesis to calculable observables (excitation localization, nonradiative couplings, reorganization energies).
- Output a tiered workflow (screening → refinement → validation) with detailed settings (functional/basis, solvation, embedding, sampling requirements).

### Prompt Template
```
Design a computational workflow to test hypotheses H1...Hn. Specify methods, system size, boundary conditions, and acceptance criteria.
```

## 5. Data-Driven Mechanism Refinement
When provided with tabulated excited-state data (hole/electron contributions, oscillator strengths, etc.):
- Separate data into performance classes.
- For each class, aggregate descriptors (means, ranges) and visualize distributions.
- Identify discriminating features and link them back to the mechanism hypotheses.
- Translate findings into design rules.

### Prompt Template
```
Given the table [data], compare the excited-state characteristics between performant and failing samples, update prior hypotheses, and express actionable design rules.
```

## 6. Descriptor Derivation from First Principles
- Start from definitions (transition density, hole/electron distribution, charge-transfer number).
- Write expressions (integrals over TD density, Mulliken charges, participation ratios).
- Show how simplifications (localized basis, fragment partitions) lead to computable descriptors.
- Connect descriptor thresholds to physical behavior (e.g., localization on fragment A implies radiative decay).

## 7. Constraints for Descriptor Design
- Calculations must be strictly performed on free monomer molecules prior to condensation. Do not reference structural features that emerge only after polymerization. For example, concepts like 'amine fragments,' 'aldehyde fragments,' or 'imine linkages' do not exist within an isolated monomer.
- Use only global (whole-molecule) electronic structure descriptors. Avoid metrics that require specifying particular atoms or local active sites, as structurally diverse monomers lack a universal standard for defining these local sites.
- Each descriptor must be a recognized physical quantity with a well-established definition and standard computational workflow in the literature. Do not invent ad-hoc combinations, coin new terms, or redefine established physical concepts.
- All descriptors must be directly obtainable from ground-state DFT single-point calculations (or TDDFT vertical excitations at the ground-state geometry). Do not propose metrics requiring potential energy surface scans, molecular dynamics, or multi-reference/multi-configurational calculations.
- Descriptor definitions must be unambiguous and deterministic, independent of arbitrarily chosen reference systems or reaction schemes. Strictly exclude metrics with contested theoretical definitions or inconsistent software implementations in the literature.

### Prompt Template
```
Derive a descriptor that quantifies [behavior]. Begin with fundamental expressions, apply fragment partitioning, and produce a final formula that can be computed from TDDFT outputs.
```
