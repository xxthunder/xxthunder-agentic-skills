"""Sphinx configuration of the ADR fixture: MyST for the Markdown, sphinx-needs for the needs."""

project = "needs-repo"
extensions = ["myst_parser", "sphinx_needs"]
needs_from_toml = "ubproject.toml"
exclude_patterns = ["_build"]
