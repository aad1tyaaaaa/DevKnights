from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SUPPORTED_LOCKFILE_VERSIONS = (1, 2, 3)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class Lockfile(BaseModel):
    """Minimal structural check of an npm package-lock.json. Contents are never executed."""

    model_config = ConfigDict(extra="allow")

    name: str | None = None
    version: str | None = None
    lockfileVersion: int
    packages: dict[str, dict[str, Any]] | None = None
    dependencies: dict[str, dict[str, Any]] | None = None

    @model_validator(mode="after")
    def check_shape(self) -> "Lockfile":
        if self.lockfileVersion not in SUPPORTED_LOCKFILE_VERSIONS:
            raise ValueError(
                f"Unsupported lockfileVersion {self.lockfileVersion}; expected one of {SUPPORTED_LOCKFILE_VERSIONS}"
            )
        if self.lockfileVersion >= 2 and self.packages is None:
            raise ValueError("lockfileVersion 2/3 requires a 'packages' object")
        if self.lockfileVersion == 1 and self.dependencies is None:
            raise ValueError("lockfileVersion 1 requires a 'dependencies' object")
        return self


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lockfile: Lockfile
    project_name: str | None = Field(default=None, max_length=214)
    client: str | None = Field(default=None, max_length=64, description="e.g. 'vscode-extension/0.1.0'")


class ScanAccepted(BaseModel):
    scan_id: str
    status: Literal["accepted"]
    message: str


class ScanSummary(BaseModel):
    packages: int
    direct: int
    transitive: int
    findings: int


class ScanDetail(BaseModel):
    scan_id: str
    status: Literal["accepted", "analyzing", "complete", "failed"]
    created_at: datetime
    project_name: str | None
    summary: ScanSummary | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class RegistryMetadataResponse(BaseModel):
    status: Literal["available", "unavailable"]
    description: str | None = None
    license: str | None = None
    deprecated: str | None = None
    published_at: str | None = None
    dist_integrity: str | None = None
    error: str | None = None


class GraphNode(BaseModel):
    id: str
    name: str
    version: str
    direct: bool
    lockfile_paths: list[str]
    resolved_urls: list[str] = Field(default_factory=list)
    lockfile_integrities: list[str] = Field(default_factory=list)
    registry: RegistryMetadataResponse


class GraphEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source: str = Field(alias="from")
    target: str = Field(alias="to")
    type: Literal["prod", "dev", "optional", "peer"]


class ScanGraph(BaseModel):
    scan_id: str
    status: Literal["accepted", "analyzing", "complete", "failed"]
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class VersionChangeResponse(BaseModel):
    name: str
    from_versions: list[str]
    to_versions: list[str]


class ScanComparisonResponse(BaseModel):
    baseline_scan_id: str
    current_scan_id: str
    added_packages: list[str]
    removed_packages: list[str]
    version_changes: list[VersionChangeResponse]
    added_edges: list[GraphEdge]


class FindingEvidence(BaseModel):
    source: Literal["npm-registry", "lockfile", "registry-contract"]
    field: str
    value: Any
    observed_at: datetime


class Finding(BaseModel):
    id: str
    rule_id: str
    package: str
    version: str
    severity: Literal["info", "low", "medium", "high"]
    confidence: Literal["low", "medium", "high"]
    priority_score: int = Field(ge=0, le=100)
    title: str
    explanation: str
    evidence: list[FindingEvidence] = Field(min_length=1)
    paths: list[list[str]] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str
