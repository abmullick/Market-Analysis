import pytest

from backend.config.settings import Settings
from backend.services.data.mfapi import MfapiClient
from backend.services.data.amfi import AmfiClient


@pytest.fixture
def mfapi_client():
    return MfapiClient(settings=Settings())


@pytest.fixture
def amfi_client():
    return AmfiClient(settings=Settings())


def test_mfapi_client_initialization(mfapi_client):
    assert mfapi_client.base_url == "https://api.mfapi.in"


def test_amfi_client_initialization(amfi_client):
    assert amfi_client.nav_url == "https://www.amfiindia.com/spages/NAVAll.txt"
