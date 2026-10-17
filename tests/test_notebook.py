import pytest
from django.urls import reverse

from dorm.storage import get_storage


@pytest.fixture(autouse=True)
def memory_storage(settings):
    settings.DORM_STORAGE = {"BACKEND": "memory"}


@pytest.mark.django_db
def test_run_flow_returns_last_cell(dorm_client):
    response = dorm_client.post(reverse("dorm:run"), {"cells": ["x = 6", "x * 7"]})
    assert response.status_code == 200
    assert response["X-Dorm-Status"] == "ok"
    assert b"42" in response.content


@pytest.mark.django_db
def test_run_single_code_field_still_works(dorm_client):
    response = dorm_client.post(reverse("dorm:run"), {"code": "1 + 1"})
    assert response["X-Dorm-Status"] == "ok"
    assert b"2" in response.content


@pytest.mark.django_db
def test_run_flow_error_reports_cell(dorm_client):
    response = dorm_client.post(reverse("dorm:run"), {"cells": ["x = 1", "undefined_name", "x"]})
    assert response["X-Dorm-Status"] == "error"
    assert response["X-Dorm-Cell"] == "1"
    assert b"In cell [2]" in response.content
    assert b"NameError" in response.content


@pytest.mark.django_db
def test_run_records_target_cell_in_history(dorm_client):
    dorm_client.post(reverse("dorm:run"), {"cells": ["x = 1", "x + 1"]})
    assert [h["code"] for h in get_storage().get_history()] == ["x + 1"]


@pytest.mark.django_db
def test_run_requires_post(dorm_client):
    assert dorm_client.get(reverse("dorm:run")).status_code == 405


@pytest.mark.django_db
def test_run_404_when_not_debug(client, settings):
    settings.DEBUG = False
    assert client.get(reverse("dorm:run")).status_code == 404
    assert client.post(reverse("dorm:run"), {"code": "1"}).status_code == 404


@pytest.mark.django_db
def test_save_command(dorm_client):
    response = dorm_client.post(reverse("dorm:save"), {"name": "all", "code": "Author.objects.all()"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "name": "all"}
    assert get_storage().get_saved_commands() == {"all": "Author.objects.all()"}


@pytest.mark.django_db
def test_save_command_requires_name_and_code(dorm_client):
    response = dorm_client.post(reverse("dorm:save"), {"name": "", "code": "x"})
    assert response.status_code == 400


@pytest.mark.django_db
def test_save_404_when_not_debug(client, settings):
    settings.DEBUG = False
    assert client.post(reverse("dorm:save"), {"name": "a", "code": "b"}).status_code == 404


@pytest.mark.django_db
def test_playground_renders_cell_template(dorm_client):
    response = dorm_client.get(reverse("dorm:playground"))
    assert b'id="dorm-cell-tpl"' in response.content
    assert b"codemirror" in response.content


@pytest.mark.django_db
def test_history_lists_recents_and_saved(dorm_client):
    storage = get_storage()
    storage.add_history("Author.objects.count()")
    storage.save_command("books", "Book.objects.all()")
    response = dorm_client.get(reverse("dorm:history"))
    assert response.status_code == 200
    body = response.content.decode()
    assert 'data-tab="recents"' in body and 'data-tab="saved"' in body
    assert "Author.objects.count()" in body
    assert "books" in body and "Book.objects.all()" in body


@pytest.mark.django_db
def test_history_escapes_code(dorm_client):
    get_storage().add_history("'<script>'")
    body = dorm_client.get(reverse("dorm:history")).content.decode()
    assert "<script>" not in body
    assert "&lt;script&gt;" in body


@pytest.mark.django_db
def test_history_empty_states(dorm_client):
    body = dorm_client.get(reverse("dorm:history")).content.decode()
    assert "No queries run yet." in body
    assert "No saved commands." in body


@pytest.mark.django_db
def test_history_404_when_not_debug(client, settings):
    settings.DEBUG = False
    assert client.get(reverse("dorm:history")).status_code == 404


@pytest.mark.django_db
def test_history_json_recents_newest_first(dorm_client):
    storage = get_storage()
    storage.add_history("first")
    storage.add_history("second")
    response = dorm_client.get(reverse("dorm:history"), {"format": "json"})
    assert response.json() == {"recents": ["second", "first"]}
