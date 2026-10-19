"""Describe, in plain words, how one OpenAPI document differs from another.

A heuristic aid for reviewers, not a judge: it labels changes that usually break consumers
("BREAKING?") and those that are usually safe ("additive"). A person decides.
"""

BREAKING = "BREAKING?"
ADDITIVE = "additive "
OTHER = "other    "

_METHODS = {"get", "put", "post", "delete", "patch", "options", "head"}


def _operations(spec: dict) -> dict:
    return {
        (method.upper(), path): op
        for path, item in spec.get("paths", {}).items()
        for method, op in item.items()
        if method in _METHODS
    }


def _strip_docs(schema):
    """Ignore titles/descriptions when comparing types: wording changes are not shape changes."""
    if isinstance(schema, dict):
        return {k: _strip_docs(v) for k, v in schema.items() if k not in ("title", "description")}
    if isinstance(schema, list):
        return [_strip_docs(v) for v in schema]
    return schema


def diff_contract(old: dict, new: dict) -> list[str]:
    lines: list[str] = []

    old_ops, new_ops = _operations(old), _operations(new)
    for method, path in sorted(old_ops.keys() - new_ops.keys(), key=lambda k: (k[1], k[0])):
        lines.append(f"{BREAKING} removed operation {method} {path}")
    for method, path in sorted(new_ops.keys() - old_ops.keys(), key=lambda k: (k[1], k[0])):
        lines.append(f"{ADDITIVE} new operation {method} {path}")

    for key in sorted(old_ops.keys() & new_ops.keys(), key=lambda k: (k[1], k[0])):
        method, path = key
        old_op, new_op = old_ops[key], new_ops[key]
        old_codes, new_codes = set(old_op.get("responses", {})), set(new_op.get("responses", {}))
        for code in sorted(old_codes - new_codes):
            lines.append(f"{BREAKING} {method} {path}: response {code} removed")
        for code in sorted(new_codes - old_codes):
            lines.append(f"{ADDITIVE} {method} {path}: response {code} added")

        def required_params(op):
            return {p["name"] for p in op.get("parameters", []) if p.get("required")}

        for name in sorted(required_params(new_op) - required_params(old_op)):
            lines.append(f"{BREAKING} {method} {path}: parameter '{name}' is now required")

    old_schemas = old.get("components", {}).get("schemas", {})
    new_schemas = new.get("components", {}).get("schemas", {})
    for name in sorted(old_schemas.keys() - new_schemas.keys()):
        lines.append(f"{BREAKING} schema {name} removed")
    for name in sorted(new_schemas.keys() - old_schemas.keys()):
        lines.append(f"{ADDITIVE} new schema {name}")

    for name in sorted(old_schemas.keys() & new_schemas.keys()):
        old_props = old_schemas[name].get("properties", {})
        new_props = new_schemas[name].get("properties", {})
        old_required = set(old_schemas[name].get("required", []))
        new_required = set(new_schemas[name].get("required", []))
        for prop in sorted(old_props.keys() - new_props.keys()):
            lines.append(f"{BREAKING} {name}.{prop} removed")
        for prop in sorted(new_props.keys() - old_props.keys()):
            if prop in new_required:
                lines.append(f"{BREAKING} {name}.{prop} added and REQUIRED (existing callers will not send it)")
            else:
                lines.append(f"{ADDITIVE} {name}.{prop} added (optional)")
        for prop in sorted(old_props.keys() & new_props.keys()):
            if _strip_docs(old_props[prop]) != _strip_docs(new_props[prop]):
                lines.append(f"{BREAKING} {name}.{prop} changed type or rules")
            if prop in new_required and prop not in old_required:
                lines.append(f"{BREAKING} {name}.{prop} became required")

    if old != new and not lines:
        lines.append(f"{OTHER} wording/metadata only (descriptions, titles, version)")
    return lines
