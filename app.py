import base64
import html as htmllib
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.ai import MODEL, PROCEDURES as AI_PROCEDURES, claude_intent, extract_intent, make_client, stream_grounded_answer
from src.data import CONTRACT_COLUMNS, PROCEDURES, add_live_records, load_records, query_records
from src.diagram import write_page
from src.engine import resolve, run_acceptance
from src.value import (CMS_MAX_ANNUAL_PENALTY, CMS_MAX_DAILY_PENALTY, CMS_PT_URL, RRH_MONTHLY_CALL_SAVINGS,
                       RRH_SCHEDULING_LIFT, fmt_big)

st.set_page_config(page_title="CareConnect · Perficient", page_icon=":material/local_hospital:", layout="wide",
                   initial_sidebar_state="expanded")

NAVY, BLUE, LIGHT, GRAY, GREEN = "#0B2545", "#1D4ED8", "#BFDBFE", "#6B7280", "#15803D"
CMS_NHE = "https://www.cms.gov/data-research/statistics-trends-and-reports/national-health-expenditure-data"
RRH = "https://www.perficient.com/outcomes/rochester-regional-health"
CONCIERGE = "https://www.perficient.com/industries/healthcare-life-sciences/ai-concierge"
PW_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC12097484/"
SHORT = {"73721": "Knee MRI", "70551": "Brain MRI", "74176": "Abdomen/pelvis CT"}


def html(markup: str) -> None:
    """Render HTML without Markdown turning indented lines into code blocks."""
    st.markdown(" ".join(line.strip() for line in markup.splitlines() if line.strip()), unsafe_allow_html=True)


ASSETS = Path(__file__).parent / "assets"


@st.cache_data
def img(name: str) -> str:
    """Embed a local photo as a data URI so the demo works offline."""
    return "data:image/jpeg;base64," + base64.b64encode((ASSETS / f"{name}.jpg").read_bytes()).decode()


def icon(paths: str) -> str:
    return (f'<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">{paths}</svg>')


ICON_CHART = icon('<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>')
ICON_PULSE = icon('<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>')
ICON_DOLLAR = icon('<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>')
ICON_TREND = icon('<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>')


def banner(photo: str, label: str, title: str, text: str) -> None:
    html(f"""<div class="banner" style="background-image:linear-gradient(90deg,rgba(11,37,69,.92) 0%,rgba(11,37,69,.72) 55%,rgba(11,37,69,.25) 100%),url('{img(photo)}')">
<div class="label">{label}</div><h2>{title}</h2><p>{text}</p></div>""")


def esc(value) -> str:
    return htmllib.escape("" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value))


