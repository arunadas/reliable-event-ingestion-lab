# Producer Smoke Test — 2026-09-17

## Update (final fix wave)

This file was updated after the final whole-branch code review fix wave. Changes
relevant to this document:

- `pyproject.toml` now declares a `[build-system]` (hatchling) and pins
  `[tool.uv] link-mode = "copy"`, so `uv sync` installs `reliable_ingestion`
  into the venv (previously only pytest's `pythonpath = ["src"]` made it
  importable, and `uv run python -m reliable_ingestion.producer` failed with
  `ModuleNotFoundError` outside of pytest). Verified below.
- Three new tests cover graceful shutdown / flush and key/event-id invariants
  that this document previously claimed were validated without evidence; the
  "End-to-end orchestration with graceful shutdown" bullet at the bottom of
  this file has been corrected to cite them by name.

## Unit tests

`uv run pytest tests/unit -v`

```
============================= test session starts ==============================
platform darwin -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
collecting ... collected 41 items

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
tests/unit/producer/test_main.py::test_run_flushes_producer_after_normal_completion PASSED
tests/unit/producer/test_main.py::test_run_flushes_and_returns_metrics_on_shutdown_mid_run PASSED
tests/unit/producer/test_main.py::test_run_uses_consistent_key_per_cart_and_unique_event_ids PASSED
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

============================== 41 passed in 0.03s ==============================
```

**Summary:** 41 passed in 0.03s (38 previously + 3 new: graceful-shutdown/flush
and key/event-id invariant tests added in the final fix wave)

## Packaging check (final fix wave)

`pyproject.toml` previously had no `[build-system]` section, so `reliable_ingestion`
was only importable inside pytest via `pythonpath = ["src"]`. After adding a
hatchling build backend and re-running `uv sync`, the module resolves without
any `PYTHONPATH` override:

```
$ uv run python -m reliable_ingestion.producer --help
usage: __main__.py [-h] [--broker-address BROKER_ADDRESS] [--topic TOPIC]
                   [--events-per-second EVENTS_PER_SECOND]
                   [--num-carts NUM_CARTS] [--max-events MAX_EVENTS]
                   [--run-duration-seconds RUN_DURATION_SECONDS] [--seed SEED]
                   [--duplicate-probability DUPLICATE_PROBABILITY]
                   [--delay-probability DELAY_PROBABILITY]
                   [--max-delay-seconds MAX_DELAY_SECONDS]

Cart event generator
...
```

Verified with a fresh `.venv` (`rm -rf .venv && uv sync`) and 5 repeated
`uv run python -m reliable_ingestion.producer --help` invocations, all
succeeding. Note: `[tool.uv] link-mode = "copy"` was also added — in this
sandboxed development shell, the default macOS clone/CoW link mode was
observed to intermittently mark the generated editable-install `.pth` file
hidden (`UF_HIDDEN`), which CPython's `site.py` silently skips, causing
`ModuleNotFoundError` outside of a fresh install. Forcing `copy` mode avoided
this consistently across repeated syncs.

## Known behavior: some carts purchase zero items

`CartItemSavedForLater` can move an item's entire active quantity to
saved-for-later before purchase. When that happens for every item in a
cart, `CartPurchased` is emitted with `total_amount_minor: 0` and
`item_count: 0`. This is arithmetically correct per the spec's own
definition of `total_amount_minor` (sum over active, non-saved-for-later
item quantities) and is not disallowed by any business invariant, but it
is a real fraction of the generated fixture data: a spot check across 500
seeds found roughly 21% of carts purchase nothing. Downstream consumer and
reconciliation experiments that assume every generated cart produces a
nonzero purchase should account for this rather than assume it away.

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
- End-to-end orchestration (main): event count, determinism, max-events limit,
  duplicate injection, and exit-nonzero-on-exhausted-retries
  (`test_run_generates_expected_event_count_for_single_cart`,
  `test_run_is_deterministic_given_same_seed`,
  `test_run_respects_max_events_limit`,
  `test_run_duplicates_when_duplicate_probability_is_one`,
  `test_run_exits_nonzero_when_publication_exhausts_retries`)
- Graceful shutdown and flush behavior (main):
  `test_run_flushes_producer_after_normal_completion` asserts the producer's
  `flush()` is called after a normal run, and
  `test_run_flushes_and_returns_metrics_on_shutdown_mid_run` simulates a
  `_ShutdownRequested` signal firing mid-run (via a fake `sleep` that raises
  it) and asserts `run()` returns a `GeneratorMetrics` object without
  propagating the exception, with `flush()` still called
- Key/event-id invariants (main):
  `test_run_uses_consistent_key_per_cart_and_unique_event_ids` asserts all
  events for one cart share the same Redpanda key, all `event_id`s in a run
  are unique, and each cart's `aggregate.version` restarts at 1
