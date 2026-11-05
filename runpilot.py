"""
RunPilot - Test Run Sheet Manager (pure Python, Streamlit)

Works on Windows, Linux, macOS and on phones/tablets through any browser.

Run (from the folder that contains this file):
    pip install -r requirements.txt
    python -m streamlit run runpilot.py

Login (change these!):
    set environment variables RUNPILOT_USER and RUNPILOT_PASS
    default demo login -> admin / admin123

Options after login
    1. Upload & Count   - pick header row, ID + status columns, see Pass / Fail / Blocked / N/A / Not Testable
                          counts with charts, browse and select any row
    2. VLOOKUP          - upload original sheet + test run sheet and run
                          =VLOOKUP(test case ID, original range, column index, 0)
    3. Upload to CB     - paste your CB link, download the final sheet and jump to the link
"""

import hashlib
import hmac
import html
import io
import os
import re
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import requests
import streamlit as st

APP_NAME = "RunPilot"

# ------------------------------------------------------------------ theme file
# Streamlit reads its colour theme from .streamlit/config.toml in the folder you start it
# from. Create it once so the app looks the same on every machine (light or dark OS).
THEME_TOML = """# RunPilot theme v2 (light)
[theme]
base = "light"
primaryColor = "#2563eb"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f1f5f9"
textColor = "#0f172a"
font = "sans serif"
"""


def ensure_theme_file():
    try:
        cfg = Path.cwd() / ".streamlit" / "config.toml"
        if cfg.exists():
            old = cfg.read_text()
            ours = "RunPilot theme" in old or "#0b1220" in old  # earlier RunPilot dark theme
            if not ours or "RunPilot theme v2" in old:
                return
        cfg.parent.mkdir(exist_ok=True)
        cfg.write_text(THEME_TOML)
    except OSError:
        pass


ensure_theme_file()

st.set_page_config(page_title=APP_NAME, page_icon="🚀", layout="wide")

# ------------------------------------------------------------------ constants
GROUPS = ["Pass", "Fail", "Blocked", "Not Applicable", "Not Testable", "Others"]
GROUP_COLOR = {
    "Pass": "#16a34a",
    "Fail": "#dc2626",
    "Blocked": "#ea580c",
    "Not Applicable": "#64748b",
    "Not Testable": "#7c3aed",
    "Others": "#0891b2",
}
INDIGO, TEAL, SKY = "#4f46e5", "#0d9488", "#0284c7"

