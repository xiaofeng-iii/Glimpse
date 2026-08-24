from datetime import date

import pytest
from fastapi import HTTPException

from api.memory_filters import normalize_memory_date_range


def test_normalizes_inclusive_dates_to_exclusive_storage_bounds():
    bounds = normalize_memory_date_range(date(2026, 8, 1), date(2026, 8, 24))

    assert bounds.created_after == "2026-08-01 00:00:00"
    assert bounds.created_before == "2026-08-25 00:00:00"


def test_rejects_a_reversed_date_range():
    with pytest.raises(HTTPException) as error:
        normalize_memory_date_range(date(2026, 8, 24), date(2026, 8, 1))

    assert error.value.status_code == 422
