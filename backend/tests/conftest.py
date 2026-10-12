import httpx
import pytest

from app.api.routes import get_github_service, get_scan_service
from app.core.config import Settings
from app.core.security import submission_limiter
from app.github import GitHubService
from app.main import app
from app.models.database import ScanRepository
from app.parsers.npm_registry import NpmRegistryClient
from app.services import ScanService


@pytest.fixture(autouse=True)
def isolated_scan_service(tmp_path):
    """Default for every test: a throwaway database and no real npm traffic.
    Tests that need something else set their own dependency override, which replaces this one."""
    offline = NpmRegistryClient(transport=httpx.MockTransport(lambda request: httpx.Response(404)), retries=0)
    service = ScanService(ScanRepository(f"sqlite:///{tmp_path / 'test.db'}"), offline)
    app.dependency_overrides[get_scan_service] = lambda: service
    local_github = GitHubService(
        Settings(
            _env_file=None,
            github_client_id=None,
            github_client_secret=None,
            github_session_secret=None,
        )
    )
    app.dependency_overrides[get_github_service] = lambda: local_github
    submission_limiter.reset()
    yield service
    app.dependency_overrides.clear()