CSS = """
<style>
.stApp{background:linear-gradient(180deg,#f1f5ff 0,#ffffff 300px);}
#MainMenu, footer{visibility:hidden;}
header[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:2.2rem;padding-bottom:3rem;max-width:1280px;}
section[data-testid="stSidebar"]{background:#f8fafc;border-right:1px solid #e2e8f0;}

/* buttons */
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button,
[data-testid="stLinkButton"] a{
  border-radius:10px;border:1px solid #cbd5e1;background:#ffffff;color:#1e293b;
  font-weight:600;padding:.55rem 1.1rem;transition:all .15s ease;
  box-shadow:0 1px 2px rgba(15,23,42,.06);}
.stButton>button p,.stDownloadButton>button p,.stFormSubmitButton>button p,
[data-testid="stLinkButton"] a p{color:inherit !important;}
.stButton>button:hover,.stDownloadButton>button:hover,.stFormSubmitButton>button:hover,
[data-testid="stLinkButton"] a:hover{border-color:#2563eb;color:#2563eb;transform:translateY(-1px);
  box-shadow:0 6px 14px rgba(37,99,235,.15);}
button[data-testid="stBaseButton-primary"],button[data-testid="stBaseButton-primaryFormSubmit"],
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primaryFormSubmit"],
[data-testid="stLinkButton"] a[data-testid="stBaseLinkButton-primary"]{
  background:linear-gradient(135deg,#2563eb,#4f46e5);border:0;color:#ffffff;
  box-shadow:0 8px 18px rgba(37,99,235,.30);}
button[data-testid="stBaseButton-primary"]:hover,button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
.stButton>button[kind="primary"]:hover,.stFormSubmitButton>button[kind="primaryFormSubmit"]:hover,
[data-testid="stLinkButton"] a[data-testid="stBaseLinkButton-primary"]:hover{
  color:#ffffff !important;filter:brightness(1.08);}
.stFormSubmitButton>button{width:100%;padding:.75rem 1rem;font-size:1rem;}
section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]{gap:.3rem;}
section[data-testid="stSidebar"] .stButton,
section[data-testid="stSidebar"] div[data-testid="stElementContainer"]{width:100% !important;}
section[data-testid="stSidebar"] .stButton>button{width:100%;min-height:46px;padding:.55rem .9rem;
  display:flex;align-items:center;justify-content:flex-start;gap:.75rem;text-align:left;
  border:0;border-radius:10px;background:transparent;box-shadow:none;color:#475569;
  font-weight:600;transform:none;}
section[data-testid="stSidebar"] .stButton>button>div{justify-content:flex-start;text-align:left;}
section[data-testid="stSidebar"] .stButton>button p{text-align:left;}
section[data-testid="stSidebar"] .stButton>button:hover{background:#eef2f7;color:#0f172a;
  box-shadow:none;transform:none;}
section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"],
section[data-testid="stSidebar"] .stButton>button[kind="primary"]{
  background:#eaf0ff;color:#1d4ed8;box-shadow:inset 4px 0 0 #2563eb;font-weight:700;filter:none;}
section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:hover,
section[data-testid="stSidebar"] .stButton>button[kind="primary"]:hover{
  background:#e0e9ff;color:#1d4ed8 !important;filter:none;box-shadow:inset 4px 0 0 #2563eb;}
.st-key-logout button{color:#b91c1c !important;}
.st-key-logout button:hover{background:#fef2f2 !important;color:#b91c1c !important;}
.side-label{font-size:.72rem;font-weight:700;letter-spacing:1px;color:#94a3b8;line-height:1;
  padding:18px 0 8px 12px;}
.side-sep{height:1px;background:#e2e8f0;margin:16px 0;}

/* inputs */
div[data-baseweb="input"]>div,div[data-baseweb="select"]>div,div[data-baseweb="textarea"]{
  border-radius:10px;background:#ffffff;border-color:#cbd5e1;}
section[data-testid="stFileUploaderDropzone"]{background:#f8fafc;border:1.5px dashed #94a3b8;border-radius:14px;}
section[data-testid="stFileUploaderDropzone"]:hover{border-color:#2563eb;background:#eff6ff;}
div[data-testid="stForm"]{background:#ffffff;border:1px solid #e2e8f0;border-radius:20px;
  padding:30px 28px;box-shadow:0 20px 50px rgba(15,23,42,.10);}
button[data-baseweb="tab"]{font-weight:600;}

/* login hero */
.hero{position:relative;overflow:hidden;
  background:linear-gradient(145deg,#1e3a8a 0%,#2563eb 55%,#4f46e5 100%);
  border-radius:26px;padding:46px;min-height:540px;display:flex;flex-direction:column;
  justify-content:center;box-shadow:0 24px 60px rgba(37,99,235,.28);}
.hero::before{content:"";position:absolute;right:-90px;top:-90px;width:300px;height:300px;
  border-radius:50%;background:rgba(255,255,255,.08);}
.hero::after{content:"";position:absolute;left:-70px;bottom:-110px;width:280px;height:280px;
  border-radius:50%;background:rgba(255,255,255,.06);}
.hero>*{position:relative;z-index:1;}
.hero-logo{width:58px;height:58px;border-radius:16px;display:flex;align-items:center;
  justify-content:center;font-size:30px;background:rgba(255,255,255,.18);
  border:1px solid rgba(255,255,255,.35);}
.hero-brand{font-size:1.15rem;font-weight:700;letter-spacing:.5px;margin:14px 0 26px;
  color:rgba(255,255,255,.92);}
.hero-title{font-size:2.7rem;font-weight:800;line-height:1.1;color:#ffffff;margin:0 0 14px;}
.grad{background:linear-gradient(90deg,#bae6fd,#a7f3d0);-webkit-background-clip:text;
  background-clip:text;color:transparent;}
.hero-sub{color:rgba(255,255,255,.84);font-size:1.02rem;max-width:480px;margin-bottom:28px;}
.feat{display:flex;gap:14px;align-items:center;background:rgba(255,255,255,.12);
  border:1px solid rgba(255,255,255,.22);border-radius:14px;padding:12px 16px;
  margin-bottom:10px;color:#e0e7ff;}
.feat .ic{font-size:22px;}
.feat b{color:#ffffff;}
.login-title{font-size:1.9rem;font-weight:800;color:#0f172a;margin-bottom:4px;}
.login-sub{color:#64748b;margin-bottom:18px;}

/* dashboard */
.page-title{font-size:1.9rem;font-weight:800;color:#0f172a;line-height:1.2;}
.page-sub{color:#64748b;margin:2px 0 18px;}
.section{font-size:1.05rem;font-weight:700;color:#0f172a;margin:24px 0 10px;
  padding-left:10px;border-left:4px solid #2563eb;}
.kpi{background:#ffffff;border:1px solid #e2e8f0;border-left:4px solid var(--accent);
  border-radius:14px;padding:16px 18px;height:128px;overflow:hidden;margin-bottom:14px;
  box-shadow:0 4px 14px rgba(15,23,42,.06);}
.kpi-label{color:#64748b;font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.6px;}
.kpi-value{color:#0f172a;font-size:1.9rem;font-weight:800;line-height:1.25;word-break:break-word;}
.kpi-sub{color:#94a3b8;font-size:.8rem;min-height:1em;}
.opt{background:#ffffff;border:1px solid #e2e8f0;border-top:4px solid var(--accent);
  border-radius:16px;padding:22px;height:240px;overflow:hidden;margin-bottom:12px;
  box-shadow:0 6px 18px rgba(15,23,42,.06);transition:all .15s ease;}
.opt:hover{transform:translateY(-3px);box-shadow:0 14px 28px rgba(15,23,42,.12);}
.opt-num{width:34px;height:34px;border-radius:10px;background:var(--accent);color:#ffffff;
  font-weight:800;display:flex;align-items:center;justify-content:center;margin-bottom:12px;}
.opt-title{color:#0f172a;font-weight:700;font-size:1.15rem;margin-bottom:6px;}
.opt-desc{color:#64748b;font-size:.92rem;}
.pill{display:inline-block;border:1px solid var(--c);color:var(--c);background:#ffffff;
  border-radius:999px;padding:2px 12px;font-size:.8rem;font-weight:700;margin-left:8px;}
.chk{display:inline-block;background:#ffffff;border:1px solid #e2e8f0;border-radius:999px;
  padding:6px 14px;margin:0 8px 8px 0;color:#334155;font-size:.88rem;
  box-shadow:0 1px 3px rgba(15,23,42,.05);}
.row-card{background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;padding:18px;
  margin-top:10px;box-shadow:0 6px 18px rgba(15,23,42,.06);}
.row-head{color:#0f172a;font-weight:700;font-size:1.05rem;margin-bottom:12px;}
.row-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;}
.rc{background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:10px 12px;}
.rc-k{color:#64748b;font-size:.72rem;text-transform:uppercase;letter-spacing:.5px;font-weight:700;}
.rc-v{color:#0f172a;font-size:.95rem;word-break:break-word;}
.brand{display:flex;align-items:center;gap:10px;font-size:1.3rem;font-weight:800;color:#0f172a;margin:6px 0 4px;}
.brand .lg{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;
  background:linear-gradient(135deg,#2563eb,#4f46e5);box-shadow:0 6px 14px rgba(37,99,235,.28);}
.userchip{background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:10px 12px;
  color:#334155;font-size:.9rem;}
[data-testid="stToolbar"],[data-testid="stAppDeployButton"]{display:none !important;}
[data-testid="stColumn"] .stButton,[data-testid="stColumn"] .stDownloadButton,
[data-testid="column"] .stButton,[data-testid="column"] .stDownloadButton,
[data-testid="stLinkButton"]{width:100%;}
[data-testid="stColumn"] .stButton>button,[data-testid="stColumn"] .stDownloadButton>button,
[data-testid="column"] .stButton>button,[data-testid="column"] .stDownloadButton>button,
[data-testid="stLinkButton"] a{width:100%;justify-content:center;}
[class*="st-key-open_"],[class*="st-key-open_"]>div,[class*="st-key-open_"] .stButton{width:100% !important;}
[class*="st-key-open_"] button{width:100% !important;justify-content:center;}
.stFormSubmitButton,[data-testid="stFormSubmitButton"]{width:100% !important;}
.stFormSubmitButton>button{width:100% !important;}
div[data-testid="stForm"] div[data-testid="stElementContainer"],
[class*="st-key-FormSubmitter"],[class*="st-key-FormSubmitter"]>div{width:100% !important;}
div[data-testid="stVerticalBlockBorderWrapper"]{background:#ffffff;border:1px solid #e2e8f0 !important;
  border-radius:16px !important;box-shadow:0 6px 20px rgba(15,23,42,.06);padding:10px 16px 12px;
  margin-bottom:6px;}
.step{display:flex;align-items:center;gap:12px;margin:4px 0 16px;}
.step-n{width:30px;height:30px;flex:0 0 30px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;background:linear-gradient(135deg,#2563eb,#4f46e5);color:#ffffff;
  font-weight:800;font-size:.9rem;box-shadow:0 4px 10px rgba(37,99,235,.30);}
.step-t{font-weight:700;font-size:1.05rem;color:#0f172a;line-height:1.2;}
.step-s{color:#64748b;font-size:.85rem;line-height:1.3;}
.login-spacer{height:110px;}
@media (max-width:800px){
  .login-spacer{height:14px;}
  .hero{padding:26px;min-height:0;}.hero-title{font-size:1.9rem;}.feat-wrap{display:none;}
}
</style>
"""

