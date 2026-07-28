from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Finding:
    heuristic_id: str
    severity: Severity
    title: str
    detail: str
    suggestion: str
    weight: int
    positive: bool = False


@dataclass
class Check:
    heuristic_id: str
    severity: Severity
    title: str
    status: str
    reason: str = ""


@dataclass
class Report:
    score: int
    findings: list[Finding]
    checks: list[Check]
    input_count: int
    output_count: int
    psbt_version: int
    warnings: list[str] = field(default_factory=list)
    labels: list[dict] = field(default_factory=list)
