# Producer Smoke Test — 2026-09-17

## Update (final fix wave)

This file was updated after the final whole-branch code review fix wave. Changes
relevant to this document:

- `pyproject.toml` now declares a `[build-system]` (hatchling), so `uv sync`
  installs `reliable_ingestion` into the venv as an editable install
  (previously only pytest's `pythonpath = ["src"]` made it importable, and
  `uv run python -m reliable_ingestion.producer` failed with
  `ModuleNotFoundError` outside of pytest).
- Three new tests cover graceful shutdown / flush and key/event-id invariants
  that this document previously claimed were validated without evidence; the
  "End-to-end orchestration with graceful shutdown" bullet at the bottom of
  this file has been corrected to cite them by name.

## Update (live broker verification — 2026-09-17)

A live smoke test against real Redpanda/PostgreSQL infrastructure was run and
corrects two earlier claims in this document:

- **The "Docker not available" claim below was wrong for this environment.**
  Docker, Redpanda, and PostgreSQL were brought up successfully and the
  producer was run against a real broker. See "Live broker run" below for
  the actual verified results.
- **`[tool.uv] link-mode = "copy"` does not reliably fix the editable-install
  problem.** Even with that setting in place, the plain command
  `uv run python -m reliable_ingestion.producer ...` still failed with
  `ModuleNotFoundError`, and the generated editable-install `.pth` file still
  had the macOS hidden (`UF_HIDDEN`) flag set. The "Packaging check" section
  below is corrected accordingly. The command verified to work reliably is
  `uv run --no-editable --locked python -m reliable_ingestion.producer ...`,
  which builds and installs a real (non-editable) wheel instead of relying on
  the editable `.pth` file, sidestepping the hidden-file issue entirely.

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

## Packaging check (corrected 2026-09-17 after live-broker verification)

`pyproject.toml` previously had no `[build-system]` section, so `reliable_ingestion`
was only importable inside pytest via `pythonpath = ["src"]`. Adding a hatchling
build backend makes `uv sync` install the package as an **editable** install,
but that alone is not reliable in this environment:

```
$ uv run python -m reliable_ingestion.producer --num-carts 3 --seed 1 --events-per-second 20
ModuleNotFoundError: No module named 'reliable_ingestion'
```

Verified root cause: the editable install's generated `.pth` file had the
macOS hidden (`UF_HIDDEN`) flag set even with `[tool.uv] link-mode = "copy"`
configured in `pyproject.toml` — CPython's `site.py` silently skips hidden
`.pth` files, so the package is on disk but never added to `sys.path`. The
`link-mode = "copy"` setting does **not** reliably prevent this in this
sandboxed development shell; an earlier version of this document overstated
its reliability based on a run that happened not to hit the issue.

**Verified working command:** installing and running as a real (non-editable)
wheel sidesteps the hidden `.pth` file entirely:

```
$ uv run --no-editable --locked python -c "import reliable_ingestion; print(reliable_ingestion.__file__)"
/Users/.../.venv/lib/python3.12/site-packages/reliable_ingestion/__init__.py

$ uv run --no-editable --locked python -m reliable_ingestion.producer --num-carts 3 --seed 1 --events-per-second 20
```

This succeeded and is now the documented way to run the producer (see "Live
broker run" below). `--locked` ensures the run uses `uv.lock` exactly rather
than re-resolving. The `[tool.uv] link-mode = "copy"` setting is left in
place (harmless, and may still help in some environments) but should not be
relied on by itself — always use `--no-editable --locked` to run the module
directly.

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

## Live broker run (verified 2026-09-17)

Docker Compose infrastructure was brought up and the producer was run against
a real Redpanda broker and PostgreSQL (PostgreSQL was up and healthy but not
otherwise exercised by this producer-only smoke test).

1. Infrastructure was started:
   ```bash
   docker compose up -d
   ```
   PostgreSQL, Redpanda, and Redpanda Console all reported running/healthy.

2. The producer was run as a real (non-editable) install — see "Packaging
   check" above for why `--no-editable --locked` is required:
   ```bash
   uv run --no-editable --locked python -m reliable_ingestion.producer \
     --num-carts 3 --seed 1 --events-per-second 20
   ```
   The first connection attempt logged a harmless IPv6 connection warning
   from `confluent-kafka`/librdkafka (the client falls back to IPv4), after
   which publication proceeded and completed successfully.

3. **Result:** 12 events generated, 12 published, 0 retries, 0 failures.

4. Topic inspection confirmed the Redpanda output contract:
   - `cart-events` has **3 partitions, 1 replica**, matching `specs/SPEC.md`'s
     "one topic with 3 partitions hash key on cart_id" requirement.
   - High watermarks after the run: partition 0 = 0, partition 1 = 4,
     partition 2 = 8 (sums to the 12 published events, distributed across
     partitions by the `cart_id` key as expected — some partitions can
     legitimately receive zero messages for a small, 3-cart run).

5. Consuming a sample of published messages confirmed, for the 5 messages
   inspected:
   - Each message's key equals its `cart_id`.
   - `aggregate.version` values are sequential per cart.
   - Partition offsets are sequential within each partition.
   - Events for the same cart arrive in the same partition, in lifecycle
     order (per-cart ordering preserved).

To reproduce, in another terminal:
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