# ----------------------------------------------------------------------------- styles
html("""
<style>
html,body,[class*="css"]{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;}
.block-container{max-width:1320px;padding:3.2rem 2rem 3rem;}
h1,h2,h3,h4{color:#0B2545;}
h4{font-size:17px!important;}
.label{font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:#6B7280;}
.hero{display:grid;grid-template-columns:1fr;gap:28px;align-items:center;padding:34px 38px;border-radius:14px;color:#fff;background-size:cover;background-position:center;box-shadow:0 10px 30px rgba(11,37,69,.18);}
.hero .label{color:#BFDBFE;}
.hero .team{font-size:14px;font-weight:600;color:#FFFFFF;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid rgba(255,255,255,.22);display:inline-block;}
.hero h1{font-size:30px;font-weight:700;line-height:1.2;margin:8px 0 10px;color:#fff;padding:0;}
.hero p{font-size:15px;line-height:1.6;color:#E2E8F0;margin:0;max-width:600px;}
.chips{margin-top:16px;display:flex;flex-wrap:wrap;gap:8px;}
.chip{font-size:12.5px;padding:5px 11px;border-radius:999px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.28);color:#fff;}
.chip.on{background:#DCFCE7;border-color:#DCFCE7;color:#14532D;font-weight:600;}
.ranges{background:#fff;border-radius:12px;padding:16px 18px;color:#111827;box-shadow:0 8px 24px rgba(0,0,0,.18);}
.ranges .row{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid #F1F5F9;font-size:13.5px;color:#374151;}
.ranges .row:last-child{border-bottom:0;}
.ranges .label{color:#6B7280;}
.ranges b{color:#0B2545;white-space:nowrap;}
.box{border:1px solid #E5E7EB;border-radius:10px;padding:16px 18px;background:#FFFFFF;}
.box.muted{background:#F8FAFC;}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0 10px;}
.kpi{display:flex;gap:14px;align-items:flex-start;border:1px solid #E5E7EB;border-radius:12px;padding:16px;background:#FFFFFF;box-shadow:0 1px 2px rgba(16,24,40,.04);}
.ico{flex:none;width:40px;height:40px;border-radius:10px;display:grid;place-items:center;}
.ico.blue{background:#DBEAFE;color:#1D4ED8;} .ico.teal{background:#CCFBF1;color:#0F766E;} .ico.amber{background:#FEF3C7;color:#B45309;} .ico.navy{background:#E0E7FF;color:#0B2545;}
.kpi .v{font-size:24px;font-weight:700;color:#0B2545;margin:2px 0 2px;line-height:1.2;}
.kpi .v.f{font-size:15px;line-height:1.35;margin:4px 0 6px;}
.kpi .l{font-size:12.5px;color:#6B7280;line-height:1.4;}
.banner{border-radius:12px;padding:26px 30px;margin-bottom:16px;color:#fff;background-size:cover;background-position:center;}
.banner .label{color:#BFDBFE;}
.banner h2{color:#fff;font-size:22px;margin:6px 0 6px;padding:0;}
.banner p{color:#E2E8F0;font-size:14.5px;margin:0;max-width:760px;line-height:1.55;}
.photo{border-radius:12px;overflow:hidden;border:1px solid #E5E7EB;background:#fff;margin-bottom:14px;}
.photo img{width:100%;height:150px;object-fit:cover;display:block;}
.photo .body{padding:12px 16px;font-size:13.5px;color:#374151;line-height:1.5;}
.photo .body b{color:#0B2545;}
.rates{margin-top:8px;border:1px solid #E5E7EB;border-radius:10px;overflow:hidden;}
.rate{display:grid;grid-template-columns:28px 1fr auto;gap:12px;align-items:center;padding:10px 14px;border-bottom:1px solid #F3F4F6;background:#FFFFFF;}
.rate:last-child{border-bottom:0;}
.rate.best{background:#F0FDF4;}
.rank{font-weight:600;color:#6B7280;font-size:13px;}
.rname{font-weight:600;color:#111827;font-size:14px;}
.rsub{font-size:12px;color:#6B7280;margin-top:2px;}
.rsub a{color:#1D4ED8;}
.track{height:4px;background:#F3F4F6;border-radius:2px;margin-top:6px;}
.track span{display:block;height:100%;border-radius:2px;background:#93C5FD;}
.best .track span{background:#15803D;}
.price{font-size:17px;font-weight:700;color:#111827;}
.tag{display:inline-block;font-size:11px;font-weight:600;padding:1px 6px;border-radius:4px;margin-left:6px;border:1px solid #D1D5DB;color:#4B5563;}
.tag.low{border-color:#86EFAC;color:#15803D;background:#FFFFFF;}
.note{margin-top:8px;padding:10px 14px;border-radius:8px;background:#EFF6FF;border:1px solid #DBEAFE;font-size:13.5px;color:#1E3A8A;}
.problem p{margin:6px 0 0;font-size:13.5px;color:#374151;line-height:1.55;}
.problem ul{margin:6px 0 0;padding-left:18px;font-size:13.5px;color:#374151;line-height:1.6;}
.problem b{color:#0B2545;}
.steps .step{display:flex;gap:12px;padding:9px 0;border-bottom:1px solid #F3F4F6;font-size:13.5px;color:#374151;}
.steps .step:last-child{border-bottom:0;}
.steps .n{flex:none;width:22px;height:22px;border-radius:50%;background:#DBEAFE;color:#1D4ED8;font-weight:700;display:grid;place-items:center;font-size:12px;}
.steps code{background:#F3F4F6;color:#1F2937;padding:1px 5px;border-radius:4px;font-size:12px;}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}
.card{border:1px solid #E5E7EB;border-radius:12px;padding:18px;background:#FFFFFF;height:100%;box-shadow:0 1px 2px rgba(16,24,40,.04);}
.card .big{font-size:30px;font-weight:700;color:#0B2545;margin:6px 0;}
.card .cap{color:#4B5563;font-size:13px;line-height:1.5;}
.card h4{margin:0 0 6px;font-size:16px;}
.card p{margin:0;color:#4B5563;font-size:13.5px;line-height:1.5;}
.card .out{margin-top:10px;font-size:13px;font-weight:600;color:#0F766E;}
.pcard{padding:0;overflow:hidden;}
.pcard img{width:100%;height:130px;object-fit:cover;display:block;}
.pcard .body{padding:14px 16px 16px;}
.flow{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;}
.flow .card{border-top:3px solid #1D4ED8;}
.flow .card h4{font-size:14px;margin-top:4px;}
.flow .card p{font-size:12.5px;}
.road{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;}
.road .card{border-top:3px solid #0F766E;}
.road ul{margin:6px 0 0;padding-left:18px;color:#374151;font-size:13px;line-height:1.6;}
.src{font-size:11.5px;color:#6B7280;margin-top:6px;line-height:1.45;}
.src a,.card a{color:#1D4ED8;}
.calc{font-size:12px;color:#1F2937;background:#F8FAFC;border:1px solid #E5E7EB;border-radius:8px;padding:8px 10px;margin-top:10px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;line-height:1.5;}
.fine{font-size:12px;color:#6B7280;line-height:1.5;}
.test{display:grid;grid-template-columns:52px 1.2fr 1fr 2fr;gap:12px;padding:10px 14px;border-bottom:1px solid #F3F4F6;font-size:13px;color:#374151;}
.pass{color:#15803D;font-weight:600;} .fail{color:#B91C1C;font-weight:600;}
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid #E5E7EB;}
.stTabs [data-baseweb="tab"]{height:44px;padding:0 16px;font-weight:600;}
[data-testid="stChatMessage"]{background:#FFFFFF;border:1px solid #EEF2F7;border-radius:12px;}
@media (max-width:1100px){.hero{grid-template-columns:1fr;}.flow{grid-template-columns:repeat(3,1fr);}}
@media (max-width:900px){.kpis,.grid4,.grid3,.road{grid-template-columns:1fr 1fr;}}
</style>
""")

