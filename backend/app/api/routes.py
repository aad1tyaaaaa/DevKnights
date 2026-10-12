from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app import __version__
from app.core.config import settings
from app.models.database import ScanRepository
from app.blockchain.registry import ReleaseRegistryReader
from app.blockchain.verify import ReleaseVerifier
from app.models.schemas import (
    ErrorResponse,
    Finding,
    HealthResponse,
    ScanAccepted,
    ScanComparisonResponse,
    ScanDetail,
    ScanGraph,
    ScanRequest,
    VerificationResult,
    VerifyRequest,
)
from app.parsers.npm_registry import NpmRegistryClient
from app.services import ScanService

router = APIRouter()
scan_service = ScanService(
    ScanRepository(settings.database_url),
    NpmRegistryClient(
        base_url=settings.npm_registry_url,
        concurrency=settings.npm_registry_concurrency,
        timeout_seconds=settings.npm_registry_timeout_seconds,
        retries=settings.npm_registry_retries,
    ),
)


release_verifier = ReleaseVerifier(
    ReleaseRegistryReader(
        rpc_url=settings.registry_rpc_url,
        deployment_file=settings.registry_deployment_file,
        address=settings.registry_address,
        timeout_seconds=settings.registry_timeout_seconds,
    ),
    scan_service.registry,
)


def get_scan_service() -> ScanService:
    return scan_service


def get_release_verifier() -> ReleaseVerifier:
    return release_verifier


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="provenyx-api", version=__version__)


@router.post(
    "/api/scans",
    response_model=ScanAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    responses={413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}},
)
async def create_scan(
    request: Request,
    background_tasks: BackgroundTasks,
    service: Annotated[ScanService, Depends(get_scan_service)],
) -> ScanAccepted:
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
        scan_request = ScanRequest.model_validate_json(bytes(body))
    except ValidationError as exc:
        raise RequestValidationError(exc.errors(include_url=False, include_context=False, include_input=False))

    scan_id = service.create_scan(scan_request.lockfile.model_dump(mode="json"), scan_request.project_name)
    background_tasks.add_task(service.analyze_scan, scan_id)
    return ScanAccepted(
        scan_id=scan_id,
        status="accepted",
        message="Lockfile received. Dependency analysis has started.",
    )


@router.get("/api/scans/{scan_id}", response_model=ScanDetail)
def get_scan(
    scan_id: str,
    service: Annotated[ScanService, Depends(get_scan_service)],
) -> ScanDetail:
    row = service.repository.get(scan_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan not found")
    return ScanDetail(
        scan_id=row.scan_id,
        status=row.status,
        created_at=row.created_at,
        project_name=row.project_name,
        summary=row.summary,
        warnings=row.warnings,
        error=row.error,
    )


@router.get("/api/scans", response_model=list[ScanDetail])
def list_scans(
    service: Annotated[ScanService, Depends(get_scan_service)],
) -> list[ScanDetail]:
    return [
        ScanDetail(
            scan_id=row.scan_id,
            status=row.status,
            created_at=row.created_at,
            project_name=row.project_name,
            summary=row.summary,
            warnings=row.warnings,
            error=row.error,
        )
        for row in service.repository.list_recent()
    ]


@router.get("/api/scans/{scan_id}/graph", response_model=ScanGraph)
def get_scan_graph(
    scan_id: str,
    service: Annotated[ScanService, Depends(get_scan_service)],
) -> ScanGraph:
    row = service.repository.get(scan_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan not found")
    if row.graph is None:
        return ScanGraph(scan_id=row.scan_id, status=row.status, warnings=row.warnings)
    return ScanGraph.model_validate(row.graph)


@router.get("/api/scans/{scan_id}/findings", response_model=list[Finding])
def get_scan_findings(
    scan_id: str,
    service: Annotated[ScanService, Depends(get_scan_service)],
) -> list[Finding]:
    if service.repository.get(scan_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan not found")
    return [Finding.model_validate(finding) for finding in service.repository.get_findings(scan_id)]


@router.get(
    "/api/scans/{scan_id}/compare/{baseline_scan_id}",
    response_model=ScanComparisonResponse,
)
def compare_scans(
    scan_id: str,
    baseline_scan_id: str,
    service: Annotated[ScanService, Depends(get_scan_service)],
) -> ScanComparisonResponse:
    try:
        return service.compare_scans(baseline_scan_id, scan_id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan not found")
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.post("/api/releases/verify", response_model=VerificationResult)
async def verify_release(
    body: VerifyRequest,
    verifier: Annotated[ReleaseVerifier, Depends(get_release_verifier)],
) -> VerificationResult:
    return await verifier.verify(body.package, body.version)
