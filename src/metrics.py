"""轻量级运行指标采集，输出 Prometheus 文本格式。"""

from __future__ import annotations

import time
from collections import defaultdict


class MetricsCollector:
    """进程内指标采集器，适用于单机/轻量部署。"""

    def __init__(self) -> None:
        self.started_at = time.time()
        self._counters: dict[str, float] = defaultdict(float)
        self._durations: dict[str, list[float]] = defaultdict(list)

    def inc(self, name: str, value: float = 1) -> None:
        self._counters[name] += value

    def observe(self, name: str, duration_seconds: float) -> None:
        self._durations[name].append(duration_seconds)

    def snapshot(self) -> dict:
        return {
            "uptime_seconds": time.time() - self.started_at,
            "counters": dict(self._counters),
            "durations": {k: list(v) for k, v in self._durations.items()},
        }

    def render_prometheus(self) -> str:
        lines: list[str] = []
        lines.append("# HELP vlm_app_uptime_seconds Application uptime in seconds")
        lines.append("# TYPE vlm_app_uptime_seconds gauge")
        lines.append(f"vlm_app_uptime_seconds {time.time() - self.started_at:.3f}")

        for name, value in sorted(self._counters.items()):
            metric_name = self._normalize(name)
            lines.append(f"# TYPE {metric_name} counter")
            lines.append(f"{metric_name} {value:.0f}")

        for name, values in sorted(self._durations.items()):
            if not values:
                continue
            metric_name = self._normalize(name)
            count = len(values)
            total = sum(values)
            avg = total / count
            lines.append(f"# TYPE {metric_name}_seconds summary")
            lines.append(f"{metric_name}_seconds_count {count}")
            lines.append(f"{metric_name}_seconds_sum {total:.6f}")
            lines.append(f"{metric_name}_seconds_avg {avg:.6f}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _normalize(name: str) -> str:
        clean = "".join(ch if ch.isalnum() else "_" for ch in name.lower())
        return f"vlm_{clean}"
