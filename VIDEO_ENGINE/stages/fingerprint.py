"""Cache fingerprints = input hash (pipeline.digest) + the config values that change the stage's output + the stage-logic version.
Off by default (A2V_FINGERPRINTS=1 turns it on): with the flag off the fingerprint is returned unchanged, so existing caches stay valid."""
import hashlib
import json

from . import config


def versioned(name: str, fp: str | None) -> str | None:
    if fp is None or not config.improve("fingerprints"):
        return fp
    cfg = {k: getattr(config, k) for k in config.STAGE_CONFIG_KEYS.get(name, ())}
    flags = [f for f in config.FLAG_NAMES if config.improve(f)]          # turning a feature on or off must not reuse the other mode's output
    return hashlib.sha1(f"{fp}|v{config.STAGE_VERSIONS.get(name, 0)}|{json.dumps(cfg, sort_keys=True)}|{flags}".encode()).hexdigest()
