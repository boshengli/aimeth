#!/usr/bin/env python3
"""Verify declared file identities and hashes, not scientific validity."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    root = manifest_path.parent
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != "1.0":
        raise ValueError("Unsupported or missing artifact manifest schema_version")
    records = data.get("artifacts")
    if not isinstance(records, list) or not records:
        raise ValueError("At least one artifact is required")
    ids, paths = set(), set()
    for item in records:
        if not isinstance(item, dict):
            raise ValueError("Artifact must be an object")
        artifact_id = item.get("id")
        rel = item.get("path")
        if not isinstance(artifact_id, str) or not artifact_id or artifact_id in ids:
            raise ValueError("Missing or duplicate artifact id")
        if not isinstance(rel, str) or not rel or rel in paths:
            raise ValueError("Missing or duplicate artifact path")
        relative = Path(rel)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Artifact path must stay inside its bundle")
        p = root / relative
        if any(part.is_symlink() for part in [p, *p.parents] if part != root and root in part.parents):
            raise ValueError("Symlinks are not accepted as frozen artifacts")
        resolved = p.resolve()
        if root not in resolved.parents or not resolved.is_file():
            raise ValueError(f"Missing or escaped artifact: {rel}")
        if resolved in paths:
            raise ValueError("Two artifact paths resolve to the same file")
        digest = item.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Expected a lowercase SHA-256 digest")
        size = item.get("bytes")
        if type(size) is not int or size < 0:
            raise ValueError("Artifact bytes must be a nonnegative integer")
        h = hashlib.sha256()
        total = 0
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                total += len(chunk)
                h.update(chunk)
        if total != size or h.hexdigest() != digest:
            raise ValueError(f"Artifact changed: {rel}")
        ids.add(artifact_id)
        paths.update((rel, resolved))
    return {"status": "hash_integrity_passed", "artifacts_checked": len(records),
            "scientific_validity_checked": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.manifest), indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Integrity check failed: {exc}\n")


if __name__ == "__main__":
    main()
