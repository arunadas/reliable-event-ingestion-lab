import io
import subprocess
import sys

import pytest

from reliable_ingestion.consumer.config import ConfigError, load_config, read_env_file
from reliable_ingestion.consumer.envelope import SourceRecord
from reliable_ingestion.consumer.schema import advisory_lock_key
from reliable_ingestion.consumer.sync_points import SyncPoints

BASE = {
    "CONSUMER_GROUP_ID": "cart-projection",
    "POSTGRES_DB": "ingestion",
    "POSTGRES_USER": "app",
    "POSTGRES_PASSWORD": "secret",
}


def test_env_file_parsing(tmp_path):
    path = tmp_path / ".env"
    path.write_text('# comment\n\nA=1\nB = two words \nC="quoted"\nnot a pair\n')
    assert read_env_file(path) == {"A": "1", "B": "two words", "C": "quoted"}


def test_missing_env_file_is_empty(tmp_path):
    assert read_env_file(tmp_path / "absent") == {}


def test_defaults(tmp_path):
    config = load_config(BASE, tmp_path / "absent")
    assert config.bootstrap_servers == "localhost:19092"
    assert config.topic == "cart-events"
    assert config.pg_host == "localhost"
    assert config.pg_port == 5432
    assert config.pg_schema == "cart_projection"
    assert config.sync_point is None
    assert config.sync_point_offset is None


def test_env_file_supplies_values_and_environment_overrides_them(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "CONSUMER_GROUP_ID=from-file\nPOSTGRES_DB=db\nPOSTGRES_USER=u\n"
        "POSTGRES_PASSWORD=p\nREDPANDA_KAFKA_PORT=29092\nPOSTGRES_PORT=6543\n"
    )
    config = load_config({"CONSUMER_GROUP_ID": "from-env"}, path)
    assert config.group_id == "from-env"
    assert config.bootstrap_servers == "localhost:29092"
    assert config.pg_port == 6543
    assert config.pg_db == "db"


@pytest.mark.parametrize(
    "missing",
    ["CONSUMER_GROUP_ID", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"],
)
def test_missing_required_value_is_a_config_error(tmp_path, missing):
    environ = {k: v for k, v in BASE.items() if k != missing}
    with pytest.raises(ConfigError, match=missing):
        load_config(environ, tmp_path / "absent")


@pytest.mark.parametrize("schema", ["Bad", "1abc", "a-b", 'x"; DROP', "a b"])
def test_unsafe_schema_name_is_rejected(tmp_path, schema):
    with pytest.raises(ConfigError, match="POSTGRES_SCHEMA"):
        load_config({**BASE, "POSTGRES_SCHEMA": schema}, tmp_path / "absent")


def test_non_integer_port_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError, match="POSTGRES_PORT"):
        load_config({**BASE, "POSTGRES_PORT": "abc"}, tmp_path / "absent")


def test_sync_point_settings(tmp_path):
    config = load_config(
        {
            **BASE,
            "CONSUMER_SYNC_POINT": "after_db_commit",
            "CONSUMER_SYNC_POINT_OFFSET": "2:17",
        },
        tmp_path / "absent",
    )
    assert config.sync_point == "after_db_commit"
    assert config.sync_point_offset == (2, 17)
    with pytest.raises(ConfigError):
        load_config({**BASE, "CONSUMER_SYNC_POINT_OFFSET": "x"}, tmp_path / "absent")


class _RecordingSyncPoints(SyncPoints):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.blocked = 0

    def _block(self):
        self.blocked += 1


RECORD = SourceRecord("cart-events", 1, 7, b"k", b"v")


def test_sync_point_is_disabled_by_default():
    stream = io.StringIO()
    sync = _RecordingSyncPoints(stream=stream)
    sync.reached("after_db_commit", RECORD)
    assert stream.getvalue() == ""
    assert sync.blocked == 0


def test_enabled_sync_point_writes_one_line_then_blocks():
    stream = io.StringIO()
    sync = _RecordingSyncPoints("after_db_commit", stream=stream)
    sync.reached("after_db_commit", RECORD)
    assert stream.getvalue() == "SYNC_POINT after_db_commit cart-events 1 7\n"
    assert sync.blocked == 1


def test_sync_point_ignores_other_names_and_other_offsets():
    stream = io.StringIO()
    sync = _RecordingSyncPoints("after_db_commit", only_at=(1, 8), stream=stream)
    sync.reached("after_db_commit", RECORD)
    sync.reached("something_else", RECORD)
    assert sync.blocked == 0
    sync.reached("after_db_commit", SourceRecord("cart-events", 1, 8, b"k", b"v"))
    assert sync.blocked == 1


def test_advisory_lock_key_is_a_signed_64_bit_integer():
    key = advisory_lock_key("cart", "schema_a", "cart-1")
    assert -(2**63) <= key < 2**63
    assert key == advisory_lock_key("cart", "schema_a", "cart-1")
    assert key != advisory_lock_key("cart", "schema_b", "cart-1")
    assert key != advisory_lock_key("cart", "schema_a", "cart-2")
    assert advisory_lock_key("a", "bc") != advisory_lock_key("ab", "c")


def test_advisory_lock_key_is_identical_across_processes():
    code = (
        "from reliable_ingestion.consumer.schema import advisory_lock_key;"
        "print(advisory_lock_key('cart', 'schema_a', 'cart-1'))"
    )
    keys = set()
    for seed in ("0", "1", "12345"):
        output = subprocess.run(
            [sys.executable, "-c", code],
            env={"PYTHONHASHSEED": seed, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            check=True,
        )
        keys.add(int(output.stdout))
    assert keys == {advisory_lock_key("cart", "schema_a", "cart-1")}
