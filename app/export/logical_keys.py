from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.connection import app_dir


@dataclass(frozen=True)
class LogicalEdge:
    source_schema: str
    source_table: str
    source_column: str
    target_schema: str
    target_table: str
    target_column: str
    edge_type: str
    note: str


def logical_keys_path() -> Path:
    candidates = [
        app_dir() / "data" / "logical_keys.json",
        app_dir() / "logical_keys.json",
        Path(__file__).resolve().parent.parent.parent / "data" / "logical_keys.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[-1]


def load_logical_keys_config() -> dict[str, Any]:
    path = logical_keys_path()
    if not path.exists():
        return {"relationships": [], "column_patterns": [], "dimensions": []}
    return json.loads(path.read_text(encoding="utf-8"))


def logical_key_rows(config: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for pattern in config.get("column_patterns", []):
        rows.append(
            [
                "(pattern)",
                pattern.get("column"),
                pattern.get("target_schema"),
                pattern.get("target_table"),
                pattern.get("target_column"),
                "pattern",
                pattern.get("note", ""),
            ]
        )
    for rel in config.get("relationships", []):
        rows.append(
            [
                rel.get("source_schema"),
                rel.get("source_table"),
                rel.get("source_column"),
                rel.get("target_schema"),
                rel.get("target_table"),
                rel.get("target_column"),
                "logical",
                rel.get("note", ""),
            ]
        )
    return rows


def explicit_logical_edges(config: dict[str, Any]) -> list[LogicalEdge]:
    edges: list[LogicalEdge] = []
    for rel in config.get("relationships", []):
        edges.append(
            LogicalEdge(
                source_schema=str(rel["source_schema"]),
                source_table=str(rel["source_table"]),
                source_column=str(rel["source_column"]),
                target_schema=str(rel["target_schema"]),
                target_table=str(rel["target_table"]),
                target_column=str(rel["target_column"]),
                edge_type="logical",
                note=str(rel.get("note", "")),
            )
        )
    return edges


def mermaid_entity_name(schema_name: str, table_name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]", "_", f"{schema_name}_{table_name}")
    if name and name[0].isdigit():
        name = f"t_{name}"
    return name


def sanitize_mermaid_label(text: str, *, max_len: int = 48) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 _\-]", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "link"
    if len(cleaned) > max_len:
        return cleaned[: max_len - 3].rstrip() + "..."
    return cleaned


def _collect_mermaid_edge_lines(
    foreign_keys: list[list[Any]],
    logical_edges: list[LogicalEdge],
) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()

    fk_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in foreign_keys:
        source_schema, source_table, column, target_schema, target_table, _, _ = row
        source = mermaid_entity_name(source_schema, source_table)
        target = mermaid_entity_name(target_schema, target_table)
        fk_groups[(source, target)].append(str(column))

    for (source, target), columns in sorted(fk_groups.items()):
        label = sanitize_mermaid_label(", ".join(dict.fromkeys(columns)))
        edge = f"    {source} }}o--|| {target} : {label}"
        if edge not in seen:
            lines.append(edge)
            seen.add(edge)

    logical_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for edge in logical_edges:
        source = mermaid_entity_name(edge.source_schema, edge.source_table)
        target = mermaid_entity_name(edge.target_schema, edge.target_table)
        logical_groups[(source, target)].append(edge.source_column)

    for (source, target), columns in sorted(logical_groups.items()):
        pair_key = (source, target)
        if pair_key in fk_groups:
            continue
        label = sanitize_mermaid_label(", ".join(dict.fromkeys(columns)))
        mermaid_edge = f"    {source} }}o..|| {target} : {label}"
        if mermaid_edge not in seen:
            lines.append(mermaid_edge)
            seen.add(mermaid_edge)

    return lines


def _parse_mermaid_edge_line(line: str) -> tuple[str, str]:
    left, _ = line.split(":", 1)
    parts = left.strip().split()
    return parts[0], parts[-1]


def _table_domain(entity: str) -> str:
    name = entity.removeprefix("public_").removeprefix("archive_")
    if name.startswith("arbiter_"):
        return "arbiter"
    if name.startswith("conflict_"):
        return "conflict"
    if name.startswith("tblschedule"):
        return "schedule"
    if name.startswith("tblschool"):
        return "schools"
    if name.startswith("tblasset"):
        return "assets"
    if name.startswith("tbl"):
        return "tables"
    return "other"


DOMAIN_TITLES = {
    "arbiter": "Arbiter integration",
    "conflict": "Conflict forms",
    "schedule": "Scheduling",
    "schools": "Schools",
    "assets": "Assets and reservations",
    "tables": "Other core tables",
    "other": "Other relationships",
}


def _domain_edge_groups(edge_lines: list[str]) -> list[tuple[str, list[str]]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for line in edge_lines:
        source, _ = _parse_mermaid_edge_line(line)
        groups[_table_domain(source)].append(line)

    ordered_domains = sorted(groups, key=lambda domain: DOMAIN_TITLES.get(domain, domain))
    return [
        (DOMAIN_TITLES.get(domain, domain.title()), groups[domain])
        for domain in ordered_domains
    ]


def _split_large_group(title: str, edge_lines: list[str], *, max_nodes: int = 10) -> list[tuple[str, list[str]]]:
    nodes = {
        node
        for line in edge_lines
        for node in _parse_mermaid_edge_line(line)
    }
    if len(nodes) <= max_nodes:
        return [(title, edge_lines)]

    subgroups: dict[str, list[str]] = defaultdict(list)
    for line in edge_lines:
        source, _ = _parse_mermaid_edge_line(line)
        name = source.removeprefix("public_").removeprefix("archive_")
        key = name.split("_", 1)[0] if "_" in name else name
        subgroups[key].append(line)

    if len(subgroups) <= 1:
        return [(title, edge_lines)]

    chunks: list[tuple[str, list[str]]] = []
    for key in sorted(subgroups):
        chunk_title = f"{title} ({key})"
        chunks.extend(_split_large_group(chunk_title, subgroups[key], max_nodes=max_nodes))
    return chunks


def build_mermaid_er(
    foreign_keys: list[list[Any]],
    logical_edges: list[LogicalEdge],
) -> str:
    edge_lines = _collect_mermaid_edge_lines(foreign_keys, logical_edges)
    return "erDiagram\n" + "\n".join(edge_lines)


def build_mermaid_er_sections(
    foreign_keys: list[list[Any]],
    logical_edges: list[LogicalEdge],
) -> list[tuple[str, str]]:
    edge_lines = _collect_mermaid_edge_lines(foreign_keys, logical_edges)
    if not edge_lines:
        return [("Relationships", "erDiagram")]

    sections: list[tuple[str, str]] = []
    for title, group in _domain_edge_groups(edge_lines):
        for chunk_title, chunk_lines in _split_large_group(title, group):
            sections.append((chunk_title, "erDiagram\n" + "\n".join(chunk_lines)))
    return sections
