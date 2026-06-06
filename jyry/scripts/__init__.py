"""Operational CLI helpers (manual, server-side).

These are debug / launch-prep tools run by hand on the server, e.g.::

    python -m jyry.scripts.set_plan --email you@example.com --plan plus
    python -m jyry.scripts.clear_applications --email you@example.com

They are intentionally kept out of the request/response paths.
"""