# ----------------------------------------------------------------------------- state
defaults = {"messages": [], "last_code": None, "trace": None}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)


# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### CareConnect")
    st.caption("Healthcare price transparency · Perficient")
    st.divider()

    secret_key = ""
    try:
        secret_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        pass
    api_key = secret_key or os.getenv("ANTHROPIC_API_KEY", "")
    st.markdown("**Claude connection**")
    entered = st.text_input("Anthropic API key", type="password", placeholder="sk-ant-…",
                            help="Optional if set in .streamlit/secrets.toml or ANTHROPIC_API_KEY.",
                            label_visibility="collapsed")
    api_key = entered or api_key
    use_claude = st.toggle("Use Claude", value=bool(api_key), disabled=not api_key)
    if api_key and use_claude:
        st.caption(f"Connected · {MODEL}")
    else:
        st.caption("Offline mode (rules engine). Add a key to enable Claude.")

    st.divider()
    st.markdown("**Data**")
    live_mode = st.toggle("Verified data only", value=False, help="Excludes all fictional demo records.")
    all_df = load_records()
    live_count = int((all_df["is_demo"].astype(bool) == False).sum())  # noqa: E712
    demo_count = int(all_df["is_demo"].astype(bool).sum())
    st.caption(f"{live_count} verified · {demo_count} demo records")
    uploaded = st.file_uploader("Upload curated 12-field CSV", type=["csv"])
    if uploaded:
        try:
            incoming = pd.read_csv(uploaded, dtype={"procedure_code": "string", "zip_code": "string"})
            missing = set(CONTRACT_COLUMNS) - set(incoming.columns)
            if missing:
                st.error("Missing: " + ", ".join(sorted(missing)))
            else:
                live = add_live_records(incoming)
                st.success(f"Loaded {len(live)} verified records")
        except Exception as exc:  # surface parse errors to the presenter
            st.error(str(exc))
    if st.button("Clear conversation", width="stretch"):
        st.session_state.messages, st.session_state.last_code, st.session_state.trace = [], None, None
        st.rerun()

