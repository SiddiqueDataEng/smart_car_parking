"""
Data Quality Checks module — Great Expectations style, pure Python.

Usage:
    from src.quality.quality_checks import QualityGate
    gate = QualityGate("silver_fact", df)
    gate.not_null(["transaction_id", "location_id"])
    gate.unique(["transaction_id"])
    gate.value_range("duration_minutes", min_val=1, max_val=1440)
    gate.positive_values("fee_pkr")
    report = gate.run(halt_on_critical=True)
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

import pandas as pd

from src.catalog.logger import get_logger

log = get_logger("quality")

_ROOT = Path(__file__).resolve().parents[2]


class QualityGate:
    def __init__(self, dataset_name: str, df: pd.DataFrame):
        self.dataset_name = dataset_name
        self.df = df
        self._checks: list = []

    # ── Check definitions ────────────────────────────────────────────────────

    def not_null(self, columns: List[str], critical: bool = True):
        """All specified columns must have no nulls."""
        for col in columns:
            self._checks.append({
                "check": "not_null",
                "column": col,
                "critical": critical,
            })
        return self

    def unique(self, columns: List[str], critical: bool = True):
        """Values in each column must be unique."""
        for col in columns:
            self._checks.append({
                "check": "unique",
                "column": col,
                "critical": critical,
            })
        return self

    def value_range(
        self, column: str,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        critical: bool = True,
    ):
        """Numeric column must be within [min_val, max_val]."""
        self._checks.append({
            "check": "value_range",
            "column": column,
            "min_val": min_val,
            "max_val": max_val,
            "critical": critical,
        })
        return self

    def positive_values(self, column: str, critical: bool = True):
        """All values must be > 0."""
        return self.value_range(column, min_val=0.001, critical=critical)

    def referential_integrity(
        self, column: str, reference_set: set, critical: bool = True
    ):
        """Every non-null value in column must exist in reference_set."""
        self._checks.append({
            "check": "referential_integrity",
            "column": column,
            "reference_set": reference_set,
            "critical": critical,
        })
        return self

    def regex_match(self, column: str, pattern: str, critical: bool = False):
        """Non-null values must match the regex pattern."""
        self._checks.append({
            "check": "regex_match",
            "column": column,
            "pattern": pattern,
            "critical": critical,
        })
        return self

    def null_rate_below(self, column: str, threshold: float = 0.05, critical: bool = False):
        """Null rate must be below threshold (e.g. 0.05 = 5%)."""
        self._checks.append({
            "check": "null_rate_below",
            "column": column,
            "threshold": threshold,
            "critical": critical,
        })
        return self

    # ── Execution ─────────────────────────────────────────────────────────────

    def _run_check(self, check: dict) -> dict:
        df = self.df
        col = check.get("column")
        result = {
            "check":    check["check"],
            "column":   col,
            "critical": check["critical"],
            "passed":   False,
            "message":  "",
            "bad_count": 0,
            "bad_samples": [],
        }

        if col and col not in df.columns:
            result["message"] = f"Column '{col}' not found in dataset"
            return result

        try:
            if check["check"] == "not_null":
                bad = df[col].isna()
                result["bad_count"] = int(bad.sum())
                result["passed"]    = result["bad_count"] == 0
                result["message"]   = (
                    f"No nulls" if result["passed"]
                    else f"{result['bad_count']} null values found"
                )
                if result["bad_count"] > 0:
                    result["bad_samples"] = df[bad][col].head(5).tolist()

            elif check["check"] == "unique":
                dupes = df[col].duplicated(keep=False) & df[col].notna()
                result["bad_count"] = int(dupes.sum())
                result["passed"]    = result["bad_count"] == 0
                result["message"]   = (
                    "All values unique" if result["passed"]
                    else f"{result['bad_count']} duplicate values found"
                )
                if result["bad_count"] > 0:
                    result["bad_samples"] = df[dupes][col].head(5).tolist()

            elif check["check"] == "value_range":
                col_data = pd.to_numeric(df[col], errors="coerce")
                bad = pd.Series([False] * len(df))
                if check.get("min_val") is not None:
                    bad = bad | (col_data < check["min_val"])
                if check.get("max_val") is not None:
                    bad = bad | (col_data > check["max_val"])
                result["bad_count"] = int(bad.sum())
                result["passed"]    = result["bad_count"] == 0
                rng_str = f"[{check.get('min_val', '-∞')}, {check.get('max_val', '+∞')}]"
                result["message"]   = (
                    f"All values in range {rng_str}" if result["passed"]
                    else f"{result['bad_count']} values outside {rng_str}"
                )
                if result["bad_count"] > 0:
                    result["bad_samples"] = col_data[bad].head(5).tolist()

            elif check["check"] == "referential_integrity":
                ref = check["reference_set"]
                bad = df[col].notna() & ~df[col].isin(ref)
                result["bad_count"] = int(bad.sum())
                result["passed"]    = result["bad_count"] == 0
                result["message"]   = (
                    "All references valid" if result["passed"]
                    else f"{result['bad_count']} invalid references"
                )
                if result["bad_count"] > 0:
                    result["bad_samples"] = df[bad][col].head(5).tolist()

            elif check["check"] == "regex_match":
                import re
                non_null = df[col].dropna()
                bad_mask = ~non_null.str.match(check["pattern"])
                result["bad_count"] = int(bad_mask.sum())
                result["passed"]    = result["bad_count"] == 0
                result["message"]   = (
                    "All values match pattern" if result["passed"]
                    else f"{result['bad_count']} values don't match '{check['pattern']}'"
                )
                if result["bad_count"] > 0:
                    result["bad_samples"] = non_null[bad_mask].head(5).tolist()

            elif check["check"] == "null_rate_below":
                null_rate = df[col].isna().mean()
                result["bad_count"] = int(df[col].isna().sum())
                result["passed"]    = null_rate <= check["threshold"]
                result["message"]   = (
                    f"Null rate {null_rate:.1%} ≤ threshold {check['threshold']:.1%}"
                    if result["passed"]
                    else f"Null rate {null_rate:.1%} exceeds threshold {check['threshold']:.1%}"
                )

        except Exception as e:
            result["message"] = f"Check error: {e}"

        return result

    def run(self, halt_on_critical: bool = True) -> dict:
        """Run all registered checks and return a quality report dict."""
        results = [self._run_check(c) for c in self._checks]

        passed = [r for r in results if r["passed"]]
        failed = [r for r in results if not r["passed"]]
        critical_failures = [r for r in failed if r["critical"]]

        report = {
            "dataset":    self.dataset_name,
            "run_time":   datetime.now().isoformat(),
            "total_rows": len(self.df),
            "checks_total":   len(results),
            "checks_passed":  len(passed),
            "checks_failed":  len(failed),
            "critical_failures": len(critical_failures),
            "overall_pass": len(critical_failures) == 0,
            "results":     results,
        }

        # Save report
        report_dir = _ROOT / "data" / "quality_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = report_dir / f"{self.dataset_name}_{ts}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        # Log summary
        status = "✅ PASS" if report["overall_pass"] else "❌ FAIL"
        log.info(
            "Quality report [%s] %s — %d/%d checks passed, %d critical failures",
            self.dataset_name, status,
            report["checks_passed"], report["checks_total"],
            report["critical_failures"],
        )
        for r in failed:
            sev = "CRITICAL" if r["critical"] else "WARNING"
            log.warning(
                "  [%s] %s.%s → %s",
                sev, self.dataset_name, r["column"], r["message"],
            )

        if halt_on_critical and critical_failures:
            raise ValueError(
                f"Quality gate FAILED for '{self.dataset_name}': "
                f"{len(critical_failures)} critical check(s) failed. "
                f"See {report_path}"
            )

        print(f"\n{'='*60}")
        print(f"Quality Report: {self.dataset_name}")
        print(f"{'='*60}")
        print(f"  Rows:    {report['total_rows']:,}")
        print(f"  Checks:  {report['checks_passed']}/{report['checks_total']} passed")
        print(f"  Status:  {status}")
        if failed:
            print(f"\n  Failed checks:")
            for r in failed:
                sev = "CRITICAL" if r["critical"] else "WARNING "
                print(f"    [{sev}] {r['column']}: {r['message']}")
        print(f"  Report saved → {report_path.name}")
        print(f"{'='*60}\n")

        return report
