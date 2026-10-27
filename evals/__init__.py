"""Behavioural evals for the dev skills (XAS-047).

Each run builds a throwaway sandbox — a store and a consumer repo, both with
local bare remotes — runs one prompt headless against a plugin exported from a
git ref, and grades the end state with plain assertions. See CONTRIBUTING.md.
"""
