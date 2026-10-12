import uuid

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app import __version__
from app.core.config import settings
from app.models.schemas import ErrorResponse, HealthResponse, ScanAccepted, ScanRequest

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="provenyx-api", version=__version__)


@router.post(
    "/api/scans",
    response_model=ScanAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    responses={413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}},
)
async def create_scan(request: Request) -> ScanAccepted:
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json")

    # Read the body ourselves so the size cap also holds for chunked uploads without Content-Length.
    limit = settings.max_scan_bytes
    too_large = HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Request body exceeds {limit} bytes")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise too_large
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > limit:
            raise too_large

    try:
        ScanRequest.model_validate_json(bytes(body))
    except ValidationError as exc:
        raise RequestValidationError(exc.errors(include_url=False, include_context=False, include_input=False))

    # Phase 1: the lockfile is validated and then discarded. Nothing is stored or analysed.
    return ScanAccepted(
        scan_id=str(uuid.uuid4()),
        status="accepted",
        message="Lockfile received. Dependency analysis is not implemented in Phase 1.",
    )
