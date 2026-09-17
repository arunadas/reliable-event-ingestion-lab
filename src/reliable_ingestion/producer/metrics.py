from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GeneratorMetrics:
    events_generated_total: int = 0
    events_published_total: int = 0
    publication_retries_total: int = 0
    publication_failures_total: int = 0
    publish_latency_ms_total: float = 0.0
    publish_latency_count: int = 0
    run_duration_seconds: float = 0.0

    def record_generated(self) -> None:
        self.events_generated_total += 1

    def record_published(self, latency_ms: float) -> None:
        self.events_published_total += 1
        self.publish_latency_ms_total += latency_ms
        self.publish_latency_count += 1

    def record_retry(self) -> None:
        self.publication_retries_total += 1

    def record_failure(self) -> None:
        self.publication_failures_total += 1

    def average_publish_latency_ms(self) -> float:
        if self.publish_latency_count == 0:
            return 0.0
        return self.publish_latency_ms_total / self.publish_latency_count

    def as_dict(self) -> dict[str, float | int]:
        return {
            "events_generated_total": self.events_generated_total,
            "events_published_total": self.events_published_total,
            "publication_retries_total": self.publication_retries_total,
            "publication_failures_total": self.publication_failures_total,
            "publish_latency_ms_avg": self.average_publish_latency_ms(),
            "run_duration_seconds": self.run_duration_seconds,
        }