HERO = """
<div class="hero">
<div class="hero-logo">🚀</div>
<div class="hero-brand">RunPilot</div>
<div class="hero-title">Test run sheets,<br><span class="grad">sorted in minutes.</span></div>
<div class="hero-sub">Count pass, fail, blocked and other test statuses, merge data between sheets with VLOOKUP
and hand the final sheet over to CB, all in one place.</div>
<div class="feat-wrap">
<div class="feat"><span class="ic">📊</span><div><b>Instant analytics</b><br>Pass, fail, blocked, N/A and not testable counts</div></div>
<div class="feat"><span class="ic">🔁</span><div><b>VLOOKUP between sheets</b><br>Original data straight into your test run sheet</div></div>
<div class="feat"><span class="ic">☁️</span><div><b>One-click CB hand-off</b><br>Jump to your CB link with the sheet ready</div></div>
</div>
</div>
"""


def classify(value) -> str:
    """Put a status value into a group, whatever the spelling (Pass, PASSED, N/A, not-testable...)."""
    c = re.sub(r"[^a-z]", "", str(value).lower())  # letters only: "Not Testable" -> "nottestable"
    if c == "na" or "notapplicable" in c or "nonapplicable" in c or "inapplicable" in c:
        return "Not Applicable"
    if "nottestable" in c or "nontestable" in c or "untestable" in c or "notestable" in c:
        return "Not Testable"
    if "block" in c:
        return "Blocked"
    if "fail" in c or "notpass" in c or c in {"f", "ng", "error"}:
        return "Fail"
    if "pass" in c or "success" in c or c in {"p", "ok"}:
        return "Pass"
    return "Others"


# ------------------------------------------------------------------ small helpers
def html_block(markup: str):
    """Render HTML safely: strip indentation and blank lines so Markdown does not treat it as code."""
    clean = "\n".join(line.strip() for line in markup.splitlines() if line.strip())
    st.markdown(clean, unsafe_allow_html=True)


def esc(value) -> str:
    return html.escape(str(value))


def short(text, n=22) -> str:
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


def page_header(title: str, sub: str = ""):
    html_block(f'<div class="page-title">{esc(title)}</div><div class="page-sub">{esc(sub)}</div>')


def section(title: str):
    html_block(f'<div class="section">{esc(title)}</div>')


def step(num, title: str, sub: str = ""):
    html_block(
        f'<div class="step"><div class="step-n">{num}</div><div><div class="step-t">{esc(title)}</div>'
        f'<div class="step-s">{esc(sub)}</div></div></div>'
    )


