from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ScanRow(Base):
    __tablename__ = "scans"

    scan_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    project_name: Mapped[str | None] = mapped_column(String(214))
    lockfile: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    graph: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    error: Mapped[str | None] = mapped_column(Text)


class ScanFindingRow(Base):
    __tablename__ = "scan_findings"

    finding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.scan_id"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class ScanRepository:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        self._sessions = sessionmaker(self._engine, expire_on_commit=False)
        Base.metadata.create_all(self._engine)

    def create(self, scan_id: str, project_name: str | None, lockfile: dict[str, Any]) -> None:
        with self._sessions.begin() as session:
            session.add(
                ScanRow(
                    scan_id=scan_id,
                    status="accepted",
                    created_at=datetime.now(timezone.utc),
                    project_name=project_name,
                    lockfile=lockfile,
                    warnings=[],
                )
            )

    def set_analyzing(self, scan_id: str) -> None:
        self._update(scan_id, status="analyzing")

    def set_complete(
        self,
        scan_id: str,
        *,
        project_name: str | None,
        summary: dict[str, Any],
        graph: dict[str, Any],
        findings: list[dict[str, Any]],
        warnings: list[str],
    ) -> None:
        with self._sessions.begin() as session:
            row = session.get(ScanRow, scan_id)
            if row is None:
                raise KeyError(f"Unknown scan {scan_id}")
            row.status = "complete"
            row.project_name = project_name
            row.summary = summary
            row.graph = graph
            row.warnings = warnings
            row.error = None
            session.execute(delete(ScanFindingRow).where(ScanFindingRow.scan_id == scan_id))
            session.add_all(
                ScanFindingRow(finding_id=finding["id"], scan_id=scan_id, payload=finding)
                for finding in findings
            )

    def set_failed(self, scan_id: str, error: str) -> None:
        self._update(scan_id, status="failed", error=error)

    def get(self, scan_id: str) -> ScanRow | None:
        with self._sessions() as session:
            return session.scalar(select(ScanRow).where(ScanRow.scan_id == scan_id))

    def get_findings(self, scan_id: str) -> list[dict[str, Any]]:
        with self._sessions() as session:
            rows = session.scalars(
                select(ScanFindingRow)
                .where(ScanFindingRow.scan_id == scan_id)
                .order_by(ScanFindingRow.finding_id)
            )
            findings = [row.payload for row in rows]
            return sorted(
                findings,
                key=lambda finding: (
                    -(
                        finding.get("ai_priority_score")
                        if isinstance(finding.get("ai_priority_score"), int)
                        else finding.get("priority_score", 0)
                    ),
                    -finding.get("priority_score", 0),
                    finding.get("rule_id", ""),
                    finding.get("package", ""),
                ),
            )

    def list_recent(self, limit: int = 50, offset: int = 0) -> list[ScanRow]:
        with self._sessions() as session:
            return list(
                session.scalars(
                    select(ScanRow)
                    .order_by(ScanRow.created_at.desc())
                    .limit(max(1, min(limit, 200)))
                    .offset(max(0, offset))
                )
            )

    def list_unfinished(self) -> list[str]:
        """Scans accepted or mid-analysis, oldest first: work a restart would otherwise strand."""
        with self._sessions() as session:
            return list(
                session.scalars(
                    select(ScanRow.scan_id)
                    .where(ScanRow.status.in_(("accepted", "analyzing")))
                    .order_by(ScanRow.created_at)
                )
            )

    def find_latest_complete(self, project_name: str, *, before: datetime, exclude_scan_id: str) -> ScanRow | None:
        """The most recent completed scan of the project created strictly before `before`.

        Requiring an earlier scan keeps comparisons pointing forward in time even when scans finish out of order.
        """
        with self._sessions() as session:
            return session.scalar(
                select(ScanRow)
                .where(
                    ScanRow.project_name == project_name,
                    ScanRow.status == "complete",
                    ScanRow.scan_id != exclude_scan_id,
                    ScanRow.created_at < before,
                )
                .order_by(ScanRow.created_at.desc())
                .limit(1)
            )

    def _update(self, scan_id: str, **values: Any) -> None:
        with self._sessions.begin() as session:
            row = session.get(ScanRow, scan_id)
            if row is None:
                raise KeyError(f"Unknown scan {scan_id}")
            for name, value in values.items():
                setattr(row, name, value)