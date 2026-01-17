from __future__ import annotations

import logging
from fastapi import Depends, APIRouter, HTTPException, Request, status

from config import get_settings
from app.db.sql_server import SQLServerRepository
from app.supabase.client import SupabaseRepository
from app.api.candidate_sync.schemas import (
    CandidateSyncRequest,
    CandidateSyncResponse,
)
from app.api.candidate_sync.logic import (
    CandidateNotFoundError,
    MultipleCandidatesFoundError,
    sync_candidate_by_email,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidate-sync", tags=["candidate-sync"])


def get_sql_repo(request: Request) -> SQLServerRepository:
    return request.app.state.sql_repo


def get_supabase_repo(request: Request) -> SupabaseRepository:
    return request.app.state.supabase_repo


@router.post(
    "",
    response_model=CandidateSyncResponse,
    status_code=status.HTTP_200_OK,
)
async def sync_candidate(
    payload: CandidateSyncRequest,
    request: Request,
    sql_repo: SQLServerRepository = Depends(get_sql_repo),
    supabase_repo: SupabaseRepository = Depends(get_supabase_repo),
) -> CandidateSyncResponse:
    logger = logging.getLogger("candidate-sync")

    try:
        candidate: CandidateContact = await sync_candidate_by_email(
            payload.email,
            sql_repo,
            supabase_repo,
        )
        logger.info(
            "Candidate sync succeeded",
            extra={"log_to_db": True, "service_name": "candidate_sync", "email": payload.email, "candidate_id": getattr(candidate, 'cand_id', None)}
        )
        return CandidateSyncResponse(
            success=True,
            message="Candidate synchronized successfully.",
            data=candidate,
        )
    except CandidateNotFoundError:
        logger.info("Candidate not found", extra={"email": payload.email})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="We could not find an account with that email.",
        )
    except MultipleCandidatesFoundError:
        logger.warning("Multiple candidate records found", extra={"email": payload.email})
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Found multiple accounts with your email please contact the support team.",
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Candidate sync failed", extra={"email": payload.email})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to process your request at this time.",
        ) from exc

