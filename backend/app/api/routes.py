import hmac
import json
import secrets
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app import __version__
from app.detection.ai_ranker import GeminiFindingRanker
from app.detection.osv import OsvClient
from app.core.config import settings
from app.core.security import limit_submissions
from app.gate import TrustGate
from app.github import GitHubApiError, GitHubService
from app.models.database import ScanRepository
from app.blockchain.registry import ReleaseRegistryReader
from app.blockchain.verify import ReleaseVerifier
from app.models.schemas import (
    ErrorResponse,
    Finding,
    GateReport,
    GateRequest,
    GitHubAuthStatus,
    GitHubRepository,
    GitHubScanRequest,
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
GITHUB_SESSION_COOKIE = "provenyx_github_session"
GITHUB_STATE_COOKIE = "provenyx_github_oauth_state"
GITHUB_SESSION_MAX_AGE = 8 * 60 * 60
GITHUB_STATE_MAX_AGE = 10 * 60
finding_ranker = (
    GeminiFindingRanker(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        base_url=settings.gemini_base_url,
        timeout_seconds=settings.gemini_timeout_seconds,
    )
    if settings.ai_ranking_enabled and settings.gemini_api_key is not None
    else None
)
scan_service = ScanService(
    ScanRepository(settings.database_url),
    NpmRegistryClient(
        base_url=settings.npm_registry_url,
        concurrency=settings.npm_registry_concurrency,
        timeout_seconds=settings.npm_registry_timeout_seconds,
        retries=settings.npm_registry_retries,
    ),
    osv=OsvClient(
        base_url=settings.osv_api_url,
        concurrency=settings.osv_concurrency,
        timeout_seconds=settings.osv_timeout_seconds,
        retries=settings.osv_retries,
    ),
    finding_ranker=finding_ranker,
)
github_service = GitHubService(settings)


release_verifier = ReleaseVerifier(
    ReleaseRegistryReader(
        rpc_url=settings.registry_rpc_url,
        deployment_file=settings.registry_deployment_file,
        address=settings.registry_address,
        timeout_seconds=settings.registry_timeout_seconds,
    ),
    scan_service.registry,
)


trust_gate = TrustGate(scan_service.registry, osv=scan_service.osv, verifier=release_verifier)


def get_scan_service() -> ScanService:
    return scan_service


def get_trust_gate() -> TrustGate:
    return trust_gate


def get_release_verifier() -> ReleaseVerifier:
    return release_verifier


def get_github_service() -> GitHubService:
    return github_service


def _github_token(request: Request, github: GitHubService) -> str:
    session = github.codec.decode(request.cookies.get(GITHUB_SESSION_COOKIE)) if github.configured else None
    token = session.get("token") if session else None
    if not isinstance(token, str):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Connect a GitHub account first")
    return token


def _github_error(exc: GitHubApiError) -> HTTPException:
    code = exc.status_code if exc.status_code in (401, 403, 404, 413, 422) else 502
    return HTTPException(code, exc.detail)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="provenyx-api", version=__version__)


@router.get("/api/github/auth/status", response_model=GitHubAuthStatus)
async def github_auth_status(
    request: Request,
    response: Response,
    github: Annotated[GitHubService, Depends(get_github_service)],
) -> GitHubAuthStatus:
    if not github.configured:
        return GitHubAuthStatus(configured=False, connected=False)
    session = github.codec.decode(request.cookies.get(GITHUB_SESSION_COOKIE))
    token = session.get("token") if session else None
    if not isinstance(token, str):
        return GitHubAuthStatus(configured=True, connected=False)
    try:
        user = await github.get_user(token)
    except GitHubApiError:
        response.delete_cookie(GITHUB_SESSION_COOKIE)
        return GitHubAuthStatus(configured=True, connected=False)
    return GitHubAuthStatus(
        configured=True,
        connected=True,
        login=user.get("login"),
        avatar_url=user.get("avatar_url"),
    )


DEFAULT_AFTER_LOGIN = "/github"


def safe_next_path(value: str | None) -> str:
    """A same-site path to return to after sign-in. Anything else falls back to the default, so the
    login link cannot be used as an open redirect (e.g. next=//evil.example or next=https://…)."""
    if value and value.startswith("/") and not value.startswith(("//", "/\\")) and "\\" not in value and len(value) <= 512:
        return value
    return DEFAULT_AFTER_LOGIN


def _frontend_redirect(path: str, **query: str) -> RedirectResponse:
    separator = "&" if "?" in path else "?"
    return RedirectResponse(f"{settings.frontend_url}{path}{separator}{urlencode(query)}")


@router.get("/api/github/auth/login")
def github_auth_login(
    github: Annotated[GitHubService, Depends(get_github_service)],
    next: str | None = None,
) -> RedirectResponse:
    if not github.configured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "GitHub authentication is not configured")
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(github.authorization_url(state))
    response.set_cookie(
        GITHUB_STATE_COOKIE,
        # `next` rides in the encrypted state cookie, so the callback cannot be pointed elsewhere.
        github.codec.encode({"state": state, "next": safe_next_path(next)}, GITHUB_STATE_MAX_AGE),
        max_age=GITHUB_STATE_MAX_AGE,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
    )
    return response


