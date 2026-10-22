# Shared Cross-Domain Skills

## Overview
Skills in the `shared` domain encompass cross-cutting capabilities applicable across multiple stages of video generation and system orchestration (e.g. bilingual text handling, metric reporting, hash verification, error diagnostics).

## Associated Agents
- All agents in `SYSTEM/agents/` may leverage shared skills.

## Criteria for Shared Classification
1. The skill must be reusable by 2 or more distinct pipeline agents or system subagents.
2. Must have deterministic inputs and outputs.
3. Must adhere to the central `SkillRecord` schema defined in `SYSTEM/registries/skill_registry.py`.

## Contribution Guidelines
1. Author skill candidate with domain set to `"shared"` in frontmatter.
2. Stage and audit with `SkillFactoryAgent`.
3. Promote approved skills into `SYSTEM/skills/shared/<skill_name>/SKILL.md`.
