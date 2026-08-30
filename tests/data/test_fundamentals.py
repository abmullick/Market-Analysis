import pytest

from backend.services.data.fundamentals import normalize_fundamentals


def test_normalize_fundamentals_not_implemented():
    with pytest.raises(NotImplementedError):
        normalize_fundamentals({})
