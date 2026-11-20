# reference/ — not part of the product

`reference/gang/` is an untouched copy of the GANG repository
(JYRRY/GANG, commit `ed5e14b`), kept on this branch as a source of features
and UI ideas. Nothing here is imported, built, tested or deployed:

- Features are ported into `jyry/` one by one, adapted to the server
  architecture and covered by tests; the original stays here for comparison.
- Desktop UI screens are reference material for the Framer front end.
- When GANG updates, this folder is refreshed and the diff shows what changed.

This folder stays on `claude/gang-integration` and is excluded when the
branch is merged into `main`.
