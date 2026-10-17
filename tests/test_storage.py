import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

from dorm.exceptions import DormStorageError
from dorm.storage import BaseStorage, get_storage, reset_storage
from dorm.storage.json_file import JSONFileStorage
from dorm.storage.memory import MemoryStorage


@pytest.fixture(autouse=True)
def _fresh_storage():
    reset_storage()
    yield
    reset_storage()


@pytest.fixture(params=["memory", "json", "sql", "redis"])
def storage(request, tmp_path):
    if request.param == "memory":
        return MemoryStorage()
    if request.param == "json":
        return JSONFileStorage(path=tmp_path / "store.json")
    if request.param == "sql":
        request.getfixturevalue("db")
        from dorm.storage.sql import SQLStorage
        return SQLStorage()
    fakeredis = pytest.importorskip("fakeredis")
    from dorm.storage.redis import RedisStorage
    return RedisStorage(client=fakeredis.FakeRedis())


# --- contract: every backend ---

def test_kv_roundtrip(storage):
    assert storage.get("ns", "missing", "dflt") == "dflt"
    storage.set("ns", "a", {"x": [1, 2]})
    storage.set("ns", "b", 2)
    storage.set("ns", "a", "replaced")
    assert storage.get("ns", "a") == "replaced"
    assert storage.all("ns") == {"a": "replaced", "b": 2}
    storage.delete("ns", "a")
    storage.delete("ns", "nope")
    assert storage.all("ns") == {"b": 2}


def test_namespaces_are_isolated(storage):
    storage.set("one", "k", 1)
    storage.set("two", "k", 2)
    storage.push("one", "x")
    assert storage.get("one", "k") == 1
    assert storage.get("two", "k") == 2
    assert storage.range("two") == []


def test_list_order_and_trim(storage):
    for i in range(5):
        storage.push("ns", i, max_len=3)
    assert storage.range("ns") == [4, 3, 2]
    assert storage.range("ns", 2) == [4, 3]
    assert storage.range("ns", 0) == []
    storage.clear("ns")
    assert storage.range("ns") == []


def test_history(storage):
    storage.history_limit = 3
    for code in ["a", "b", "b", "c", "d"]:
        storage.add_history(code)
    history = storage.get_history()
    assert [h["code"] for h in history] == ["d", "c", "b"]
    assert all("ts" in h for h in history)
    assert len(storage.get_history(1)) == 1
    storage.clear_history()
    assert storage.get_history() == []


def test_saved_commands(storage):
    storage.save_command("all", "Author.objects.all()")
    storage.save_command("books", "Book.objects.all()")
    assert storage.get_saved_commands() == {
        "all": "Author.objects.all()", "books": "Book.objects.all()",
    }
    storage.delete_saved_command("all")
    assert storage.get_saved_commands() == {"books": "Book.objects.all()"}


def test_settings(storage):
    assert storage.get_setting("layout", "row") == "row"
    storage.set_setting("layout", "col")
    storage.set_setting("verbose", False)
    assert storage.get_setting("layout") == "col"
    assert storage.get_settings() == {"layout": "col", "verbose": False}


# --- backend specifics ---

def test_json_persists_across_instances(tmp_path):
    path = tmp_path / "sub" / "store.json"
    JSONFileStorage(path=path).save_command("q", "Book.objects.count()")
    assert JSONFileStorage(path=path).get_saved_commands() == {"q": "Book.objects.count()"}


def test_json_corrupt_file_raises(tmp_path):
    path = tmp_path / "store.json"
    path.write_text("{not json")
    with pytest.raises(DormStorageError):
        JSONFileStorage(path=path).get_settings()


@pytest.mark.django_db
def test_sql_creates_table_lazily():
    from dorm.storage.sql import SQLStorage

    assert "dorm_storage" not in connection.introspection.table_names()
    SQLStorage().set_setting("k", "v")
    assert "dorm_storage" in connection.introspection.table_names()


def test_sql_unknown_alias():
    from dorm.storage.sql import SQLStorage

    with pytest.raises(ImproperlyConfigured):
        SQLStorage(alias="nope")


# --- factory ---

class CustomStorage(MemoryStorage):
    pass


def test_default_is_memory(settings):
    if hasattr(settings, "DORM_STORAGE"):
        del settings.DORM_STORAGE
    assert isinstance(get_storage(), MemoryStorage)
    assert get_storage() is get_storage()


def test_backend_by_name_with_options(settings, tmp_path):
    settings.DORM_STORAGE = {
        "BACKEND": "json",
        "OPTIONS": {"path": tmp_path / "s.json"},
        "HISTORY_LIMIT": 7,
    }
    storage = get_storage()
    assert isinstance(storage, JSONFileStorage)
    assert storage.history_limit == 7


def test_custom_backend_by_dotted_path(settings):
    settings.DORM_STORAGE = {"BACKEND": "tests.test_storage.CustomStorage"}
    assert isinstance(get_storage(), CustomStorage)


@pytest.mark.parametrize("config", [
    {"BACKEND": "nosuch"},
    {"BACKEND": "json"},
    {"BACKEND": "memory", "OPTIONS": {"bogus": 1}},
    {"BACKEND": "tests.test_storage.NotAStorage"},
    {"BACKEND": "tests.does_not_exist.Storage"},
])
def test_bad_config_raises(settings, config):
    settings.DORM_STORAGE = config
    with pytest.raises(ImproperlyConfigured):
        get_storage()


class NotAStorage:
    pass


def test_setting_change_resets_singleton(settings, tmp_path):
    settings.DORM_STORAGE = {"BACKEND": "memory"}
    first = get_storage()
    settings.DORM_STORAGE = {"BACKEND": "json", "OPTIONS": {"path": tmp_path / "s.json"}}
    assert get_storage() is not first
    assert isinstance(get_storage(), JSONFileStorage)


def test_base_storage_is_abstract():
    with pytest.raises(TypeError):
        BaseStorage()
