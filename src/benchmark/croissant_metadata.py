from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_RAI_FIELDS = [
    "rai:useCases",
    "rai:outOfScopeUses",
    "rai:dataCollection",
    "rai:personalSensitiveInformation",
    "rai:limitations",
]


def validate_croissant_metadata(path: Path | str) -> dict[str, Any]:
    metadata_path = Path(path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    if metadata.get("conformsTo") != "http://mlcommons.org/croissant/1.1":
        errors.append("conformsTo must be http://mlcommons.org/croissant/1.1")
    if not metadata.get("url"):
        errors.append("url is required for a canonical artifact location")
    if not metadata.get("license"):
        errors.append("license is required")

    distribution = metadata.get("distribution", [])
    if not distribution:
        errors.append("distribution must include at least one cr:FileObject")
    for resource in distribution:
        if resource.get("@type") != "cr:FileObject":
            errors.append(f"distribution resource {resource.get('@id', '<missing-id>')} is not cr:FileObject")
        for key in ["@id", "name", "contentUrl", "encodingFormat"]:
            if not resource.get(key):
                errors.append(f"distribution resource is missing {key}")

    record_sets = metadata.get("recordSet", [])
    if not record_sets:
        errors.append("recordSet must describe at least one structured record set")
    for record_set in record_sets:
        record_id = record_set.get("@id", "<missing-id>")
        if record_set.get("@type") != "cr:RecordSet":
            errors.append(f"recordSet {record_id} is not cr:RecordSet")
        if not record_set.get("field"):
            errors.append(f"recordSet {record_id} has no fields")
        if not record_set.get("key"):
            errors.append(f"recordSet {record_id} has no key")

    for field in REQUIRED_RAI_FIELDS:
        if not metadata.get(field):
            errors.append(f"missing required RAI field {field}")

    return {
        "status": "pass" if not errors else "fail",
        "path": str(metadata_path),
        "distribution_count": len(distribution),
        "record_set_count": len(record_sets),
        "errors": errors,
    }
