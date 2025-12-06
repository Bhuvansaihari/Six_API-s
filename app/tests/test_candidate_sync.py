from datetime import date
from typing import Any, Dict, List

import pytest

from app.db.sql_server import CandidateRecord
from app.api.candidate_sync.logic import (
    CandidateNotFoundError,
    MultipleCandidatesFoundError,
    sync_candidate_by_email,
)


class DummySQLRepo:
    def __init__(self, records: List[CandidateRecord]) -> None:
        self._records = records

    def fetch_candidates_by_email(self, email: str) -> List[CandidateRecord]:
        return self._records


class DummySupabaseRepo:
    def __init__(self) -> None:
        self.upserts: List[Dict[str, Any]] = []

    def upsert_candidate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.upserts.append(payload)
        return payload


@pytest.fixture(autouse=True)
def patch_to_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    async def immediate(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("app.api.candidate_sync.logic.asyncio.to_thread", immediate)


@pytest.mark.asyncio
async def test_sync_candidate_success() -> None:
    record = CandidateRecord(
        candidate_id=1,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        password="secret",
        birth_date=date(1990, 1, 1),
        ssn="123-45-6789",
        over_18_age=True,
        mobile="1234567890",
        home=None,
        work=None,
        work_ext=None,
        relocation=True,
    )
    sql_repo = DummySQLRepo([record])
    supabase_repo = DummySupabaseRepo()

    result = await sync_candidate_by_email("john@example.com", sql_repo, supabase_repo)

    assert result.email == "john@example.com"
    assert len(supabase_repo.upserts) == 1
    inserted = supabase_repo.upserts[0]
    assert inserted["cand_id"] == 1  # Should match CandidateID from SQL Server
    assert inserted["email"] == "john@example.com"
    assert inserted["relocation"] is True
    assert inserted["first_name"] == "John"


@pytest.mark.asyncio
async def test_sync_candidate_not_found() -> None:
    sql_repo = DummySQLRepo([])
    supabase_repo = DummySupabaseRepo()

    with pytest.raises(CandidateNotFoundError):
        await sync_candidate_by_email("missing@example.com", sql_repo, supabase_repo)


@pytest.mark.asyncio
async def test_sync_candidate_multiple_found() -> None:
    record = CandidateRecord(
        candidate_id=1,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        password=None,
        birth_date=None,
        ssn=None,
        over_18_age=None,
        mobile=None,
        home=None,
        work=None,
        work_ext=None,
        relocation=None,
    )
    sql_repo = DummySQLRepo([record, record])
    supabase_repo = DummySupabaseRepo()

    with pytest.raises(MultipleCandidatesFoundError):
        await sync_candidate_by_email("john@example.com", sql_repo, supabase_repo)