# ----------------------------------------------------------------------------- derived numbers
knee = query_records("73721", live_only=live_mode)
spread_pct = ((knee["price"].max() - knee["price"].min()) / knee["price"].min() * 100) if len(knee) > 1 else 0
data_label = "verified data" if live_mode else "demo data"
knee_lo, knee_hi, knee_n = (float(knee["price"].min()), float(knee["price"].max()), len(knee)) if len(knee) else (0, 0, 0)
V = st.session_state

# ----------------------------------------------------------------------------- header
html(f"""
<div class="hero" style="background-image:linear-gradient(90deg,rgba(11,37,69,.95) 0%,rgba(11,37,69,.82) 45%,rgba(11,37,69,.35) 100%),url('{img("hero")}')">
<div>
<div class="team">Ampana Jayaram · Amer Ahmed · Pranava Chanduri</div>
<div class="label">Perficient · Healthcare and Life Sciences</div>
<h1>CareConnect: healthcare prices patients can understand</h1>
<p>CareConnect turns CMS hospital price transparency files into plain-language, source-cited answers. Hospitals use it to attract
patients who compare prices, and Perficient can implement it as a reusable accelerator for hospitals and health systems.</p>
<div class="chips">
<span class="chip">Prices only from published records</span><span class="chip">Every rate cites its source</span>
</div>
</div>
</div>
""")

html(f"""
<div class="kpis" style="grid-template-columns:repeat(2,1fr)">
<div class="kpi"><div class="ico blue">{ICON_PULSE}</div><div><div class="label">Knee MRI price variation</div><div class="v">3.1×</div><div class="l">Commercial facility prices for the same knee MRI range from $367 to $1,126 (middle half of prices).</div><div class="src">Source: <a href="{PW_URL}" target="_blank">Philips &amp; Whaley, Health Affairs Scholar, 2025</a></div></div></div>
<div class="kpi"><div class="ico teal">{ICON_DOLLAR}</div><div><div class="label">Hospital revenue uplift / yr</div><div class="v f">New patients × published rate</div><div class="l">New patients = price-shopping visits × booking share. Rate from the hospital's own price file.</div><div class="src">Hospital supplies visits and booking share from its own analytics.</div></div></div>
</div>
""")

tab_value, tab_chat, tab_arch = st.tabs(
    [":material/trending_up: Business case", ":material/chat: Patient assistant",
     ":material/verified_user: Architecture and trust"])


# ----------------------------------------------------------------------------- helpers
def rate_cards(records: pd.DataFrame) -> str:
    if records is None or records.empty:
        return ""
    hi = float(records["price"].max())
    rows = []
    for i, r in enumerate(records.head(7).itertuples(), start=1):
        best = i == 1 and len(records) > 1
        src = r.source_url if isinstance(r.source_url, str) and r.source_url else None
        src_html = (f'<a href="{esc(src)}" target="_blank">official source</a> · row {esc(r.source_row)} · {esc(r.last_updated)}'
                    if src else "fictional demo record, no official source")
        tag = '<span class="tag">Demo</span>' if bool(r.is_demo) else '<span class="tag">Verified</span>'
        low = '<span class="tag low">Lowest</span>' if best else ""
        rows.append(f"""<div class="rate {'best' if best else ''}"><div class="rank">{i}</div>
<div><div class="rname">{esc(r.hospital_name)}{tag}{low}</div>
<div class="rsub">{esc(r.city)} {esc(r.zip_code)} · record {esc(r.record_id)} · {src_html}</div>
<div class="track"><span style="width:{float(r.price) / hi * 100:.0f}%"></span></div></div>
<div class="price">${float(r.price):,.0f}</div></div>""")
    out = '<div class="rates">' + "".join(rows) + "</div>"
    if len(records) > 1:
        lo = float(records["price"].min())
        out += (f'<div class="note">The lowest and highest negotiated rates differ by <b>${hi - lo:,.0f}</b> '
                f'({(hi - lo) / hi * 100:.0f}%) for the same CPT code.</div>')
    return out


