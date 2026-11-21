"""config_default.json declares only settings that config_schema.json knows."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _undeclared_keys(config, schema, path=''):
    """Keys of config (not _comment* or $schema) missing from schema's properties."""
    properties = schema.get('properties', {})
    missing = []
    for key, value in config.items():
        if key.startswith('_') or key == '$schema':
            continue
        if key not in properties:
            missing.append(f'{path}.{key}')
        elif isinstance(value, dict):
            missing += _undeclared_keys(value, properties[key], f'{path}.{key}')
    return missing


def test_every_default_setting_is_in_the_schema():
    config = json.loads((ROOT / 'config_default.json').read_text())
    schema = json.loads((ROOT / 'config_schema.json').read_text())
    assert _undeclared_keys(config, schema) == []