@router.get("/api/github/auth/callback")
async def github_auth_callback(
    request: Request,
    github: Annotated[GitHubService, Depends(get_github_service)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    state_payload = github.codec.decode(request.cookies.get(GITHUB_STATE_COOKIE)) if github.configured else None
    expected_state = state_payload.get("state") if state_payload else None
    after_login = safe_next_path(state_payload.get("next") if state_payload else None)
    if error or not code or not state or not isinstance(expected_state, str) or not hmac.compare_digest(state, expected_state):
        return _frontend_redirect(after_login, github_error=error or "invalid_oauth_state")
    try:
        token = await github.exchange_code(code)
    except GitHubApiError as exc:
        return _frontend_redirect(after_login, github_error=exc.detail)
    response = _frontend_redirect(after_login, connected="1")
    response.delete_cookie(GITHUB_STATE_COOKIE)
    response.set_cookie(
        GITHUB_SESSION_COOKIE,
        github.codec.encode({"token": token}, GITHUB_SESSION_MAX_AGE),
        max_age=GITHUB_SESSION_MAX_AGE,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
    )
    return response


@router.post("/api/github/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def github_auth_logout(response: Response) -> None:
    response.delete_cookie(GITHUB_SESSION_COOKIE)


@router.get("/api/github/repositories", response_model=list[GitHubRepository])
async def github_repositories(
    request: Request,
    github: Annotated[GitHubService, Depends(get_github_service)],
) -> list[GitHubRepository]:
    try:
        return await github.list_repositories(_github_token(request, github))
    except GitHubApiError as exc:
        raise _github_error(exc)


@router.get("/api/github/repositories/{owner}/{repository}/lockfiles", response_model=list[str])
async def github_repository_lockfiles(
    owner: str,
    repository: str,
    request: Request,
    github: Annotated[GitHubService, Depends(get_github_service)],
) -> list[str]:
    try:
        return await github.find_lockfiles(_github_token(request, github), owner, repository)
    except GitHubApiError as exc:
        raise _github_error(exc)


@router.post(
    "/api/github/scans",
    response_model=ScanAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(limit_submissions)],
)
async def create_github_scan(
    body: GitHubScanRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    github: Annotated[GitHubService, Depends(get_github_service)],
    service: Annotated[ScanService, Depends(get_scan_service)],
) -> ScanAccepted:
    try:
        content = await github.fetch_lockfile(
            _github_token(request, github), body.owner, body.repository, body.lockfile_path, settings.max_scan_bytes
        )
    except GitHubApiError as exc:
        raise _github_error(exc)
    try:
        lockfile = ScanRequest.model_validate(
            {
                "lockfile": json.loads(content),
                "project_name": f"{body.owner}/{body.repository}",
                "client": "github/0.1.0",
            }
        )
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Repository package-lock.json is invalid") from exc
    scan_id = service.create_scan(lockfile.lockfile.model_dump(mode="json"), lockfile.project_name)
    background_tasks.add_task(service.analyze_scan, scan_id)
    return ScanAccepted(
        scan_id=scan_id,
        status="accepted",
        message="GitHub lockfile received. Dependency analysis has started.",
    )


@router.post(
    "/api/scans",
    response_model=ScanAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    responses={413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}},
    dependencies=[Depends(limit_submissions)],
)
async def create_scan(
    request: Request,
    background_tasks: BackgroundTasks,
    service: Annotated[ScanService, Depends(get_scan_service)],
) -> ScanAccepted:
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json")

    scan_request = _validate(ScanRequest, await _read_capped_body(request, settings.max_scan_bytes))

    scan_id = service.create_scan(scan_request.lockfile.model_dump(mode="json"), scan_request.project_name)
    background_tasks.add_task(service.analyze_scan, scan_id)
    return ScanAccepted(
        scan_id=scan_id,
        status="accepted",
        message="Lockfile received. Dependency analysis has started.",
    )


@router.post(
    "/api/gate",
    response_model=GateReport,
    responses={413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}},
    dependencies=[Depends(limit_submissions)],
)
async def evaluate_trust_gate(
    request: Request,
    gate: Annotated[TrustGate, Depends(get_trust_gate)],
) -> GateReport:
    """Pull request trust gate: examines only releases the head lockfile adds or updates relative to the base."""
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json")
    gate_request = _validate(GateRequest, await _read_capped_body(request, 2 * settings.max_scan_bytes))
    return await gate.evaluate(
        gate_request.head_lockfile.model_dump(mode="json"),
        gate_request.base_lockfile.model_dump(mode="json") if gate_request.base_lockfile else None,
        fail_on=gate_request.fail_on,
        label=gate_request.label,
    )


async def _read_capped_body(request: Request, limit: int) -> bytes:
    """Read the body ourselves so the size cap also holds for chunked uploads without Content-Length."""
    too_large = HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Request body exceeds {limit} bytes")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise too_large
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > limit:
            raise too_large
    return bytes(body)


def _validate(model, body: bytes):
    try:
        return model.model_validate_json(body)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors(include_url=False, include_context=False, include_input=False))


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
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
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
        for row in service.repository.list_recent(limit, offset)
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