def safe_stream(gen, fallback: str):
    try:
        yield from gen
    except Exception as exc:  # network/auth errors: degrade to the grounded answer
        yield f"\n\n{fallback}\n\n(Claude unavailable: {type(exc).__name__}. Showing the rules-engine answer.)"


# ----------------------------------------------------------------------------- assistant
with tab_chat:
    left, right = st.columns([1.6, 1], gap="large")
    with left:
        st.markdown("#### Ask about a procedure price")
        st.caption("Supported: knee MRI (73721), brain MRI (70551), abdomen/pelvis CT (74176). Blue Choice PPO outpatient facility rates.")
        suggestions = ["How much is a knee MRI without contrast?", "Which hospital is cheapest?",
                       "Where did these prices come from?", "What will I actually pay?",
                       "How much is an MRI?", "Just guess a C-section price"]
        cols = st.columns(3)
        for i, s in enumerate(suggestions):
            if cols[i % 3].button(s, key=f"sug{i}", width="stretch"):
                st.session_state.pending = s

        box = st.container(height=560, border=True)
        with box:
            if not st.session_state.messages:
                with st.chat_message("assistant"):
                    st.markdown("Hi, I'm CareConnect. Tell me which scan your doctor ordered and I'll compare "
                                "published Blue Choice PPO negotiated rates across Dallas-Fort Worth hospitals, with the source for every number.")
            for m in st.session_state.messages:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])
                    if m.get("records"):
                        html(rate_cards(pd.DataFrame(m["records"])))

        prompt = st.chat_input("Ask a question, for example: How much is a brain MRI?")
        prompt = prompt or st.session_state.pop("pending", None)

        if prompt:
            history = list(st.session_state.messages)
            with box:
                with st.chat_message("user"):
                    st.markdown(prompt)
            engine = "Rules engine"
            intent = extract_intent(prompt)
            client = None
            if api_key and use_claude:
                try:
                    client = make_client(api_key)
                    with st.spinner("Reading your question…"):
                        intent = claude_intent(client, prompt, history)
                    engine = f"Claude ({MODEL})"
                except Exception as exc:
                    st.toast(f"Claude unavailable ({type(exc).__name__}); using the rules engine.")
                    client = None
            res = resolve(prompt, last_code=st.session_state.last_code, live_only=live_mode, intent=intent)
            if res.code:
                st.session_state.last_code = res.code
            with box:
                with st.chat_message("assistant"):
                    if client is not None:
                        gen = stream_grounded_answer(client, prompt, history, res.records, res.intent, live_mode)
                        answer = st.write_stream(safe_stream(gen, res.text))
                    else:
                        answer = res.text
                        st.markdown(answer)
                    show_records = res.intent.intent in ("procedure", "comparison") and not res.records.empty
                    if show_records:
                        html(rate_cards(res.records))
            st.session_state.messages += [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": answer if isinstance(answer, str) else "".join(answer),
                 "records": res.records.to_dict(orient="records") if show_records else None},
            ]

    with right:
        html(f"""<div class="photo"><img src="{img('assistant')}" alt="Clinician using a phone">
<div class="body"><b>Know the price before you book.</b> Patients ask in their own words; CareConnect answers from
published hospital files and shows where every number came from.</div></div>""")
        st.write("")
        html("""<div class="box muted"><div class="label">Demo script</div>
<ol style="color:#374151;font-size:14px;line-height:1.8;padding-left:18px;margin:8px 0 0">
<li>Ask for a knee MRI without contrast</li><li>Follow up: “Which is cheapest?”</li>
<li>“Where did these prices come from?”</li><li>“What will I actually pay?” (safe limitation)</li>
<li>“Guess a C-section price” (declines to make one up)</li></ol></div>""")

