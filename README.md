# Astro Layer 1

Deterministic Western astrology computation service that converts birth data
and a UTC window into the versioned `activations[]` JSON contract.

This directory is the boundary of the public Layer 1 repository selected under
licensing option B. It must contain only Layer 1 code, machine-readable mapping
public schema/configuration, synthetic tests, and repository operations files. Do not add the private KB,
prompts, Layer 2 service, mobile App code, or user data. Private components must
communicate with this service over HTTP and must not import or link its code.

## Status

The MVP computation pipeline includes natal charts, transits, secondary
progressions, solar and lunar returns, annual profections, life-area
aggregation, polarity, time bucketing, stable hashing, deterministic JSON
emission, and precision degradation.

The current algorithm contract is `layer1@2026.08.17.1`. Runtime projection
uses coarse public fallbacks only. Detailed life-area weights, exact KB polarity
metadata, KB content, and generated Track A artifacts remain private and are not
packaged with this service.

## Development

Python 3.11 or newer is required.

```bash
python -m unittest discover -s layer1/tests -v
```

For the full suite:

```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

## Public privacy gate

This repository uses a fail-closed allowlist and scans the complete history of
every ref before it can be pushed. Enable the versioned local hooks once after
cloning:

```bash
git config core.hooksPath .githooks
python scripts/privacy_gate.py --working-tree
python scripts/privacy_gate.py --all-history
```

The pre-commit hook scans the index, the pre-push hook scans every reachable
commit, and GitHub Actions repeats the full-history check. Files outside the
approved Layer 1 boundary, literal birth data outside the single synthetic
reference, local machine paths, credentials, symlinks, and submodules fail the
gate. Hooks can be bypassed manually, so `--no-verify` must not be used for this
public repository.

## Local HTTP service

The browser/mobile transport accepts local civil birth data and converts it to
UTC inside Layer 1. For local development, bind only to loopback:

```bash
python -m pip install -e '.[test]'
python -m uvicorn layer1.http_api:create_app --factory --host 127.0.0.1 --port 8001
```

The service exposes `POST /v1/activations` and `POST /v1/natal-summary`.
It does not persist or log request bodies. Configure exact development origins
with `LAYER1_CORS_ORIGINS`; the defaults cover Expo web on port 8083.

## License

AGPL-3.0-only. Any deployed network service based on this code must offer its
corresponding source as required by the license. Obtain legal advice for final
distribution compliance.
