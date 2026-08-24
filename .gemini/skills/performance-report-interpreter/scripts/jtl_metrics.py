#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    fraction = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * fraction


def _clean_url(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    # Protect against accidentally pasted Markdown links.
    if raw.startswith("[") and "](" in raw and raw.endswith(")"):
        raw = raw.split("](", 1)[1][:-1]
    return raw


class JtlMetricsAnalyzer:
    """Calcula métricas y alcance HTTP genéricos desde JTL CSV o XML."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _rows_csv(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self.path.open(encoding="utf-8", errors="replace", newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    elapsed = float(row.get("elapsed") or 0)
                except ValueError:
                    elapsed = 0.0
                try:
                    ts = float(row.get("timeStamp") or 0)
                except ValueError:
                    ts = 0.0
                rows.append({
                    "label": row.get("label") or "UNKNOWN",
                    "success": str(row.get("success", "")).lower() == "true",
                    "elapsed": elapsed,
                    "timestamp": ts,
                    "url": _clean_url(row.get("URL") or row.get("url")),
                    "method": str(row.get("method") or "").strip().upper() or None,
                })
        return rows

    def _rows_xml(self) -> list[dict[str, Any]]:
        root = ET.parse(self.path).getroot()
        rows: list[dict[str, Any]] = []
        for node in root.iter():
            if node.tag not in {"httpSample", "sample"}:
                continue
            url = None
            method = None
            for child in list(node):
                if child.tag == "java.net.URL" and child.text:
                    url = _clean_url(child.text)
                elif child.tag == "method" and child.text:
                    method = child.text.strip().upper()
            rows.append({
                "label": node.attrib.get("lb", "UNKNOWN"),
                "success": node.attrib.get("s", "false").lower() == "true",
                "elapsed": float(node.attrib.get("t", "0") or 0),
                "timestamp": float(node.attrib.get("ts", "0") or 0),
                "url": url,
                "method": method,
            })
        return rows

    def rows(self) -> list[dict[str, Any]]:
        head = self.path.read_bytes()[:200].lstrip()
        if head.startswith(b"<?xml") or head.startswith(b"<testResults"):
            return self._rows_xml()
        return self._rows_csv()

    @staticmethod
    def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        count = len(rows)
        success = sum(1 for row in rows if row["success"])
        failed = count - success
        elapsed = [float(row["elapsed"]) for row in rows]
        timestamps = [float(row["timestamp"]) for row in rows if row["timestamp"] > 0]
        if timestamps:
            start = min(timestamps)
            end = max(
                float(row["timestamp"]) + float(row["elapsed"])
                for row in rows
                if float(row["timestamp"]) > 0
            )
            span_s = max((end - start) / 1000.0, 0.001)
        else:
            span_s = 0.0
        return {
            "requests": count,
            "successful": success,
            "failed": failed,
            "success_rate": (success / count * 100.0) if count else None,
            "error_rate": (failed / count * 100.0) if count else None,
            "throughput": (count / span_s) if span_s > 0 else None,
            "average_ms": (sum(elapsed) / count) if count else None,
            "p50_ms": percentile(elapsed, 0.50),
            "p90_ms": percentile(elapsed, 0.90),
            "p95_ms": percentile(elapsed, 0.95),
            "p99_ms": percentile(elapsed, 0.99),
            "max_ms": max(elapsed) if elapsed else None,
        }

    @staticmethod
    def _scope(rows: list[dict[str, Any]]) -> dict[str, Any]:
        origins: set[str] = set()
        hosts: set[str] = set()
        methods: set[str] = set()
        for row in rows:
            url = row.get("url")
            if url:
                try:
                    parsed = urlsplit(str(url))
                    if parsed.scheme and parsed.netloc:
                        origins.add(f"{parsed.scheme}://{parsed.netloc}")
                        hosts.add(parsed.netloc)
                except ValueError:
                    pass
            if row.get("method"):
                methods.add(str(row["method"]))
        if len(origins) == 1:
            display_target = next(iter(origins))
        elif len(origins) > 1:
            ordered = sorted(origins)
            preview = ", ".join(ordered[:3])
            suffix = "" if len(ordered) <= 3 else f" +{len(ordered) - 3} más"
            display_target = f"Flujo multi-servicio ({len(ordered)} destinos): {preview}{suffix}"
        elif len(hosts) == 1:
            display_target = next(iter(hosts))
        else:
            display_target = "Aplicación / servicio bajo prueba"
        return {
            "target": display_target,
            "origins": sorted(origins),
            "hosts": sorted(hosts),
            "methods": sorted(methods),
        }

    def analyze(self) -> dict[str, Any]:
        rows = self.rows()
        global_metrics = self._summary(rows)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row["label"])].append(row)
        transactions = []
        for label, items in grouped.items():
            item = self._summary(items)
            item["label"] = label
            item["status"] = "PASS" if (item.get("failed") or 0) == 0 else "FAIL"
            urls = sorted({str(row.get("url")) for row in items if row.get("url")})
            methods = sorted({str(row.get("method")) for row in items if row.get("method")})
            item["urls"] = urls
            item["methods"] = methods
            transactions.append(item)
        transactions.sort(key=lambda item: item["label"].lower())
        return {
            "metrics": global_metrics,
            "transactions": transactions,
            "scope": self._scope(rows),
        }