def kpi_row(items):
    cols = st.columns(len(items))
    for col, (label, value, color, sub) in zip(cols, items):
        col.markdown(
            f'<div class="kpi" style="--accent:{color}"><div class="kpi-label">{esc(label)}</div>'
            f'<div class="kpi-value">{esc(value)}</div><div class="kpi-sub">{esc(sub)}</div></div>',
            unsafe_allow_html=True,
        )


def guess(cols, keywords, default=0):
    """Index of the first column whose name contains one of the keywords."""
    for key in keywords:
        for i, name in enumerate(cols):
            if key in name.lower():
                return i
    return min(default, len(cols) - 1)


def col_letter(i: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA (Excel style)."""
    i += 1
    out = ""
    while i:
        i, r = divmod(i - 1, 26)
        out = chr(65 + r) + out
    return out


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()


def name_key(name) -> str:
    """Column-name key that ignores case, spaces, underscores and a trailing s (Remark == remarks)."""
    k = re.sub(r"[^a-z0-9]", "", str(name).lower())
    return k[:-1] if k.endswith("s") and len(k) > 3 else k


def norm_key(series: pd.Series) -> pd.Series:
    """Make lookup keys comparable like Excel does: trimmed, case-insensitive, 101.0 == 101."""
    def f(v):
        if pd.isna(v):
            return None
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        return str(v).strip().casefold()

    return series.map(f)


def read_sheet(prefix: str, label: str):
    """Uploader + sheet picker + header-row picker. Returns (DataFrame, signature) or (None, None)."""
    file = st.file_uploader(label, type=["xlsx", "xlsm", "xls", "csv"], key=f"{prefix}_file")
    if not file:
        return None, None
    is_csv = file.name.lower().endswith(".csv")
    c1, c2 = st.columns([2, 1])
    sheet = None
    try:
        if not is_csv:
            names = pd.ExcelFile(file).sheet_names
            sheet = c1.selectbox("Sheet", names, key=f"{prefix}_sheet")
        hdr = c2.number_input(
            "Header row", min_value=1, value=1, step=1, key=f"{prefix}_hdr",
            help="The row number that contains the column names.",
        )
        file.seek(0)
        if is_csv:
            df = pd.read_csv(file, header=hdr - 1, keep_default_na=False, na_values=[""])
        else:
            df = pd.read_excel(file, sheet_name=sheet, header=hdr - 1,
                               keep_default_na=False, na_values=[""])
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not read the file: {exc}")
        return None, None
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all").reset_index(drop=True)
    return df, (file.name, file.size, sheet, int(hdr))


def set_testrun(df, sig):
    st.session_state.update(
        tr_df=df, tr_orig=df.copy(), tr_sig=sig, tr_name=sig[0], vl_applied=[]
    )


# ------------------------------------------------------------------ auth
def _hash(password: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), b"runpilot-salt", 100_000).hex()


USING_DEFAULT_LOGIN = "RUNPILOT_PASS" not in os.environ
USERS = {os.getenv("RUNPILOT_USER", "admin"): _hash(os.getenv("RUNPILOT_PASS", "admin123"))}


def check_login(user: str, pwd: str) -> bool:
    stored = USERS.get(user)
    return stored is not None and hmac.compare_digest(stored, _hash(pwd))


def login_page():
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        html_block(HERO)
    with right:
        html_block('<div class="login-spacer"></div>')
        html_block(
            '<div class="login-title">Welcome back 👋</div>'
            '<div class="login-sub">Sign in to continue to RunPilot</div>'
        )
        with st.form("login"):
            user = st.text_input("Username", placeholder="Enter your username")
            pwd = st.text_input("Password", type="password", placeholder="Enter your password")
            ok = st.form_submit_button("Sign in", type="primary")
        if USING_DEFAULT_LOGIN:
            st.caption("Demo login: admin / admin123 (set RUNPILOT_USER / RUNPILOT_PASS to change)")
        if ok:
            if check_login(user.strip(), pwd):
                st.session_state.logged_in = True
                st.session_state.user = user.strip()
                st.session_state.page = "home"
                st.rerun()
            else:
                st.error("Invalid username or password.")


# ------------------------------------------------------------------ charts
def _group_scale():
    return alt.Scale(domain=GROUPS, range=[GROUP_COLOR[g] for g in GROUPS])


def donut_chart(gdf: pd.DataFrame, total: int):
    arc = (
        alt.Chart(gdf)
        .mark_arc(innerRadius=72, outerRadius=118, cornerRadius=4)
        .encode(
            theta=alt.Theta("Count:Q"),
            color=alt.Color("Group:N", scale=_group_scale(),
                            legend=alt.Legend(title=None, orient="bottom", columns=3)),
            tooltip=["Group:N", "Count:Q"],
        )
    )
    centre = (
        alt.Chart(pd.DataFrame({"t": [f"{total:,}"]}))
        .mark_text(size=30, fontWeight="bold", color="#0f172a")
        .encode(text="t:N")
    )
    return alt.layer(arc, centre).properties(width="container", height=340)


def status_bar_chart(sdf: pd.DataFrame):
    return (
        alt.Chart(sdf)
        .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
        .encode(
            x=alt.X("Status:N", sort="-y", title=None, axis=alt.Axis(labelAngle=-30)),
            y=alt.Y("Count:Q", title=None),
            color=alt.Color("Group:N", scale=_group_scale(), legend=None),
            tooltip=["Status:N", "Group:N", "Count:Q"],
        )
        .properties(width="container", height=300)
    )


def row_card(row: pd.Series):
    group = row["Result group"]
    cells = []
    for key, value in row.items():
        if key == "#":
            continue
        text = "—" if pd.isna(value) else str(value)
        cells.append(
            '<div class="rc"><div class="rc-k">' + esc(key) + '</div><div class="rc-v">'
            + esc(text).replace("\n", "<br>") + "</div></div>"
        )
    html_block(
        '<div class="row-card"><div class="row-head">Row ' + str(int(row["#"]))
        + f'<span class="pill" style="--c:{GROUP_COLOR[group]}">{esc(group)}</span></div>'
        '<div class="row-grid">' + "".join(cells) + "</div></div>"
    )


# ------------------------------------------------------------------ page: home
def page_home():
    hour = datetime.now().hour
    greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    page_header(f"{greet}, {st.session_state.user} 👋",
                "Here is where your test run work stands.")

    tr, orig = st.session_state.get("tr_df"), st.session_state.get("orig_df")
    applied = st.session_state.get("vl_applied", [])
    loaded = int(tr is not None) + int(orig is not None)
    kpi_row([
        ("Original sheet", short(st.session_state.get("orig_name", "Not loaded")), TEAL,
         "" if orig is None else f"{len(orig):,} rows · {len(orig.columns)} columns"),
        ("Test run sheet", short(st.session_state.get("tr_name", "Not loaded")), INDIGO,
         "" if tr is None else f"{len(tr):,} rows · {len(tr.columns)} columns"),
        ("Sheets loaded", f"{loaded} of 2", SKY, "original + test run"),
    ])

    section("Choose what you want to do")
    cards = [
        ("count", "1", "Upload & Count",
         "Upload the original sheet and see pass, fail, blocked, not applicable and not "
         "testable counts with charts. Select any row for its details.", INDIGO),
        ("vlookup", "2", "VLOOKUP",
         "Upload the test run sheet and bring data across from the original sheet with "
         "=VLOOKUP(test case ID, range, column index, 0).", TEAL),
        ("cb", "3", "Upload to CB",
         "Paste your CB link, download the final test run sheet and jump straight to the "
         "link when you press Upload.", SKY),
    ]
    for col, (key, num, title, desc, color) in zip(st.columns(3), cards):
        with col:
            html_block(
                f'<div class="opt" style="--accent:{color}"><div class="opt-num">{num}</div>'
                f'<div class="opt-title">{esc(title)}</div><div class="opt-desc">{esc(desc)}</div></div>'
            )
            if st.button(f"Open {title}  →", key=f"open_{key}"):
                st.session_state.page = key
                st.rerun()

    section("Checklist")
    checks = [
        (orig is not None, "Original sheet uploaded"),
        (tr is not None, "Test run sheet uploaded"),
        (bool(applied), "VLOOKUP applied"),
    ]
    html_block("".join(
        f'<span class="chk">{"✅" if ok else "⬜"} {esc(text)}</span>' for ok, text in checks
    ))


# ------------------------------------------------------------------ page: upload & count
def page_count():
    page_header("Upload & Count",
                "Upload the original sheet, choose the columns and see the count of every test status.")

    with st.container(border=True):
        step(1, "Upload original sheet", "Excel or CSV. Pick the sheet and the row that holds the column names.")
        new, sig = read_sheet("cnt", "Drag and drop the original sheet (xlsx, xls, csv)")
        if new is not None and sig != st.session_state.get("orig_sig"):
            st.session_state.update(orig_df=new, orig_sig=sig, orig_name=sig[0])
        df = st.session_state.get("orig_df")
        if df is None:
            st.info("Upload the original sheet to see the analysis. Use “Header row” if your "
                    "column names are not in row 1.")
            return
        st.caption(f"✅ {st.session_state.orig_name} · {len(df):,} rows · {len(df.columns)} columns")

    cols = list(df.columns)
    with st.container(border=True):
        step(2, "Choose the columns", "Which column holds the test case ID and which holds the status.")
        c1, c2 = st.columns(2)
        id_col = c1.selectbox(
            "Test case ID column", cols, key="cnt_id",
            index=guess(cols, ["test case id", "testcase id", "tc id", "test case", "testcase", "id"]),
        )
        status_col = c2.selectbox(
            "Status / result column", cols, key="cnt_status",
            index=guess(cols, ["status", "result", "verdict", "outcome"], default=1),
        )
        if id_col == status_col:
            st.warning("The ID column and the status column are the same. Pick different columns.")

    valid = df[df[id_col].notna()].copy()
    if valid.empty:
        st.warning("No test cases found: the chosen ID column is empty.")
        return
    status = valid[status_col].fillna("(blank)").astype(str).str.strip().replace("", "(blank)")
    values = sorted(status.unique())

    group = status.map(classify)
    counts = group.value_counts().reindex(GROUPS, fill_value=0)
    total = len(valid)
    unique_ids = valid[id_col].nunique()
    n = {g: int(counts[g]) for g in GROUPS}
    testable = total - n["Not Applicable"] - n["Not Testable"]
    exec_rate = n["Pass"] / testable * 100 if testable else 0.0

    def pct(x):
        return f"{x / total * 100:.1f}% of total"

    section("Results")
    kpi_row([
        ("Total test cases", f"{total:,}", INDIGO, f"{unique_ids:,} unique IDs"),
        ("Passed", f"{n['Pass']:,}", GROUP_COLOR["Pass"], pct(n["Pass"])),
        ("Failed", f"{n['Fail']:,}", GROUP_COLOR["Fail"], pct(n["Fail"])),
        ("Pass rate", f"{n['Pass'] / total * 100:.1f}%", TEAL,
         f"{exec_rate:.1f}% excl. N/A & not testable"),
    ])
    kpi_row([
        ("Blocked", f"{n['Blocked']:,}", GROUP_COLOR["Blocked"], pct(n["Blocked"])),
        ("Not Applicable", f"{n['Not Applicable']:,}", GROUP_COLOR["Not Applicable"],
         pct(n["Not Applicable"])),
        ("Not Testable", f"{n['Not Testable']:,}", GROUP_COLOR["Not Testable"],
         pct(n["Not Testable"])),
        ("Others", f"{n['Others']:,}", GROUP_COLOR["Others"], "blank, not run or unrecognised"),
    ])

    with st.container(border=True):
        t_over, t_det, t_rows = st.tabs(["📈 Overview", "📋 Status details", "🔎 Browse & select row"])

        with t_over:
            left, right = st.columns([1, 1.25])
            gdf = pd.DataFrame({"Group": GROUPS, "Count": [n[g] for g in GROUPS]})
            with left:
                st.markdown("**Result split**")
                st.altair_chart(donut_chart(gdf[gdf["Count"] > 0], total))
            with right:
                st.markdown("**Count by status value**")
                sdf = status.value_counts().rename_axis("Status").reset_index(name="Count").head(15)
                sdf["Group"] = sdf["Status"].map(classify)
                st.altair_chart(status_bar_chart(sdf))

            summary = gdf.copy()
            summary["Share"] = (summary["Count"] / total * 100).round(1).astype(str) + " %"
            st.dataframe(summary, hide_index=True)

        with t_det:
            st.caption("Every status value found in your sheet and the group RunPilot counted it in.")
            det = status.value_counts().rename_axis("Status value").reset_index(name="Count")
            det.insert(1, "Counted as", det["Status value"].map(classify))
            det["Share"] = (det["Count"] / total * 100).round(1).astype(str) + " %"
            st.dataframe(det, hide_index=True)
            unknown = det[det["Counted as"] == "Others"]["Status value"].tolist()
            if unknown:
                st.info("Not recognised as Pass, Fail, Blocked, Not Applicable or Not Testable, so "
                        "counted under Others: " + ", ".join(unknown))

        with t_rows:
            choice = st.radio("Show", ["All"] + GROUPS, horizontal=True, key="cnt_filter")
            view = valid.copy()
            view.insert(0, "#", view.index + 1)
            view["Result group"] = group
            if choice != "All":
                view = view[view["Result group"] == choice]
            view = view.reset_index(drop=True)
            if view.empty:
                st.info("No rows in this group.")
            else:
                st.caption("Tick the checkbox at the start of a row to see that line's full data below.")
                pos = None
                try:
                    event = st.dataframe(view, hide_index=True, on_select="rerun",
                                         selection_mode="single-row", key="cnt_tbl")
                    picked = event.selection.rows
                    pos = picked[0] if picked else None
                except TypeError:  # older Streamlit without row selection
                    st.dataframe(view, hide_index=True)
                    n = st.number_input("Row # to view", min_value=1, value=1, step=1)
                    match = view.index[view["#"] == n]
                    pos = match[0] if len(match) else None
                if pos is not None and pos < len(view):
                    row_card(view.iloc[pos])


# ------------------------------------------------------------------ page: vlookup
def page_vlookup():
    page_header("VLOOKUP",
                "Bring data from the original sheet into the test run sheet, "
                "just like =VLOOKUP(test case ID, original range, column index, 0).")
    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash)

    with st.container(border=True):
        step(1, "Upload both sheets", "The original sheet is reused from Upload & Count. Upload another one here only to replace it.")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Original sheet** · source of the data")
            new, sig = read_sheet("orig", "Upload the original sheet")
            if new is not None and sig != st.session_state.get("orig_sig"):
                st.session_state.update(orig_df=new, orig_sig=sig, orig_name=sig[0])
            if st.session_state.get("orig_df") is not None:
                o = st.session_state.orig_df
                st.caption(f"✅ {st.session_state.orig_name} · {len(o):,} rows · {len(o.columns)} columns")
        with c2:
            st.markdown("**Test run sheet** · receives the data")
            new, sig = read_sheet("trv", "Upload the test run sheet")
            if new is not None and sig != st.session_state.get("tr_sig"):
                set_testrun(new, sig)
            if st.session_state.get("tr_df") is not None:
                t = st.session_state.tr_df
                st.caption(f"✅ {st.session_state.tr_name} · {len(t):,} rows · {len(t.columns)} columns")

    orig, tr = st.session_state.get("orig_df"), st.session_state.get("tr_df")
    if orig is None or tr is None:
        st.info("Upload both sheets to continue.")
        return

    or_cols, tr_cols = list(orig.columns), list(tr.columns)
    id_guess = ["test case id", "testcase id", "tc id", "test case", "testcase", "id"]
    tr_lower = {name_key(c): c for c in tr_cols}

    with st.container(border=True):
        step(2, "Match the IDs and choose what to copy",
             "Each test run ID is looked up in the original sheet. The columns you tick are copied "
             "from the original into the test run sheet.")
        a, b = st.columns(2)
        look_col = a.selectbox("Test run ID column (lookup value)", tr_cols,
                               index=guess(tr_cols, id_guess), key="vl_look",
                               help="Test case ID column in the test run sheet.")
        key_col = b.selectbox("Original ID column (match with)", or_cols,
                              index=guess(or_cols, id_guess), key="vl_start",
                              help="Test case ID column in the original sheet.")
        copy_options = [c for c in or_cols if c != key_col]
        default_cols = [c for c in copy_options
                        if name_key(c) in ("remark", name_key("status")) and name_key(c) in tr_lower]
        picked = st.multiselect("Original columns to copy into the test run sheet", copy_options,
                                default=default_cols, key=f"vl_cols_{key_col}",
                                help="Remarks, Status or any other column. A column with the same name "
                                     "in the test run sheet is filled; otherwise a new column is added.")
        mode = st.radio("If the test run cell already has a value", ["Overwrite with original data",
                        "Keep it, only fill blank cells"], horizontal=True, key="vl_mode")

        targets = {}
        if picked:
            st.markdown("**Original column → Test run column**")
            for src in picked:
                c1, c2 = st.columns([1, 1])
                c1.text_input("Original column", value=src, disabled=True, key=f"vl_src_{src}")
                existing = tr_lower.get(name_key(src))
                targets[src] = c2.text_input(
                    "Test run column" + (" (already exists, will be filled)" if existing else " (new column)"),
                    value=existing or src, key=f"vl_tgt_{src}_{existing}").strip() or src

    # ---- run the lookup
    okeys = norm_key(orig[key_col])
    tkeys = norm_key(tr[look_col])
    matched = tkeys.isin(set(okeys.dropna()))

    def lookup(src):
        mapping = pd.Series(orig[src].values, index=okeys.values)
        mapping = mapping[mapping.index.notna()]
        mapping = mapping[~mapping.index.duplicated(keep="first")]
        return tkeys.map(mapping)

    updated, stats, formulas = tr.copy(), [], []
    key_i = or_cols.index(key_col)
    for src, tgt in targets.items():
        found = lookup(src)
        if tgt in updated.columns:
            cur = updated[tgt]
            can_write = matched & found.notna()
            if mode.startswith("Keep"):
                can_write &= cur.isna() | (cur.astype(str).str.strip() == "")
            new_vals = cur.astype(object).where(~can_write, found)
            stats.append({"Original column": src, "Test run column": tgt, "Type": "existing",
                          "Cells filled / updated": int(can_write.sum())})
        else:
            new_vals = found.where(matched, "#N/A")
            stats.append({"Original column": src, "Test run column": tgt, "Type": "new",
                          "Cells filled / updated": int(matched.sum())})
        updated[tgt] = new_vals
        src_i = or_cols.index(src)
        if src_i > key_i:
            f = (f"=VLOOKUP({col_letter(tr_cols.index(look_col))}2, "
                 f"Original!${col_letter(key_i)}:${col_letter(src_i)}, {src_i - key_i + 1}, 0)")
        else:  # VLOOKUP cannot look to the left of the key column
            f = (f"=INDEX(Original!${col_letter(src_i)}:${col_letter(src_i)}, "
                 f"MATCH({col_letter(tr_cols.index(look_col))}2, Original!${col_letter(key_i)}:${col_letter(key_i)}, 0))")
        formulas.append(f"{tgt}:  {f}")

    with st.container(border=True):
        step(3, "Result", "Preview the filled test run sheet, then apply it.")
        kpi_row([
            ("Test run rows", f"{len(tr):,}", INDIGO, f"ID column: {short(look_col, 24)}"),
            ("Original rows", f"{len(orig):,}", TEAL, f"ID column: {short(key_col, 24)}"),
            ("IDs matched", f"{int(matched.sum()):,}", GROUP_COLOR["Pass"],
             f"{matched.mean() * 100:.1f}% of test run rows"),
            ("IDs not found", f"{int((~matched).sum()):,}", GROUP_COLOR["Fail"],
             "test run ID missing in original"),
        ])
        if not picked:
            st.info("Tick at least one original column above (for example Remarks) to copy it.")
        else:
            st.dataframe(pd.DataFrame(stats), hide_index=True)
            with st.expander("Equivalent Excel formulas"):
                st.code("\n".join(formulas), language="text")
            st.caption("IDs not found keep their current value (new columns show #N/A). "
                       "Blank cells in the original never erase test run data.")
        st.dataframe(updated, hide_index=True)

        b1, b2, b3, _ = st.columns([1, 1, 1, 1])
        if b1.button("✔ Apply to test run sheet", type="primary", disabled=not picked):
            applied = [a_ for a_ in st.session_state.get("vl_applied", []) if a_["name"] not in targets.values()]
            applied += [{"name": t, "formula": f} for t, f in zip(targets.values(), formulas)]
            st.session_state.update(
                tr_df=updated, vl_applied=applied,
                flash="Copied from the original sheet: " + ", ".join(targets.values())
                      + f" ({int(matched.sum())} IDs matched, {int((~matched).sum())} not found).")
            st.rerun()
        b2.download_button("⬇ Download test run sheet", to_excel_bytes(st.session_state.tr_df),
                           file_name="testrun_with_vlookup.xlsx")
        if b3.button("↺ Reset added columns"):
            st.session_state.update(tr_df=st.session_state.tr_orig.copy(), vl_applied=[],
                                    flash="Reset the test run sheet to the uploaded version.")
            st.rerun()

        applied = st.session_state.get("vl_applied", [])
        if applied:
            html_block("".join(f'<span class="chk">➕ {esc(a_["name"])}</span>' for a_ in applied))
            st.caption("These columns are now part of the test run sheet and will be used in Upload to CB.")


# ------------------------------------------------------------------ page: upload to CB
def page_cb():
    page_header("Upload to CB",
                "Add the test run sheet, then paste your CB link and press Upload.")

    with st.container(border=True):
        step(1, "Test run sheet", "Upload it here, or reuse the one from the VLOOKUP step.")
        new, sig = read_sheet("cb", "Drag and drop the test run sheet (xlsx, xls, csv)")
        if new is not None and sig != st.session_state.get("tr_sig"):
            set_testrun(new, sig)
        tr = st.session_state.get("tr_df")
        if tr is None:
            st.info("Upload the test run sheet to continue.")
            return
        applied = st.session_state.get("vl_applied", [])
        extra = f" · VLOOKUP columns: {', '.join(a_['name'] for a_ in applied)}" if applied else ""
        st.caption(f"✅ {st.session_state.tr_name} · {len(tr):,} rows · {len(tr.columns)} columns{extra}")
        d1, d2, _ = st.columns([1, 1, 2])
        base_name = os.path.splitext(st.session_state.tr_name)[0]
        d1.download_button("⬇ Excel (.xlsx)", to_excel_bytes(tr), file_name=f"{base_name}_final.xlsx")
        d2.download_button("⬇ CSV (.csv)", tr.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"{base_name}_final.csv")

    with st.container(border=True):
        step(2, "Paste your CB link and press Upload",
             "Upload opens the link in a new tab. Upload the downloaded sheet on that page.")
        link = st.text_input("CB link", key="cb_link",
                             placeholder="https://codebeamer.company.com/cb/...  (the page where the test run sheet is uploaded)")
        link = link.strip()
        valid_link = link.lower().startswith(("http://", "https://"))
        if link and not valid_link:
            st.error("The link must start with http:// or https://")
        lb, _ = st.columns([1, 2])
        lb.link_button("☁️  Upload to CB  ↗", link if valid_link else "https://", type="primary",
                       disabled=not valid_link)

    with st.expander("Advanced: send every row directly through the CB REST API"):
        st.caption("Optional. Creates one tracker item per row. Needs your CB server URL, tracker "
                   "ID and credentials. Keep “Dry run” ticked to preview without sending.")
        a1, a2 = st.columns(2)
        base_url = a1.text_input("CB server URL", placeholder="https://codebeamer.company.com/cb")
        tracker_id = a2.text_input("Tracker ID")
        a3, a4 = st.columns(2)
        cb_user = a3.text_input("CB username")
        cb_pass = a4.text_input("CB password / API token", type="password")
        name_col = st.selectbox("Column used as item Name", list(tr.columns), key="api_name")
        desc_cols = st.multiselect("Columns added to Description",
                                   [c for c in tr.columns if c != name_col], key="api_desc")
        dry_run = st.checkbox("Dry run (do not send, only preview)", value=True)
        if st.button("Start API upload"):
            if not dry_run and not (base_url and tracker_id and cb_user and cb_pass):
                st.error("Fill in the server URL, tracker ID and credentials.")
                return
            url = f"{base_url.rstrip('/')}/rest/v3/trackers/{tracker_id}/items"
            bar = st.progress(0.0)
            ok, failed, errors, payload = 0, 0, [], {}
            for i, (_, row) in enumerate(tr.iterrows(), start=1):
                payload = {
                    "name": str(row[name_col]),
                    "description": "\n".join(f"{c}: {row[c]}" for c in desc_cols),
                }
                if dry_run:
                    ok += 1
                else:
                    try:
                        r = requests.post(url, json=payload, auth=(cb_user, cb_pass), timeout=30)
                        if r.status_code in (200, 201):
                            ok += 1
                        else:
                            failed += 1
                            errors.append({"row": i, "status": r.status_code,
                                           "response": r.text[:200]})
                    except requests.RequestException as exc:
                        failed += 1
                        errors.append({"row": i, "status": "error", "response": str(exc)})
                bar.progress(i / len(tr))
            kpi_row([("Would upload" if dry_run else "Uploaded", f"{ok:,}", GROUP_COLOR["Pass"], ""),
                     ("Failed", f"{failed:,}", GROUP_COLOR["Fail"], "")])
            if errors:
                st.dataframe(pd.DataFrame(errors), hide_index=True)
            if dry_run:
                st.info("Dry run only. Untick “Dry run” to send the rows to CB.")
                st.json({"url": url, "example_payload": payload})


# ------------------------------------------------------------------ navigation
PAGES = [
    ("home", "Dashboard", ":material/dashboard:", page_home),
    ("count", "Upload & Count", ":material/bar_chart:", page_count),
    ("vlookup", "VLOOKUP", ":material/manage_search:", page_vlookup),
    ("cb", "Upload to CB", ":material/cloud_upload:", page_cb),
]


def sidebar():
    with st.sidebar:
        html_block(f'<div class="brand"><div class="lg">🚀</div>{APP_NAME}</div>')
        html_block('<div class="side-label">MENU</div>')
        for key, label, icon, _ in PAGES:
            active = st.session_state.page == key
            if st.button(label, key=f"nav_{key}", icon=icon,
                         type="primary" if active else "secondary"):
                st.session_state.page = key
                st.rerun()
        html_block('<div class="side-sep"></div>')
        html_block(f'<div class="userchip">👤 Signed in as <b>{esc(st.session_state.user)}</b></div>')
        html_block('<div style="height:6px"></div>')
        if st.button("Logout", key="logout", icon=":material/logout:"):
            st.session_state.clear()
            st.rerun()


html_block(CSS)
if st.get_option("theme.base") != "light":
    st.warning("The white theme was just installed. Stop the app (Ctrl+C in the terminal) and "
               "run it again to apply it. If this message stays, delete the .streamlit folder "
               "next to runpilot.py and start again.")
st.session_state.setdefault("page", "home")

if st.session_state.get("logged_in"):
    sidebar()
    for key, _, _, func in PAGES:
        if key == st.session_state.page:
            func()
else:
    login_page()