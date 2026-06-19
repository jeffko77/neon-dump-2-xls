from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path


def _escape_mermaid_block(source: str) -> str:
    return source.replace("&", "&amp;").replace("<", "&lt;")


def _friendly_table_name(entity: str) -> str:
    return entity.removeprefix("public_").removeprefix("archive_")


def _parse_edge_line(line: str) -> tuple[str, str, str, str]:
    left, label = line.split(":", 1)
    edge_kind = "logical" if ".." in left else "foreign key"
    parts = left.strip().split()
    return parts[0], parts[-1], label.strip(), edge_kind


def _render_relationship_table(edge_lines: list[str]) -> str:
    if not edge_lines:
        return "<p>No relationships in this group.</p>"

    rows: list[str] = []
    for line in edge_lines:
        source, target, label, edge_kind = _parse_edge_line(line.strip())
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(_friendly_table_name(source))}</code></td>"
            f"<td><code>{html.escape(label)}</code></td>"
            f"<td><code>{html.escape(_friendly_table_name(target))}</code></td>"
            f"<td>{html.escape(edge_kind)}</td>"
            "</tr>"
        )

    return (
        '<table class="relationship-table">'
        "<thead><tr><th>From table</th><th>Column(s)</th><th>To table</th><th>Type</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def _render_diagram_sections(sections: list[tuple[str, str]]) -> str:
    blocks: list[str] = []
    for index, (title, source) in enumerate(sections, start=1):
        escaped = _escape_mermaid_block(source)
        safe_title = html.escape(title)
        edge_lines = [line for line in source.splitlines()[1:] if line.strip()]
        table_html = _render_relationship_table(edge_lines)
        blocks.append(
            f"""  <section class="diagram-section">
    <h2>{index}. {safe_title}</h2>
    {table_html}
    <details class="diagram-visual">
      <summary>Show visual diagram</summary>
      <div class="diagram">
        <div class="diagram-inner">
          <div class="mermaid">
{escaped}
          </div>
        </div>
      </div>
    </details>
  </section>"""
        )
    return "\n".join(blocks)


def write_schema_diagram_html(
    output_path: str | Path,
    *,
    mermaid_source: str,
    host: str,
    exported_at: datetime,
    fk_count: int,
    logical_count: int,
    mermaid_sections: list[tuple[str, str]] | None = None,
) -> Path:
    path = Path(output_path)
    sections = mermaid_sections or [("All relationships", mermaid_source)]
    diagram_html = _render_diagram_sections(sections)
    timestamp = html.escape(exported_at.isoformat())
    host_text = html.escape(host)

    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Lax Scheduler Schema Diagram</title>
  <style>
    :root {{
      color-scheme: light dark;
      font-family: system-ui, -apple-system, sans-serif;
      line-height: 1.5;
    }}
    body {{ margin: 1.5rem; max-width: 1100px; }}
    .meta {{ margin-bottom: 1rem; color: #555; }}
    .legend {{ margin: 1rem 0; padding: 0.75rem 1rem; border: 1px solid #ccc; border-radius: 8px; }}
    .diagram-section {{
      margin-bottom: 2.5rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid #ddd;
    }}
    .diagram-section h2 {{
      margin: 0 0 1rem;
      font-size: 1.35rem;
    }}
    .relationship-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 1.05rem;
      margin-bottom: 1rem;
    }}
    .relationship-table th,
    .relationship-table td {{
      border: 1px solid #ccc;
      padding: 0.65rem 0.8rem;
      text-align: left;
      vertical-align: top;
    }}
    .relationship-table th {{
      background: #f3f3f3;
      font-size: 0.95rem;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }}
    @media (prefers-color-scheme: dark) {{
      .relationship-table th {{ background: #222; }}
    }}
    .relationship-table code {{
      font-size: 1em;
      word-break: break-word;
    }}
    .diagram-visual summary {{
      cursor: pointer;
      font-weight: 600;
      margin: 0.5rem 0 0.75rem;
    }}
    .diagram-toolbar {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.5rem;
      margin: 1rem 0;
    }}
    .diagram-toolbar button {{
      font: inherit;
      padding: 0.35rem 0.85rem;
      cursor: pointer;
    }}
    .diagram {{
      overflow: auto;
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 1.25rem;
      min-height: 220px;
      max-height: 70vh;
      background: #fafafa;
    }}
    @media (prefers-color-scheme: dark) {{
      .diagram {{ background: #111; }}
    }}
    .diagram-inner {{
      transform-origin: top left;
      display: inline-block;
      min-width: max-content;
    }}
    .diagram .mermaid svg {{
      display: block;
      max-width: none !important;
      width: auto !important;
      height: auto !important;
    }}
    pre.source {{ white-space: pre-wrap; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>Lax Scheduler Schema Diagram</h1>
  <p class="meta">Exported {timestamp} from <code>{host_text}</code></p>
  <div class="legend">
    <strong>Legend</strong>
    <ul>
      <li><code>foreign key</code> — Postgres FK constraint ({fk_count} in export)</li>
      <li><code>logical</code> — legacy / inferred link from logical_keys.json ({logical_count} edges shown)</li>
    </ul>
    <p>Relationships are grouped by area (Arbiter, Scheduling, Schools, etc.). Tables are the readable view; open “Show visual diagram” if you want the graphic.</p>
  </div>
  <div class="diagram-toolbar" id="diagram-toolbar" hidden>
    <button type="button" id="zoom-out" aria-label="Zoom out">−</button>
    <button type="button" id="zoom-reset" aria-label="Reset zoom">100%</button>
    <button type="button" id="zoom-in" aria-label="Zoom in">+</button>
    <span>Zoom open visual diagrams.</span>
  </div>
{diagram_html}
  <h2>Mermaid source</h2>
  <pre class="source">{html.escape(mermaid_source)}</pre>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';

    const MIN_LABEL_PX = 22;
    const DEFAULT_ZOOM = 1;
    const inners = Array.from(document.querySelectorAll('.diagram-inner'));
    const toolbar = document.getElementById('diagram-toolbar');

    if (inners.length > 0) {{
      toolbar.hidden = false;
      mermaid.initialize({{
        startOnLoad: false,
        securityLevel: 'loose',
        theme: 'base',
        themeVariables: {{
          fontSize: '22px',
          fontFamily: 'system-ui, -apple-system, sans-serif',
        }},
        themeCSS: `
          .er text, .er tspan, .er .entityLabel, .er .relationshipLabel {{
            font-size: ${{MIN_LABEL_PX}}px !important;
          }}
        `,
        er: {{
          useMaxWidth: false,
          layoutDirection: 'TB',
          fontSize: MIN_LABEL_PX,
          minEntityWidth: 220,
          minEntityHeight: 68,
          entityPadding: 20,
          nodeSpacing: 80,
          rankSpacing: 80,
          diagramPadding: 24,
        }},
      }});

      const enhanceSvg = (inner) => {{
        const svg = inner.querySelector('svg');
        if (!svg) return;
        for (const text of svg.querySelectorAll('text, tspan')) {{
          const current = Number.parseFloat(text.getAttribute('font-size') || '0');
          if (!Number.isFinite(current) || current < MIN_LABEL_PX) {{
            text.setAttribute('font-size', String(MIN_LABEL_PX));
          }}
        }}
        const box = svg.getBBox();
        svg.setAttribute('width', String(Math.ceil(box.width)));
        svg.setAttribute('height', String(Math.ceil(box.height)));
      }};

      let zoom = DEFAULT_ZOOM;
      const clamp = (value) => Math.min(4, Math.max(0.75, value));
      const applyZoom = () => {{
        for (const inner of inners) {{
          inner.style.transform = `scale(${{zoom}})`;
        }}
        document.getElementById('zoom-reset').textContent = `${{Math.round(zoom * 100)}}%`;
      }};

      for (const details of document.querySelectorAll('.diagram-visual')) {{
        details.addEventListener('toggle', async () => {{
          if (!details.open || details.dataset.mermaidRendered === 'true') return;
          const node = details.querySelector('.mermaid');
          if (!node) return;
          details.dataset.mermaidRendered = 'true';
          await mermaid.run({{ nodes: [node] }});
          const inner = details.querySelector('.diagram-inner');
          if (inner) enhanceSvg(inner);
          applyZoom();
        }});
      }}

      document.getElementById('zoom-in').addEventListener('click', () => {{
        zoom = clamp(zoom + 0.25);
        applyZoom();
      }});
      document.getElementById('zoom-out').addEventListener('click', () => {{
        zoom = clamp(zoom - 0.25);
        applyZoom();
      }});
      document.getElementById('zoom-reset').addEventListener('click', () => {{
        zoom = DEFAULT_ZOOM;
        applyZoom();
      }});
    }}
  </script>
</body>
</html>
"""
    path.write_text(content, encoding="utf-8")
    return path
