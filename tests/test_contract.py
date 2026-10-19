import copy
import json

import pytest

from scripts.export_openapi import SNAPSHOT, build
from tests.contract_diff import ADDITIVE, BREAKING, diff_contract

HOW_TO_UPDATE = (
    "\n\nThe public API contract no longer matches contract/openapi.json.\n"
    "- Accident? Undo the code change.\n"
    "- Intentional? Decide whether it is BREAKING for other teams (see labels above), then run\n"
    "      python scripts/export_openapi.py\n"
    "  and commit the updated contract/openapi.json together with the code change so reviewers\n"
    "  and consumers can see the difference. Do not regenerate it without reading the changes."
)


def test_api_contract_matches_the_saved_snapshot():
    saved = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    current = build()

    if saved != current:
        changes = diff_contract(saved, current)
        pytest.fail("Contract changes:\n  " + "\n  ".join(changes) + HOW_TO_UPDATE)


def test_snapshot_covers_the_documented_endpoints():
    saved = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    assert set(saved["paths"]) == {"/health", "/health/db", "/v1/items", "/v1/items/{item_id}"}
    assert len(saved["info"]["version"].split(".")) == 3  # semantic version, e.g. 1.1.0


# --- the diff helper itself -----------------------------------------------------------

@pytest.fixture
def spec():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_no_changes_means_no_report(spec):
    assert diff_contract(spec, copy.deepcopy(spec)) == []


def test_removed_property_is_flagged_as_breaking(spec):
    new = copy.deepcopy(spec)
    del new["components"]["schemas"]["Item"]["properties"]["quantity"]

    report = diff_contract(spec, new)

    assert any(line.startswith(BREAKING) and "Item.quantity removed" in line for line in report)


def test_new_optional_property_is_additive(spec):
    new = copy.deepcopy(spec)
    new["components"]["schemas"]["Item"]["properties"]["location"] = {"type": "string"}

    report = diff_contract(spec, new)

    assert report == [f"{ADDITIVE} Item.location added (optional)"]


def test_new_required_property_is_flagged_as_breaking(spec):
    new = copy.deepcopy(spec)
    new["components"]["schemas"]["ItemCreate"]["properties"]["location"] = {"type": "string"}
    new["components"]["schemas"]["ItemCreate"].setdefault("required", []).append("location")

    report = diff_contract(spec, new)

    assert any(line.startswith(BREAKING) and "ItemCreate.location" in line for line in report)


def test_removed_operation_and_changed_status_codes(spec):
    new = copy.deepcopy(spec)
    del new["paths"]["/v1/items/{item_id}"]["delete"]
    del new["paths"]["/v1/items"]["post"]["responses"]["409"]

    report = diff_contract(spec, new)

    assert any(line.startswith(BREAKING) and "removed operation DELETE /v1/items/{item_id}" in line for line in report)
    assert any(line.startswith(BREAKING) and "POST /v1/items: response 409 removed" in line for line in report)


def test_renaming_a_path_reports_both_sides(spec):
    new = copy.deepcopy(spec)
    new["paths"]["/v2/items"] = new["paths"].pop("/v1/items")

    report = diff_contract(spec, new)

    assert any(line.startswith(BREAKING) and "/v1/items" in line for line in report)
    assert any(line.startswith(ADDITIVE) and "/v2/items" in line for line in report)


def test_authentication_changes_are_flagged_as_breaking(spec):
    new = copy.deepcopy(spec)
    scheme = next(iter(new["components"]["securitySchemes"]))
    new["components"]["securitySchemes"]["ApiKeyAuth"] = {"type": "apiKey", "in": "header", "name": "X-API-Key"}
    del new["components"]["securitySchemes"][scheme]
    new["paths"]["/v1/items"]["get"]["security"] = [{"ApiKeyAuth": []}]

    report = diff_contract(spec, new)

    assert any(line.startswith(BREAKING) and f"scheme {scheme} removed" in line for line in report)
    assert any(line.startswith(BREAKING) and "ApiKeyAuth added" in line for line in report)
    assert any(line.startswith(BREAKING) and "GET /v1/items: authentication requirement changed" in line for line in report)


def test_wording_only_change_is_labelled_as_such(spec):
    new = copy.deepcopy(spec)
    new["info"]["description"] = "different words"

    report = diff_contract(spec, new)

    assert len(report) == 1 and "wording/metadata only" in report[0]


def test_type_change_is_flagged_as_breaking(spec):
    new = copy.deepcopy(spec)
    new["components"]["schemas"]["Item"]["properties"]["quantity"] = {"type": "string"}

    report = diff_contract(spec, new)

    assert any(line.startswith(BREAKING) and "Item.quantity changed type" in line for line in report)
