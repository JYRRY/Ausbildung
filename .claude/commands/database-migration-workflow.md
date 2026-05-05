---
name: database-migration-workflow
description: Workflow command scaffold for database-migration-workflow in Ausbildung.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /database-migration-workflow

Use this workflow when working on **database-migration-workflow** in `Ausbildung`.

## Goal

Initializes or updates Alembic migrations to reflect changes in ORM models.

## Common Files

- `alembic/env.py`
- `alembic/versions/*.py`
- `alembic.ini`
- `alembic/script.py.mako`
- `alembic/README.md`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit alembic/env.py to ensure new models are imported and registered
- Create or update migration scripts in alembic/versions/
- Update alembic.ini or alembic/script.py.mako if migration config or templates change
- Document migration usage or changes in alembic/README.md

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.