import pytest


@pytest.fixture
def core():
    from starling import _core
    return _core
