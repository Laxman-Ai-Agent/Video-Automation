"""SYSTEM package root. Registers the `backend` import alias (core/backend_alias.py) before any SYSTEM module imports through it."""
from SYSTEM.core.backend_alias import install

install()
