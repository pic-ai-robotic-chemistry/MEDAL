# MiMEDAL

MiMEDAL is the project repository accompanying the paper **"Mechanism-Evolving Discovery from Minimal Experiments"**.

It is built around the open-source [OpenClaw](https://github.com/openclaw/openclaw) agent framework and extends it with a domain-specific scientific skill library for autonomous chemistry research workflows.

## What this repository contains

- `skills/` — the MiMEDAL scientific skill library used to orchestrate computational chemistry and autonomous workflow execution on top of OpenClaw.
- `results/` — experimental or computational result artifacts associated with the project.

## Conceptual overview

In the paper, MiMEDAL is described as a specialized agentic framework layered on top of OpenClaw. OpenClaw provides the general-purpose cognitive substrate (task routing, LLM access, memory, and agent execution), while MiMEDAL adds:

- chemistry-oriented skills,
- domain-specific orchestration logic,
- interfaces to external computation services,
- and integration points for automated experimentation.

This repository primarily exposes the **scientific skills layer** and associated project artifacts.

## Installation

MiMEDAL is distributed here as a collection of OpenClaw-compatible skills.

### Install into an existing OpenClaw setup

1. Install and configure OpenClaw first.
2. Copy the skill folders from this repository into your local OpenClaw `skills/` directory.

For example:

```bash
cp -R skills/* /path/to/your/openclaw/skills/
```

A common OpenClaw user-level location is a workspace such as:

```bash
cp -R skills/* ~/.openclaw/workspace/skills/
```

If your OpenClaw setup uses a different active custom-skills directory, copy them there instead.

## Private infrastructure notice

Some workflows in MiMEDAL depend on external compute or file-upload services (for example, Gaussian, DFTB+, or structure-optimization backends).

The original private deployment endpoints, upload headers, and tokens have been removed from this public code release. In the relevant config/example files, these values are now replaced with placeholders such as:

- `https://your-own-hpc-api.example.com`
- `https://your-own-upload-api.example.com/api/file/upload`
- `https://your-own-mace-service.example.com`
- `PLEASE_SET_YOUR_OWN_SERVER_API_TOKEN`
- `PLEASE_SET_YOUR_OWN_CONTAINER_IMAGE`

To use these workflows, you must connect the skills to **your own server APIs and credentials**.

## Usage notes

- Read each skill's `SKILL.md` before use.
- Some skills assume access to external chemistry software, remote schedulers, or local analysis tools.
- Public placeholders are intentionally non-functional until replaced with your own deployment-specific settings.

## Reproducibility and scope

This repository is intended to document the MiMEDAL project structure and provide the reusable skill layer used in the work. Exact end-to-end execution may require:

- a configured OpenClaw runtime,
- external compute services,
- chemistry software dependencies,
- and, in some cases, local laboratory or institutional infrastructure not bundled here.

## Citation

If you use this repository in academic work, please cite the associated paper:

**Mechanism-Evolving Discovery from Minimal Experiments**

## License

MIT License
