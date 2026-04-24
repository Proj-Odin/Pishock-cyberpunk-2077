import sys
import types

import pytest


class _BlockedPiShockModule(types.ModuleType):
    def __getattr__(self, name: str):
        raise AssertionError(f"unexpected real pishock access in tests: {name}")


@pytest.fixture(autouse=True)
def _block_real_pishock_import(monkeypatch):
    if "pishock" not in sys.modules:
        monkeypatch.setitem(sys.modules, "pishock", _BlockedPiShockModule("pishock"))
