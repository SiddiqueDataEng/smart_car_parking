"""
Data Catalog & Lineage Tracker for SMART Parking Solutions.

catalog.json  — dataset registry (name, layer, schema, row count, last updated, sources)
lineage.json  — DAG of dataset provenance

CLI:
    python src/catalog/catalog.py --show
    python src/catalog/catalog.py --lineage
"""
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.catalog.logger import get_logger

log = get_logger("catalog")

_ROOT = Path(__file__).resolve().parents[2]
_CATALOG_PATH = _ROOT / "data" / "catalog.json"
_LINEAGE_PATH = _ROOT / "data" / "lineage.json"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


# ── Public API ────────────────────────────────────────────────────────────────

def register_dataset(
    name: str,
    layer: str,
    file_path: str,
    row_count: int,
    schema: Dict[str, str],
    source_datasets: Optional[List[str]] = None,
    transformations: Optional[List[str]] = None,
    description: str = "",
):
    """Register or update a dataset entry in the catalog."""
    catalog = _load_json(_CATALOG_PATH)

    catalog[name] = {
        "name":             name,
        "layer":            layer,
        "file_path":        file_path,
        "row_count":        row_count,
        "schema":           schema,
        "source_datasets":  source_datasets or [],
        "transformations":  transformations or [],
        "description":      description,
        "last_updated":     datetime.now().isoformat(),
    }
    _save_json(_CATALOG_PATH, catalog)
    log.info("Catalog: registered '%s' (%s, %d rows)", name, layer, row_count)

    # Update lineage DAG
    if source_datasets:
        lineage = _load_json(_LINEAGE_PATH)
        lineage[name] = source_datasets
        _save_json(_LINEAGE_PATH, lineage)
        log.info("Lineage: %s ← %s", name, source_datasets)


def register_from_parquet(
    parquet_path: Path,
    name: str,
    layer: str,
    source_datasets: Optional[List[str]] = None,
    transformations: Optional[List[str]] = None,
    description: str = "",
):
    """Convenience wrapper that reads a Parquet file and registers it."""
    import pandas as pd
    df = pd.read_parquet(parquet_path)
    schema = {col: str(dtype) for col, dtype in df.dtypes.items()}
    register_dataset(
        name=name,
        layer=layer,
        file_path=str(parquet_path.resolve().relative_to(_ROOT)),
        row_count=len(df),
        schema=schema,
        source_datasets=source_datasets,
        transformations=transformations,
        description=description,
    )


def get_catalog() -> dict:
    return _load_json(_CATALOG_PATH)


def get_lineage() -> dict:
    return _load_json(_LINEAGE_PATH)


def check_orphans() -> List[str]:
    """Return dataset names that appear as sources but have no own entry."""
    catalog  = get_catalog()
    lineage  = get_lineage()
    all_sources = {src for srcs in lineage.values() for src in srcs}
    orphans = [s for s in all_sources if s not in catalog]
    return orphans


# ── CLI ───────────────────────────────────────────────────────────────────────

def _show_catalog():
    catalog = get_catalog()
    if not catalog:
        print("Catalog is empty.")
        return

    header = f"{'Dataset':<40} {'Layer':<12} {'Rows':>10} {'Last Updated':<22} {'Sources'}"
    print("=" * 110)
    print("  SMART Parking Solutions — Data Catalog")
    print("=" * 110)
    print(header)
    print("-" * 110)

    layers_order = ["Bronze", "Silver", "Gold", "Platinum", "ML"]
    all_datasets = list(catalog.values())
    all_datasets.sort(key=lambda d: (
        layers_order.index(d["layer"]) if d["layer"] in layers_order else 99,
        d["name"],
    ))

    for entry in all_datasets:
        sources = ", ".join(entry.get("source_datasets", [])) or "—"
        updated = entry["last_updated"][:19]
        print(f"  {entry['name']:<38} {entry['layer']:<12} {entry['row_count']:>10,} "
              f"  {updated:<22} {sources}")

    print("=" * 110)
    print(f"  Total: {len(catalog)} datasets")
    orphans = check_orphans()
    if orphans:
        print(f"  ⚠  Orphan sources: {orphans}")
    else:
        print("  ✓  No orphan nodes in lineage graph")
    print("=" * 110)


def _show_lineage():
    lineage = get_lineage()
    if not lineage:
        print("Lineage graph is empty.")
        return

    print("=" * 80)
    print("  SMART Parking Solutions — Lineage DAG")
    print("=" * 80)
    for target, sources in sorted(lineage.items()):
        print(f"  {' + '.join(sources)}")
        print(f"    └─► {target}")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SMART Parking Data Catalog CLI")
    parser.add_argument("--show",    action="store_true", help="Show full catalog table")
    parser.add_argument("--lineage", action="store_true", help="Show lineage DAG")
    args = parser.parse_args()

    if args.lineage:
        _show_lineage()
    else:
        _show_catalog()
