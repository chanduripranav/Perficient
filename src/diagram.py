"""ETL + AI extension architecture diagram (Mermaid), styled to match the team's ETL chart.

The diagram is written to static/architecture.html and embedded with st.iframe, so it is
served from the app's own origin and Mermaid loads from static/ (works offline).
"""
import json
from pathlib import Path

ARCHITECTURE = """---
config:
  flowchart:
    curve: step
    nodeSpacing: 40
    rankSpacing: 48
    padding: 16
---
flowchart TB
    subgraph ETL["ETL pipeline"]
        direction LR
        A["🌐 Data Source A"] --> S
        B["🌐 Data Source B"] --> S
        C["🌐 Data Source C"] --> S
        S["📥 Web Scrape<br>and Download"] --> E["🧹 Extract,<br>Clean, Transform"]
        E --> J["🔗 Join &<br>Combine"]
    end

    ETL --> DB[("🗄️ Central<br>Database")]
    DB <-->|"SQL query ⇄ relevant data"| AIX

    subgraph AIX["AI extension"]
        direction LR
        U["👤 User asks<br>a question"] --> AI["🤖 AI Assistant<br>(Claude)"]
        AI -->|updates| D["📊 Dashboard"]
        AI -->|updates| W["🌐 Website"]
        AI -->|updates| M["🗺️ Map"]
    end

    classDef source fill:#F5F7FA,stroke:#8B95A5,stroke-width:2px,color:#1F2937
    classDef scrape fill:#FEF3EE,stroke:#EE8A63,stroke-width:2px,color:#1F2937
    classDef process fill:#FEF8EA,stroke:#E5A65B,stroke-width:2px,color:#1F2937
    classDef store fill:#EBFBF4,stroke:#3FB68B,stroke-width:2px,color:#17694B
    classDef group fill:#FFFFFF,stroke:#D1D5DB,stroke-width:1px,stroke-dasharray:5 4,color:#6B7280
    class A,B,C,U,D,W,M source
    class S,AI scrape
    class E,J process
    class DB store
    class ETL,AIX group
    linkStyle default interpolate step stroke:#111111,stroke-width:2px
"""

FONT = "https://fonts.googleapis.com/css2?family=Recursive:slnt,wght,CASL,CRSV,MONO@-15..0,300..1000,0..1,0..1,0..1&display=swap"

STATIC = Path(__file__).resolve().parents[1] / "static"
PAGE_PATH = "/app/static/architecture.html"


def page_html(code: str = ARCHITECTURE) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="{FONT}">
<style>
html,body{{margin:0;height:100%;background:#FFFFFF;overflow:hidden;}}
#out{{height:100vh;display:block;}}
#out svg{{width:100%!important;height:100vh!important;max-width:none!important;display:block;}}
.node rect,.node path,.node polygon{{filter:drop-shadow(4px 5px 0 rgba(17,24,39,.08));}}
.cluster-label,.cluster-label span{{font-weight:600;}}
</style></head><body><div id="out"></div>
<script>
const CODE = {json.dumps(code)};
let done = false;
async function draw() {{
  if (done || document.body.clientWidth === 0) return;   // wait until the tab is visible
  done = true;
  mermaid.initialize({{ startOnLoad: false, theme: "base", securityLevel: "loose",
    themeVariables: {{ fontFamily: "'Recursive', ui-monospace, Menlo, monospace", fontSize: "16px",
                       lineColor: "#111111", primaryTextColor: "#1F2937", edgeLabelBackground: "#FFFFFF" }},
    flowchart: {{ htmlLabels: true, useMaxWidth: false, curve: "step" }} }});
  try {{ await document.fonts.ready; }} catch (e) {{}}
  const {{ svg }} = await mermaid.render("arch", CODE);
  document.getElementById("out").innerHTML = svg;
}}
function start() {{
  new ResizeObserver(draw).observe(document.body);
  draw();
}}
function load(src, onFail) {{
  const s = document.createElement("script"); s.src = src; s.onload = start; s.onerror = onFail;
  document.head.appendChild(s);
}}
load("/app/static/mermaid.min.js",
     () => load("https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js", () => {{}}));
</script></body></html>"""


def write_page() -> str:
    """Write static/architecture.html if it changed; return the URL path to embed."""
    STATIC.mkdir(exist_ok=True)
    target = STATIC / "architecture.html"
    content = page_html()
    if not target.exists() or target.read_text() != content:
        target.write_text(content)
    return PAGE_PATH
