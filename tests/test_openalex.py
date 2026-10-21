from unittest.mock import Mock

import pytest
import requests

from openalex_pipeline.openalex import OpenAlexClient, OpenAlexError, redact, short_id


def test_short_id_accepts_openalex_urls_and_ids():
    assert short_id("https://openalex.org/W123") == "W123"
    assert short_id("W123") == "W123"
    assert short_id(None) is None
    assert short_id("") is None


def test_redact_hides_api_key():
    assert "secret-value" not in redact("request failed: secret-value", "secret-value")


def test_resolve_institution_normalizes_ror(monkeypatch):
    client = OpenAlexClient(min_interval=0)
    response = Mock()
    response.json.return_value = {
        "id": "https://openalex.org/I123",
        "display_name": "Example University",
    }
    get = Mock(return_value=response)
    monkeypatch.setattr(client, "_get", get)

    result = client.resolve_institution("https://ror.org/012345678/")

    assert result == {"institution_id": "I123", "name": "Example University"}
    get.assert_called_once_with("institutions/ror:012345678", {})


def test_iter_work_pages_uses_cursor_and_stops_at_limit(monkeypatch):
    client = OpenAlexClient(min_interval=0)
    pages = [
        {"results": [{"id": f"W{index}"} for index in range(2)], "meta": {"next_cursor": "next"}},
        {"results": [{"id": f"W{index}"} for index in range(2, 4)], "meta": {"next_cursor": "last"}},
    ]
    get = Mock(side_effect=[Mock(json=Mock(return_value=page)) for page in pages])
    monkeypatch.setattr(client, "_get", get)

    result = list(client.iter_work_pages("I123", "2025-01-01", "2025-12-31", per_page=2, max_works=3))

    assert [page_number for page_number, _ in result] == [1, 2]
    assert get.call_args_list[0].args[1]["cursor"] == "*"
    assert get.call_args_list[1].args[1]["cursor"] == "next"


def test_iter_work_pages_stops_on_empty_page(monkeypatch):
    client = OpenAlexClient(min_interval=0)
    get = Mock(return_value=Mock(json=Mock(return_value={"results": [], "meta": {"next_cursor": "next"}})))
    monkeypatch.setattr(client, "_get", get)

    assert list(client.iter_work_pages("I123", "2025-01-01", "2025-12-31")) == [
        (1, {"results": [], "meta": {"next_cursor": "next"}})
    ]
    get.assert_called_once()


def test_iter_work_pages_validates_page_size():
    client = OpenAlexClient(min_interval=0)
    with pytest.raises(ValueError, match="per_page"):
        list(client.iter_work_pages("I123", "2025-01-01", "2025-12-31", per_page=201))


def test_http_errors_do_not_leak_key(monkeypatch):
    client = OpenAlexClient(api_key="secret-value", min_interval=0)
    response = Mock(status_code=403, text="invalid key secret-value")
    monkeypatch.setattr(client.session, "get", Mock(return_value=response))

    with pytest.raises(OpenAlexError) as error:
        client._get("works", {})

    assert "secret-value" not in str(error.value)


def test_request_exception_does_not_echo_url_or_encoded_key(monkeypatch):
    client = OpenAlexClient(api_key="secret-value", min_interval=0)
    request_error = requests.ConnectionError(
        "connection failed for https://api.openalex.org/works?api_key=secret%2Dvalue"
    )
    monkeypatch.setattr(client.session, "get", Mock(side_effect=request_error))

    with pytest.raises(OpenAlexError) as error:
        client._get("works", {})

    assert "secret" not in str(error.value)
    assert "https://" not in str(error.value)