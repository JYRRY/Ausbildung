---
name: add-new-database-model
description: Workflow command scaffold for add-new-database-model in Ausbildung.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /add-new-database-model

Use this workflow when working on **add-new-database-model** in `Ausbildung`.

## Goal

Defines new ORM models and related constants/enums for new database entities.

## Common Files

- `jyry/db/models.py`
- `jyry/db/enums.py`
- `jyry/constants.py`
- `jyry/db/base.py`
- `jyry/db/__init__.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit or create model classes in jyry/db/models.py
- Update or add enums in jyry/db/enums.py if needed
- Add or update reference constants in jyry/constants.py if needed
- Update jyry/db/base.py or mixins if new conventions or mixins are required
- Update jyry/db/__init__.py to expose new models if necessary

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.