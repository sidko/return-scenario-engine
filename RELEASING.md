# Releasing

After `main` CI passes, push `v<version>` over SSH. The tag must match both
`package.json` and `python/pyproject.toml`. The workflow tests both
implementations, compares npm package bytes before upload, and normalizes PyPI
archives before comparing their contents so archive timestamps do not make a
retry unsafe. Matching existing files are skipped; different content fails.
It creates the GitHub Release after both registries succeed.
