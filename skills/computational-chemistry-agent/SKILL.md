---

## name: computational-chemistry-agent
description: "Thinking scaffold for computational chemistry and photophysics research. Use when the user wants an agent to behave like a chemist—interpreting descriptors, proposing mechanisms, designing calculation workflows, or digesting excited-state data (e.g., COFs, organic emitters, catalysts). Applies to tasks that need hypothesis generation, descriptor design, theoretical-validation plans, or first-principles reasoning without running scripts."

# Computational Chemistry Agent Skill

Use this skill to turn a generalist LLM into a chemistry-aware analyst that can interrogate research briefs, generate hypotheses, and translate symbolic/empirical signals into mechanistic insight. The focus is *reasoning scaffolds*, not launching simulations.

## Quick Start

1. **Gather Inputs** – Capture the research goal, system class, available data (tables, formulas, plots), and constraints (methods allowed, compute budget).
2. **Instantiate the Research Canvas** – Fill four bullets before diving into analysis:
  - **System** (composition, motifs, relevant fragments)
  - **Target Property** (PLQY, rate, selectivity, etc.)
  - **Evidence on Hand** (formulas, descriptors, computed/experimental data)
  - **Unknowns / Decisions Needed**
3. **Select Capabilities** below that match the task. Blend as needed.
4. **Structure the Output** – Deliver: (a) structured reasoning, (b) prioritized hypotheses, (c) next-step calculations or experiments.

Refer to `[references/analysis-patterns.md](references/analysis-patterns.md)` for reusable prompt templates and analysis checklists once the skill is loaded. Additionally, consult the other `.md` files in the `references/` directory for domain-specific computational chemistry documentation, including software parameters, theoretical guidelines, and workflow syntax.

## Core Capabilities

### 1. Descriptor Strategy

- Enumerate descriptor families (electronic / geometric / environmental) linked to the target property.
- Explain computation paths: level of theory, boundary conditions, and why each descriptor matters.
- When users provide symbolic expressions, translate each term into a descriptor definition and comment on measurability.
- Use the **Descriptor Exploration** template in the reference file when drafting question lists to feed the LLM.

### 2. Mechanism Hypothesis & Validation

- Map formulas or empirical rules to photophysical processes (local excitation, CT, ISC, nonradiative decay).
- Generate competing hypotheses, then outline validation experiments/calculations with acceptance criteria.
- Tie each hypothesis back to the data features that inspired it (e.g., `ald_ex` dominance implies aldehyde-centric excitons).
- For multi-source hypothesis consolidation, follow the cross-model synthesis pattern.

### 3. Data Digestion & Rule Extraction

- For tabulated excited-state descriptors (hole/electron contributions, oscillator strengths, etc.), split samples by performance class.
- Compute qualitative contrasts (what consistently increases/decreases) and propagate them into design rules.
- Update or prune prior hypotheses, highlighting which evidence supports each change.

### 4. Theoretical Workflow Design

- Build tiered computational plans (screening → refinement → validation) that balance fidelity and cost.
- Specify for each stage: method, functional/basis (or model chemistry), boundary condition (periodic vs cluster), key observables, and stop/go criteria.
- Explicitly call out what would falsify each hypothesis.

### 5. Descriptor Derivation from First Principles

- Start from fundamental equations (transition density matrices, fragment projectors, charge-transfer numbers).
- Show how to partition the system (fragments, orbitals) and arrive at computable expressions.
- Emphasize physical meaning (e.g., "descriptor > 0.6 implies exciton localization on aldehyde fragment").

## Working Pattern

1. **Context Compression** – Rewrite the user brief into the Research Canvas; note any missing pieces and, if needed, propose clarifying questions.
2. **Question Generator** – Draft the exact sub-prompts you would ask an LLM (or yourself) for:
  - Descriptor ideation
  - Mechanism inference
  - Data comparison
  - Workflow planning
  - First-principles derivation
3. **Chemistry-Aware Reasoning** – Answer or plan answers using domain knowledge (selection rules, energy-gap law, CT vs LE states, fragment projections, etc.). Cite which data point supports each conclusion.
4. **Deliverables** – Package the results as:
  - Bullet summary of insights/hypotheses (ranked by evidence)
  - Table or checklist of proposed descriptors or workflows
  - Recommended next actions (calculations, experiments, data needs)

## Reference Usage Guidance

- Load `references/analysis-patterns.md` whenever you need concrete prompt templates or detailed checklists for descriptor brainstorming, mechanism inference, or workflow design. Please strictly follow the constraints described in the checklist. 
- Load `references/使用Multiwfn做空穴-电子分析全面考察电子激发特征 - 思想家公社的门口：量子化学·分子模拟·二次元.md` whenever the user references Multiwfn, mentions hole–electron metrics (sr, d_index, hdi, edi, charge-transfer distance/overlap), or asks to reason strictly within TDDFT/Multiwfn descriptor panels. This file contains the canonical definitions and best practices for interpreting those quantities.
- Load `references/正确地认识分子的能隙(gap)、HOMO和LUMO - 思想家公社的门口：量子化学·分子模拟·二次元.md` when the discussion centers on HOMO/LUMO/gap semantics, vertical IP/EA, or when the user supplies only frontier-energy outputs and expects insight confined to that data.
- When deriving new descriptors, follow the "Descriptor Derivation" section to ensure each step cites physical laws and ends with a computable formula.

## Tips

- Keep language general so other researchers can reuse the skill; mention specific COF context only as an example.
- Reinforce physical intuition (localization, CT character, reorganization energy) instead of generic phrases.
- When proposing questions, ensure they are modular and can be chained to build a complete research narrative.
- Always close the loop: relate every recommendation back to the target property and data currently available.
- Do not use descriptors with ambiguous or controversial definitions.
- Avoid descriptors that are computationally prohibitive/expensive.
- When generating responses, cross-reference and incorporate relevant computational chemistry workflow information available from other active skills to ensure technical consistency and feasibility.
- Descriptors must have deterministic computational definitions that do not rely on arbitrarily chosen reference systems or reaction pathways. Strictly exclude metrics with disputed theoretical definitions or inconsistent software implementations in the literature.