# ----------------------------------------------------------------------------- value
with tab_value:
    banner("clinician", "Business case for hospitals", "How CareConnect pays off for a hospital",
           "Hospitals already have to publish their prices. CareConnect turns that obligation into a patient acquisition "
           "channel: patients who can see and understand a price are more likely to book, the hospital is seen as "
           "transparent, and staff spend less time answering pricing calls.")

    st.markdown("#### The business problem")
    html("""<div class="grid3 problem">
<div class="card"><div class="label">Business problem</div>
<p>A patient whose doctor orders an MRI does not know which hospital offers it, what it costs or what insurance covers.
CMS requires every hospital to publish its prices, but they sit in large machine-readable files full of billing codes and
different price types that patients cannot use.</p>
<p>So hospitals carry the cost of compliance without the benefit: price-shopping patients cannot compare them,
and pricing questions go to the call center.</p></div>
<div class="card"><div class="label">What CareConnect solves</div>
<ul>
<li><b>For patients:</b> plain-language answers about published prices, with the source for every number.</li>
<li><b>For hospitals:</b> turns a required price file into a way to attract patients, show transparency and reduce pricing calls.</li>
<li><b>For Perficient:</b> a reusable data, AI and digital experience accelerator to implement for hospital clients.</li>
</ul></div>
<div class="card"><div class="label">Proof of concept scope</div>
<p>Three diagnostic procedures: knee MRI, brain MRI and abdomen/pelvis CT.</p>
<p>Blue Choice PPO negotiated outpatient facility rates.</p>
<p>Dallas-Fort Worth hospitals.</p></div>
</div>""")
    st.write("")

    st.markdown("#### What the hospital gains")
    benefits = [
        ("patients", "More patients, more revenue",
         "Patients comparing prices can choose and book your hospital. Each added procedure is paid at your own "
         "published negotiated rate.", "Higher patient volume", ""),
        ("systems", "Marketing and trust",
         "Clear, cited prices show the hospital is open about what care costs, a message it can use in marketing "
         "and patient communications.", "Brand differentiation", ""),
        ("insurers", "Easier navigation",
         f"Patients find the right service and price online, so fewer calls reach the contact center. At Rochester "
         f"Regional Health, Perficient reported +{RRH_SCHEDULING_LIFT:.0%} online scheduling and "
         f"{fmt_big(RRH_MONTHLY_CALL_SAVINGS)}+ monthly call-center savings.", "Lower service cost",
         f'<div class="src">Source: <a href="{RRH}" target="_blank">Perficient, Rochester Regional Health case study</a></div>'),
        ("hospital", "Compliance made useful",
         f"CMS requires hospitals to publish standard charges and present shoppable services in a consumer-friendly "
         f"way. Hospitals with more than 550 beds can be fined ${CMS_MAX_DAILY_PENALTY:,} a day "
         f"(${CMS_MAX_ANNUAL_PENALTY:,} a year) for noncompliance.", "Regulatory value",
         f'<div class="src">Source: <a href="{CMS_PT_URL}" target="_blank">CMS hospital price transparency</a></div>'),
    ]
    html('<div class="grid4">' + "".join(
        f'<div class="card pcard"><img src="{img(ph)}" alt="{t}"><div class="body"><h4>{t}</h4><p>{d}</p>'
        f'<div class="out">{o}</div>{src}</div></div>' for ph, t, d, o, src in benefits) + "</div>")
    st.write("")


