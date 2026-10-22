# Skill Factory Agent

- **Canonical Path:** `SYSTEM/agents/skill_factory/`
- **Agent ID:** `skill_factory`
- **Category:** `SYSTEM_SUBAGENT`
- **Primary Class:** `SkillFactoryAgent`
- **Owner:** `system-core`

## Purpose
System agent responsible for authoring, auditing for security vulnerabilities, staging, and registering reusable skills with the central `SkillRegistry`.

## Capabilities
- `skill-authoring`
- `security-audit`
- `skill-staging`
- `version-registration`

## Allowed Tools
- `skill_registry`
- `static_auditor`
- `file_storage`
