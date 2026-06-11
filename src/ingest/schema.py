from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Item:
    title: str
    url: str
    source: str
    timestamp: datetime
    score: float = 0.0
    summary: str = ""
    extra: dict = field(default_factory=dict)

    def age_hours(self, now: Optional[datetime] = None) -> float:
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        ts = self.timestamp
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        return max(0.0, (now - ts).total_seconds() / 3600.0)