# ----------------------------------------------------------------------------- architecture
with tab_arch:
    banner("brain", "Architecture and trust", "Grounded by design",
           "Deterministic code retrieves and ranks prices from verified records. Claude only interprets the question and explains the results.")
    st.markdown("#### Data pipeline and AI extension")
    st.caption("Top: the ETL pipeline loads hospital price files into the central database. "
               "Bottom: a user asks a question, the AI assistant queries the database for the relevant data, "
               "and updates the dashboard, website and map.")
    with st.container(border=True):
        st.iframe(write_page(), height=590)  # app-authored page served from /app/static
    st.write("")
    a1, a2 = st.columns(2, gap="large")
    with a1:
        st.markdown("#### Privacy gateway")
        html("""<div class="note"><b>Proposed: privacy gateway.</b> We propose a privacy gateway that detects and removes
        unnecessary patient identifiers before requests reach a secure, enterprise-grade AI model.</div>""")
    with a2:
        st.markdown("#### Data contract")
        st.dataframe(pd.DataFrame({"Field": CONTRACT_COLUMNS, "Meaning": [
            "Stable unique record ID", "Hospital identity", "City", "ZIP as text", "CPT code as text",
            "Readable procedure label", "Blue Choice PPO", "Negotiated USD amount", "Official source link",
            "Original CSV row reference", "Published data date", "True only for fictional test data"]}),
            hide_index=True, width="stretch", height=455)

    st.markdown("#### Acceptance tests")
    if st.button("Run all 8 acceptance tests", type="primary"):
        st.session_state.acceptance = run_acceptance()
    results = st.session_state.get("acceptance")
    if results:
        passed = sum(r["passed"] for r in results)
        html(f"""<div class="box" style="padding:0">
<div style="padding:12px 14px;border-bottom:1px solid #E5E7EB;font-size:14px"><b>{passed} of {len(results)} passed</b>
<span style="color:#6B7280"> (rules engine)</span></div>
<div class="test" style="font-weight:600;color:#6B7280;font-size:12px"><div>Result</div><div>Question</div><div>Expected</div><div>Answer</div></div>""" + "".join(
            f"""<div class="test"><div class="{'pass' if r['passed'] else 'fail'}">{'Pass' if r['passed'] else 'Fail'}</div>
<div><b>{esc(r['question'])}</b><br><span style="color:#6B7280">intent: {esc(r['intent'])}</span></div>
<div>{esc(r['expected'])}</div><div style="color:#4B5563">{esc(r['answer'][:180])}{'…' if len(r['answer']) > 180 else ''}</div></div>"""
            for r in results) + "</div>")

    # ------------------------------------------------------------- privacy gateway value
    st.write("")
    st.markdown("#### How the privacy gateway helps Perficient")
    st.caption("Proposed next step. The current proof of concept does not collect patient data.")
    html("""<div class="grid4">
<div class="card"><div class="label">1 · Faster approvals</div><h4>Hospitals say yes faster</h4>
<p>Hospital legal, compliance and security teams must approve any AI tool, and patient privacy (HIPAA) is their first question.
A gateway that strips identifiers before the model sees them gives a clear answer: shorter sales cycles, fewer stalled deals.</p></div>
<div class="card"><div class="label">2 · Bigger engagements</div><h4>Unlocks the valuable roadmap</h4>
<p>Today CareConnect uses only public price data. Out-of-pocket estimates, appointment booking and patient-specific navigation
need personal context, and they cannot go live safely without a privacy layer.</p></div>
<div class="card"><div class="label">3 · Reusable asset</div><h4>Sold across every healthcare AI project</h4>
<p>Chatbots, the AI Healthcare Concierge, call-center summaries and scheduling assistants all share this need. Built once, reused
across clients: repeatable security, governance, integration and managed-services work.</p></div>
<div class="card"><div class="label">4 · Trust and lower risk</div><h4>Differentiation and protection</h4>
<p>"Privacy by design" stands out against bolt-on chatbots, and it protects Perficient too: a patient-data leak damages the
consultancy along with its client.</p></div>
</div>""")
