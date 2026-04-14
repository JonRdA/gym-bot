from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gym_bot.config.service import UserConfigService

_YAML = """
exercises:
  pullup: { metrics: [reps, weight] }
  row:    { metrics: [reps] }
workouts:
  pull: [pullup, row]
"""


@pytest.fixture
def yaml_file(tmp_path):
    path = tmp_path / "training.yaml"
    path.write_text(_YAML)
    return str(path)


def _fake_db(find_return=None) -> SimpleNamespace:
    collection = SimpleNamespace(
        find_one=AsyncMock(return_value=find_return),
        update_one=AsyncMock(),
    )
    return SimpleNamespace(user_configs=collection)


async def test_get_config_seeds_new_user_from_yaml(yaml_file):
    db = _fake_db(find_return=None)
    svc = UserConfigService(db, yaml_file, owner_user_id=None)

    config = await svc.get_config(user_id=42)

    assert config.user_id == 42
    assert "pullup" in config.exercises
    assert config.workouts == {"pull": ["pullup", "row"]}
    db.user_configs.update_one.assert_awaited_once()
    _, kwargs = db.user_configs.update_one.call_args
    assert kwargs["upsert"] is True


async def test_get_config_parses_existing_document_without_touching_yaml(tmp_path):
    db = _fake_db(
        find_return={
            "user_id": 7,
            "exercises": {"pullup": {"metrics": ["reps"]}},
            "workouts": {"pull": ["pullup"]},
        }
    )
    # Point at a non-existent YAML — if the service touches it, the test fails loudly.
    svc = UserConfigService(db, str(tmp_path / "missing.yaml"), owner_user_id=None)

    config = await svc.get_config(user_id=7)

    assert config.user_id == 7
    assert config.get_exercise("pullup").metrics == ["reps"]
    db.user_configs.update_one.assert_not_awaited()


async def test_get_config_uses_cache_on_second_call(yaml_file):
    db = _fake_db(find_return=None)
    svc = UserConfigService(db, yaml_file, owner_user_id=None)

    first = await svc.get_config(user_id=1)
    second = await svc.get_config(user_id=1)

    assert first is second
    assert db.user_configs.find_one.await_count == 1


async def test_sync_owner_is_noop_when_owner_not_set(yaml_file):
    db = _fake_db()
    svc = UserConfigService(db, yaml_file, owner_user_id=None)

    await svc.sync_owner()

    db.user_configs.update_one.assert_not_awaited()


async def test_sync_owner_upserts_and_caches_when_owner_set(yaml_file):
    db = _fake_db()
    svc = UserConfigService(db, yaml_file, owner_user_id=99)

    await svc.sync_owner()

    db.user_configs.update_one.assert_awaited_once()
    # Subsequent get_config should serve from cache — no DB lookup.
    config = await svc.get_config(user_id=99)
    assert config.user_id == 99
    db.user_configs.find_one.assert_not_awaited()
