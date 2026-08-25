from __future__ import annotations

from m8flow_backend.observability.request_context import REQUEST_ID_HEADER


def test_request_id_is_generated_and_echoed(client):
    response = client.get("/v1.0/status")
    assert response.status_code == 200
    assert response.headers.get(REQUEST_ID_HEADER)


def test_inbound_request_id_is_preserved(client):
    response = client.get("/v1.0/status", headers={REQUEST_ID_HEADER: "req-fixed-123"})
    assert response.headers.get(REQUEST_ID_HEADER) == "req-fixed-123"


def test_each_request_gets_a_distinct_request_id(client):
    first = client.get("/v1.0/status").headers.get(REQUEST_ID_HEADER)
    second = client.get("/v1.0/status").headers.get(REQUEST_ID_HEADER)
    assert first and second and first != second
