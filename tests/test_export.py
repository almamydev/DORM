import csv
import io
import json
import zipfile

import pytest
from django.urls import reverse
from library.models import Author

from dorm import exports


def _content(response) -> bytes:
    return b"".join(response.streaming_content)


@pytest.fixture
def authors(db):
    def make(n):
        Author.objects.bulk_create(
            Author(name=f"A;uthor {i}", birth_year=1900 + i % 100) for i in range(n)
        )
    return make


# --- preview truncation info ---

@pytest.mark.django_db
def test_truncated_preview_reports_total(dorm_client, authors):
    authors(250)
    body = dorm_client.post(reverse("dorm:run"), {"cells": ["Author.objects.all()"]}).content.decode()
    assert 'data-truncated="true"' in body
    assert 'data-total="250"' in body
    assert "Showing first 200 of 250 rows" in body


@pytest.mark.django_db
def test_small_preview_not_truncated(dorm_client, authors):
    authors(3)
    body = dorm_client.post(reverse("dorm:run"), {"cells": ["Author.objects.all()"]}).content.decode()
    assert 'data-truncated="false"' in body


# --- full export endpoint ---

@pytest.mark.django_db
def test_export_single_csv_has_all_rows(dorm_client, authors):
    authors(250)
    response = dorm_client.post(reverse("dorm:export"), {
        "cells": ["qs = Author.objects.order_by('id')", "qs"], "format": "csv", "verbose": "1",
    })
    assert response.status_code == 200
    assert 'filename="author_records.csv"' in response["Content-Disposition"]
    rows = list(csv.reader(io.StringIO(_content(response).decode()), delimiter=";"))
    assert rows[0] == ["ID", "Nom de l'auteur", "Année de naissance"]
    assert len(rows) == 251
    assert rows[1][1] == "Author 0"   # semicolons stripped


@pytest.mark.django_db
def test_export_field_names_when_not_verbose(dorm_client, authors):
    authors(2)
    response = dorm_client.post(reverse("dorm:export"), {
        "cells": ["Author.objects.values('name')"], "format": "json", "verbose": "0",
    })
    data = json.loads(_content(response))
    assert data[0] == {"name": "A;uthor 0"}   # JSON keeps semicolons
    assert len(data) == 2


@pytest.mark.django_db
def test_export_large_result_is_zipped_in_parts(dorm_client, authors):
    authors(3200)
    response = dorm_client.post(reverse("dorm:export"), {
        "cells": ["Author.objects.order_by('id')"], "format": "csv", "verbose": "0",
    })
    assert response["Content-Type"] == "application/zip"
    assert 'filename="author_records.zip"' in response["Content-Disposition"]

    zf = zipfile.ZipFile(io.BytesIO(_content(response)))
    assert zf.namelist() == [
        "author_records_part001.csv", "author_records_part002.csv", "author_records_part003.csv",
    ]
    counts = [len(zf.read(n).decode().splitlines()) - 1 for n in zf.namelist()]
    assert counts == [1500, 1500, 200]
    assert zf.read("author_records_part001.csv").decode().splitlines()[0] == '"id";"name";"birth_year"'


@pytest.mark.django_db
def test_export_query_error(dorm_client):
    response = dorm_client.post(reverse("dorm:export"), {"cells": ["nope"], "format": "csv"})
    assert response.status_code == 400
    assert "NameError" in response.json()["error"]


@pytest.mark.django_db
def test_export_non_tabular_result(dorm_client):
    response = dorm_client.post(reverse("dorm:export"), {"cells": ["1 + 1"], "format": "csv"})
    assert response.status_code == 400


@pytest.mark.django_db
def test_export_bad_format(dorm_client):
    response = dorm_client.post(reverse("dorm:export"), {"cells": ["1"], "format": "xls"})
    assert response.status_code == 400


@pytest.mark.django_db
def test_export_404_when_not_debug(client, settings):
    settings.DEBUG = False
    assert client.post(reverse("dorm:export"), {"cells": ["1"], "format": "csv"}).status_code == 404


# --- build_export unit ---

def test_build_export_exact_boundary_is_single_file():
    rows = [[str(i)] for i in range(exports.ROWS_PER_FILE)]
    _, filename, content_type = exports.build_export("csv", ["n"], rows, "x")
    assert filename == "x.csv"
    assert content_type.startswith("text/csv")


def test_build_export_one_over_boundary_zips():
    rows = [[str(i)] for i in range(exports.ROWS_PER_FILE + 1)]
    fh, filename, _ = exports.build_export("json", ["n"], iter(rows), "x")
    zf = zipfile.ZipFile(fh)
    assert filename == "x.zip"
    assert [len(json.loads(zf.read(n))) for n in zf.namelist()] == [exports.ROWS_PER_FILE, 1]
