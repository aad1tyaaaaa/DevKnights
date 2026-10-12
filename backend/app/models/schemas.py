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


class ErrorResponse(BaseModel):
    detail: str
