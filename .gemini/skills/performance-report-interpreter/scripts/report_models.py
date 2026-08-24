#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Workload:
    users: int | None = None
    duration_seconds: float | None = None
    ramp_up_seconds: float | None = None
    pacing_seconds: float | None = None


@dataclass
class Metrics:
    requests: int | None = None
    successful: int | None = None
    failed: int | None = None
    success_rate: float | None = None
    error_rate: float | None = None
    throughput: float | None = None
    average_ms: float | None = None
    p50_ms: float | None = None
    p90_ms: float | None = None
    p95_ms: float | None = None
    p99_ms: float | None = None
    max_ms: float | None = None


@dataclass
class TransactionMetric:
    label: str
    samples: int
    success_rate: float
    error_rate: float
    average_ms: float
    p95_ms: float
    p99_ms: float
    throughput: float
    status: str


@dataclass
class EvidenceSample:
    label: str
    kind: str
    method: str | None = None
    url: str | None = None
    status_code: str | None = None
    success: bool | None = None
    elapsed_ms: float | None = None
    assertions_passed: bool | None = None
    request_headers: dict[str, str] = field(default_factory=dict)
    request_body: str | None = None
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: str | None = None
    source: str | None = None


@dataclass
class EvidenceBundle:
    coverage: str
    transactions: list[EvidenceSample] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage": self.coverage,
            "transactions": [asdict(item) for item in self.transactions],
            "notes": self.notes,
        }


@dataclass
class Interpretation:
    verdict: str = "DESCONOCIDO"
    risk: str = "No disponible"
    decision: str = "No disponible"
    decision_message: str = ""
    trend: str = "No disponible"
    trend_summary: str = ""
    workload: Workload = field(default_factory=Workload)
    metrics: Metrics = field(default_factory=Metrics)
    transactions: list[TransactionMetric] = field(default_factory=list)
    executive_summary: str = ""
    metric_explanations: list[str] = field(default_factory=list)
    evidence_statement: str = ""
    limitations: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
