from reliable_ingestion.producer.config import parse_args


def test_defaults_produce_a_valid_config():
    config = parse_args([])
    assert config.topic == "cart-events"
    assert config.num_carts == 10
    assert config.seed == 0
    assert config.max_events is None
    assert config.run_duration_seconds is None
    assert config.duplicate_probability == 0.0
    assert config.delay_probability == 0.0
    assert config.max_delay_seconds == 0.0
    assert config.producer_instance_id.startswith("generator-")


def test_broker_address_falls_back_to_env_var(monkeypatch):
    monkeypatch.setenv("REDPANDA_KAFKA_PORT", "19092")
    config = parse_args([])
    assert config.broker_address == "localhost:19092"


def test_explicit_args_override_defaults():
    config = parse_args(
        [
            "--broker-address",
            "redpanda:9092",
            "--topic",
            "custom-topic",
            "--num-carts",
            "5",
            "--seed",
            "42",
            "--max-events",
            "100",
            "--run-duration-seconds",
            "30",
            "--duplicate-probability",
            "0.1",
            "--delay-probability",
            "0.2",
            "--max-delay-seconds",
            "3.5",
        ]
    )
    assert config.broker_address == "redpanda:9092"
    assert config.topic == "custom-topic"
    assert config.num_carts == 5
    assert config.seed == 42
    assert config.max_events == 100
    assert config.run_duration_seconds == 30.0
    assert config.duplicate_probability == 0.1
    assert config.delay_probability == 0.2
    assert config.max_delay_seconds == 3.5


def test_producer_instance_id_is_unique_per_call():
    first = parse_args([])
    second = parse_args([])
    assert first.producer_instance_id != second.producer_instance_id
