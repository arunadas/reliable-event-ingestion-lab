from reliable_ingestion.producer.metrics import GeneratorMetrics


def test_counters_start_at_zero():
    metrics = GeneratorMetrics()
    assert metrics.events_generated_total == 0
    assert metrics.events_published_total == 0
    assert metrics.publication_retries_total == 0
    assert metrics.publication_failures_total == 0
    assert metrics.average_publish_latency_ms() == 0.0


def test_record_generated_increments_counter():
    metrics = GeneratorMetrics()
    metrics.record_generated()
    metrics.record_generated()
    assert metrics.events_generated_total == 2


def test_record_published_tracks_count_and_average_latency():
    metrics = GeneratorMetrics()
    metrics.record_published(10.0)
    metrics.record_published(20.0)
    assert metrics.events_published_total == 2
    assert metrics.average_publish_latency_ms() == 15.0


def test_record_retry_and_failure_increment_counters():
    metrics = GeneratorMetrics()
    metrics.record_retry()
    metrics.record_failure()
    assert metrics.publication_retries_total == 1
    assert metrics.publication_failures_total == 1


def test_as_dict_contains_all_expected_keys():
    metrics = GeneratorMetrics()
    metrics.record_generated()
    metrics.record_published(5.0)
    d = metrics.as_dict()
    assert set(d) == {
        "events_generated_total",
        "events_published_total",
        "publication_retries_total",
        "publication_failures_total",
        "publish_latency_ms_avg",
        "run_duration_seconds",
    }
