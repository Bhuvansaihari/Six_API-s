from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.db.sql_server import SQLServerRepository, CandidateRecord
from app.supabase.client import SupabaseRepository, serialize_candidate
from app.api.candidate_sync.schemas import CandidateContact

logger = logging.getLogger(__name__)


class CandidateNotFoundError(Exception):
    pass


class MultipleCandidatesFoundError(Exception):
    pass


async def sync_candidate_by_email(
    email: str,
    sql_repo: SQLServerRepository,
    supabase_repo: SupabaseRepository,
) -> CandidateContact:
    """Lookup candidate in SQL Server and persist to Supabase."""

    records = await asyncio.to_thread(sql_repo.fetch_candidates_by_email, email)
    if not records:
        logger.info("No candidate record found for email", extra={"email": email})
        raise CandidateNotFoundError(f"No candidate found for {email}")
    if len(records) > 1:
        logger.warning(
            "Multiple candidate records found for email",
            extra={"email": email, "count": len(records)},
        )
        raise MultipleCandidatesFoundError(f"Multiple candidates found for {email}")

    candidate = records[0]
    payload = serialize_candidate(
        candidate_id=candidate.candidate_id,
        first_name=candidate.first_name,
        last_name=candidate.last_name,
        email=email,
        password=candidate.password,
        birth_date=candidate.birth_date,
        ssn=candidate.ssn,
        over_18_age=candidate.over_18_age,
        mobile=candidate.mobile,
        home=candidate.home,
        work=candidate.work,
        work_ext=candidate.work_ext,
        relocation=candidate.relocation,
    )

    await asyncio.to_thread(supabase_repo.upsert_candidate, payload)

    return CandidateContact(
        candidate_id=candidate.candidate_id,
        first_name=candidate.first_name,
        last_name=candidate.last_name,
        email=email,
        password=candidate.password,
        birth_date=candidate.birth_date,
        ssn=candidate.ssn,
        over_18_age=candidate.over_18_age,
        mobile=candidate.mobile,
        home=candidate.home,
        work=candidate.work,
        work_ext=candidate.work_ext,
        relocation=candidate.relocation,
    )

