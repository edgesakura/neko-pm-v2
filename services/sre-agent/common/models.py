from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class AlertSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertCategory(Enum):
    API_5XX_SPIKE = "API_5XX_SPIKE"
    POD_CRASHLOOP = "POD_CRASHLOOP"
    HIGH_LATENCY = "HIGH_LATENCY"
    UNKNOWN = "UNKNOWN"


@dataclass
class Alert:
    id: str
    title: str
    description: str
    severity: AlertSeverity
    category: AlertCategory
    source: str  # "datadog", "cloudwatch", etc.
    timestamp: str
    tags: Dict[str, str] = field(default_factory=dict)
    raw_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Diagnosis:
    alert_id: str
    category: AlertCategory
    severity: AlertSeverity
    summary: str
    metrics: List[Dict[str, Any]] = field(default_factory=list)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    health_checks: List[Dict[str, Any]] = field(default_factory=list)
    root_cause: Optional[str] = None
    recommended_actions: List[str] = field(default_factory=list)


@dataclass
class Incident:
    id: str
    title: str
    description: str
    severity: str
    category: str
    root_cause: str
    resolution: str
    duration_minutes: int
    timestamp: str
    tags: List[str] = field(default_factory=list)
    lessons_learned: Optional[str] = None
