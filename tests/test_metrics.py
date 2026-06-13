"""运行指标采集测试。"""

from src.metrics import MetricsCollector


def test_metrics_render_prometheus():
    metrics = MetricsCollector()
    metrics.inc("chat_requests_total")
    metrics.observe("chat_request_duration", 0.25)

    text = metrics.render_prometheus()

    assert "vlm_app_uptime_seconds" in text
    assert "vlm_chat_requests_total 1" in text
    assert "vlm_chat_request_duration_seconds_count 1" in text
