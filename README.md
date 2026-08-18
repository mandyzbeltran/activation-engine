# Astro Layer 1

Deterministic Western astrology computation service that converts birth data
and a UTC window into the versioned `activations[]` JSON contract.

This directory is the boundary of the public Layer 1 repository selected under
licensing option B. It must contain only Layer 1 code, machine-readable mapping
configuration, tests, and operational documentation. Do not add the private KB,
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

## License

AGPL-3.0-only. Any deployed network service based on this code must offer its
corresponding source as required by the license. Obtain legal advice for final
distribution compliance.
