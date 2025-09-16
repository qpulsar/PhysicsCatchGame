"""Migration script: make sprite regions and media metadata global (no per-game dependency).

Operations:
- Sprite regions: deduplicate by (image_path, name) and set survivor's game_id=0. Delete duplicates.
- Media metadata: convert assets/metadata.json values to {"description": str} structure.

Run: venv/bin/python scripts/migrate_to_global.py
"""
from __future__ import annotations

import os
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "game_data.db"
ASSETS_ROOT = PROJECT_ROOT / "assets"
METADATA_PATH = ASSETS_ROOT / "metadata.json"


def migrate_sprite_regions_to_global(db_path: Path) -> int:
    """Deduplicate sprite_regions by (image_path, name) and set survivor game_id=0.

    Returns the number of affected rows (updates + deletes).
    """
    if not db_path.exists():
        print(f"[sprite] DB not found: {db_path}")
        return 0
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    affected = 0
    try:
        cur.execute("SELECT id, game_id, image_path, name, x, y, width, height FROM sprite_regions")
        rows = cur.fetchall()
        groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
        for r in rows:
            key = (r["image_path"], r["name"])
            groups.setdefault(key, []).append(r)
        conn.execute("BEGIN IMMEDIATE")
        for key, lst in groups.items():
            # Prefer an existing global (game_id=0) if present; else pick the smallest id as survivor
            survivor = None
            globals_ = [r for r in lst if int(r["game_id"]) == 0]
            if globals_:
                survivor = min(globals_, key=lambda r: int(r["id"]))
            else:
                survivor = min(lst, key=lambda r: int(r["id"]))
            # Ensure survivor is global
            if int(survivor["game_id"]) != 0:
                cur.execute("UPDATE sprite_regions SET game_id = 0 WHERE id = ?", (int(survivor["id"]),))
                affected += cur.rowcount or 0
            # Delete all others with same (image_path, name)
            for r in lst:
                if int(r["id"]) == int(survivor["id"]):
                    continue
                cur.execute("DELETE FROM sprite_regions WHERE id = ?", (int(r["id"]),))
                affected += cur.rowcount or 0
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"[sprite] Affected rows: {affected}")
    return affected


def migrate_metadata_to_global(meta_path: Path) -> int:
    """Convert per-game description mapping to a single global description key.

    Returns the number of entries updated.
    """
    if not meta_path.exists():
        print(f"[media] metadata.json not found: {meta_path}")
        return 0
    try:
        with meta_path.open("r", encoding="utf-8") as f:
            data = json.load(f) or {}
        changed = 0
        for rel, mapping in list(data.items()):
            if not isinstance(mapping, dict):
                continue
            if "description" in mapping and isinstance(mapping["description"], str):
                continue
            # collect non-empty game_* descriptions
            desc = ""
            for k, v in mapping.items():
                if k.startswith("game_") and isinstance(v, str) and v.strip():
                    desc = v.strip()
                    break
            new_map = {"description": desc}
            if mapping != new_map:
                data[rel] = new_map
                changed += 1
        if changed:
            with meta_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[media] Updated entries: {changed}")
        return changed
    except Exception as e:
        print(f"[media] Failed: {e}")
        return 0


def main() -> None:
    print("-- migrate to global start --")
    migrate_sprite_regions_to_global(DB_PATH)
    migrate_metadata_to_global(METADATA_PATH)
    print("-- migrate to global done --")


if __name__ == "__main__":
    main()
