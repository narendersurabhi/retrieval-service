"""FR-008 / FR-009: the search and ingest contracts carry ADR 0005's rules."""

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
API = yaml.safe_load((ROOT / "contracts" / "openapi.yaml").read_text())
TOOL = json.loads((ROOT / "contracts" / "mcp" / "search.json").read_text())
DOC_PATH = "/v1/collections/{collection}/documents/{document_id}"
FORBIDDEN_ARGS = {"user", "user_id", "tenant", "tenant_id", "groups", "acl", "filter", "filters"}


def schema(name: str) -> Draft202012Validator:
    return Draft202012Validator({"$ref": f"#/components/schemas/{name}",
                                 "components": API["components"]})  # fmt: skip


def resolve(node):
    while isinstance(node, dict) and "$ref" in node:
        target = API
        for part in node["$ref"][2:].split("/"):
            target = target[part]
        node = target
    return node


@pytest.mark.spec("FR-008")
def test_search_arguments_cannot_carry_identity_or_filters():
    inputs = TOOL["inputSchema"]
    assert TOOL["name"] == "search" and TOOL["version"] == "0.1.0"
    assert set(inputs["properties"]) == {"query", "k", "collection"}
    assert inputs["additionalProperties"] is False and inputs["required"] == ["query"]
    assert not FORBIDDEN_ARGS & set(inputs["properties"])
    tool = Draft202012Validator(inputs)
    tool.validate({"query": "refund policy", "k": 5})
    assert not tool.is_valid({"query": "x", "tenant": "other-tenant"})
    assert not tool.is_valid({"query": "x", "k": 51})
    assert not tool.is_valid({"query": ""})


@pytest.mark.spec("FR-008")
def test_http_search_matches_the_tool_and_requires_identity():
    op = API["paths"]["/v1/search"]["post"]
    assert API["components"]["schemas"]["SearchRequest"] == TOOL["inputSchema"]
    assert API["components"]["schemas"]["SearchResults"] == TOOL["outputSchema"]
    headers = {resolve(p)["name"]: resolve(p) for p in op["parameters"]}
    assert headers["x-agent-identity"]["required"] is True
    schema("SearchResults").validate({
        "results": [{"chunk_id": "c1", "document_id": "d1", "collection": "policies",
                     "score": 0.82, "text": "Refunds within 30 days.",
                     "source": {"title": "Refund policy", "uri": "https://example.test/r"}}],
        "truncated": False, "tokens": 9,
    })  # fmt: skip


@pytest.mark.spec("FR-009")
def test_ingest_replaces_a_document_version_atomically():
    item = API["paths"][DOC_PATH]
    assert {"put", "get", "delete"} <= set(item)
    put = item["put"]
    assert set(put["responses"]) >= {"200", "409"}
    assert "Idempotency-Key" in {p["name"] for p in put["parameters"]}
    assert item["delete"]["responses"].keys() == {"204"}
    version = schema("DocumentVersion")
    version.validate({"version": "2026-11-10T00:00:00Z", "title": "Refund policy",
                      "acl": {"tenants": ["acme"], "groups": ["support"]},
                      "chunks": [{"chunk_id": "d1#0", "order": 0, "text": "Refunds...",
                                  "metadata": {"heading": "Refunds", "page": "1"}}]})  # fmt: skip
    assert not version.is_valid({"version": "1", "acl": {}, "chunks": []})
    no_embeddings = {"version": "1", "acl": {}, "chunks": [
        {"chunk_id": "c", "order": 0, "text": "t", "embedding": [0.1, 0.2]}]}  # fmt: skip
    assert not version.is_valid(no_embeddings)  # the service owns the embedding model
    status = API["components"]["schemas"]["DocumentStatus"]["properties"]["status"]
    assert status["enum"] == ["indexed", "unchanged"]


@pytest.mark.spec("FR-009")
def test_ingest_uses_service_credentials():
    assert API["security"] == [{"serviceBearer": []}]
    assert API["components"]["securitySchemes"]["serviceBearer"]["scheme"] == "bearer"
    put = API["paths"][DOC_PATH]["put"]
    assert "x-agent-identity" not in {resolve(p)["name"] for p in put.get("parameters", [])}
