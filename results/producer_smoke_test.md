# Producer Smoke Test — 2026-09-17

## Unit tests

`uv run pytest tests/unit -v`

```
============================= test session starts ==============================
platform darwin -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
collecting ... collected 38 items

tests/unit/producer/test_cart_simulator.py::test_first_event_is_cart_created_at_version_1 PASSED
tests/unit/producer/test_cart_simulator.py::test_last_event_is_cart_purchased PASSED
tests/unit/producer/test_cart_simulator.py::test_versions_increase_by_one_without_gaps_across_many_seeds PASSED
tests/unit/producer/test_cart_simulator.py::test_at_least_one_item_added_event_across_many_seeds PASSED
tests/unit/producer/test_cart_simulator.py::test_saved_for_later_never_exceeds_previously_active_quantity PASSED
tests/unit/producer/test_cart_simulator.py::test_purchase_total_excludes_saved_for_later_quantity PASSED
tests/unit/producer/test_cart_simulator.py::test_purchase_payload_uses_given_order_id PASSED
tests/unit/producer/test_cart_simulator.py::test_same_seed_produces_identical_event_sequence PASSED
tests/unit/producer/test_cart_simulator.py::test_money_fields_are_always_int PASSED
tests/unit/producer/test_config.py::test_defaults_produce_a_valid_config PASSED
tests/unit/producer/test_config.py::test_broker_address_falls_back_to_env_var PASSED
tests/unit/producer/test_config.py::test_explicit_args_override_defaults PASSED
tests/unit/producer/test_config.py::test_producer_instance_id_is_unique_per_call PASSED
tests/unit/producer/test_events.py::test_format_timestamp_is_utc_millisecond_with_z_suffix PASSED
tests/unit/producer/test_events.py::test_to_dict_omits_payload_when_none PASSED
tests/unit/producer/test_events.py::test_to_dict_includes_payload_when_present PASSED
tests/unit/producer/test_events.py::test_to_dict_has_required_envelope_fields PASSED
tests/unit/producer/test_events.py::test_to_json_bytes_round_trips_as_utf8_json PASSED
tests/unit/producer/test_fault_injection.py::test_should_duplicate_never_triggers_at_zero_probability PASSED
tests/unit/producer/test_fault_injection.py::test_should_duplicate_always_triggers_at_one_probability PASSED
tests/unit/producer/test_fault_injection.py::test_delay_seconds_is_zero_at_zero_probability PASSED
tests/unit/producer/test_fault_injection.py::test_delay_seconds_within_bounds_at_full_probability PASSED
tests/unit/producer/test_fault_injection.py::test_same_rng_state_is_deterministic PASSED
tests/unit/producer/test_main.py::test_run_generates_expected_event_count_for_single_cart PASSED
tests/unit/producer/test_main.py::test_run_is_deterministic_given_same_seed PASSED
tests/unit/producer/test_main.py::test_run_respects_max_events_limit PASSED
tests/unit/producer/test_main.py::test_run_duplicates_when_duplicate_probability_is_one PASSED
tests/unit/producer/test_main.py::test_run_exits_nonzero_when_publication_exhausts_retries PASSED
tests/unit/producer/test_metrics.py::test_counters_start_at_zero PASSED
tests/unit/producer/test_metrics.py::test_record_generated_increments_counter PASSED
tests/unit/producer/test_metrics.py::test_record_published_tracks_count_and_average_latency PASSED
tests/unit/producer/test_metrics.py::test_record_retry_and_failure_increment_counters PASSED
tests/unit/producer/test_metrics.py::test_as_dict_contains_all_expected_keys PASSED
tests/unit/producer/test_publisher.py::test_publish_success_returns_delivery_and_records_metrics PASSED
tests/unit/producer/test_publisher.py::test_publish_uses_cart_id_as_key PASSED
tests/unit/producer/test_publisher.py::test_publish_retries_on_failure_then_succeeds_with_identical_payload PASSED
tests/unit/producer/test_publisher.py::test_publish_raises_after_max_retries_and_records_failure PASSED
tests/unit/producer/test_publisher.py::test_publish_retries_on_callback_timeout_then_succeeds PASSED

============================== 38 passed in 0.03s ==============================
```

**Summary:** 38 passed in 0.03s

## Live broker run

Docker daemon is not available in this environment. The producer was validated via unit tests only (fake producer, no live broker).

To perform a live smoke test once infrastructure is available:

1. Start the infrastructure:
   ```bash
   docker compose up -d
   ```

2. Run the producer:
   ```bash
   uv run python -m reliable_ingestion.producer --num-carts 3 --seed 1 --events-per-second 20
   ```

3. In another terminal, consume a sample of published messages:
   ```bash
   docker compose exec redpanda rpk topic consume cart-events -n 5
   ```

The unit test suite validates:
- Event sequence generation and correctness (cart simulator)
- Event envelope serialization (events)
- Configuration parsing and defaults (config)
- Kafka publisher with retry logic (publisher)
- Metrics recording (metrics)
- Fault injection (fault injection)
- End-to-end orchestration with graceful shutdown (main)
