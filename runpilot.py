"""
RunPilot - Test Run Sheet Manager (pure Python, Streamlit)

Works on Windows, Linux, macOS and on phones/tablets through any browser.

Run:
    pip install streamlit pandas openpyxl requests
    streamlit run runpilot.py

Login (change these!):
    set environment variables RUNPILOT_USER and RUNPILOT_PASS
    default demo login -> admin / admin123

Options after login
    1. Upload Excel sheet
    2. Analysis: total test case count, find + remove duplicates (with count), VLOOKUP
    3. Upload to CB (Codebeamer) - test run sheet
"""

import hashlib
import hmac
import io
import os

import pandas as pd
import requests
import streamlit as st

APP_NAME = "RunPilot"

st.set_page_config(page_title=APP_NAME, page_icon="🚀", layout="wide")

# ------------------------------------------------------------------ styling
st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 55%, #6d28d9 100%); }
    h1, h2, h3, h4, p, label, span, div[data-testid="stMarkdownContainer"] { color: #f1f5f9; }
    .card { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.18);
            border-radius: 16px; padding: 24px; backdrop-filter: blur(8px); }
    div[data-testid="stMetric"] { background: rgba(255,255,255,0.10); border-radius: 14px;
            padding: 16px; border: 1px solid rgba(255,255,255,0.18); }
    div[data-testid="stMetricValue"] { color: #ffffff; }
    .stButton > button, .stDownloadButton > button {
        background: linear-gradient(90deg, #06b6d4, #8b5cf6); color: white; border: 0;
        border-radius: 10px; padding: 0.6rem 1.2rem; font-weight: 600; }
    input, textarea { color: #0f172a !important; }
    section[data-testid="stSidebar"] { background: rgba(15,23,42,0.85); }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ auth
def _hash(password: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), b"runpilot-salt", 100_000
    ).hex()


USERS = {os.getenv("RUNPILOT_USER", "admin"): _hash(os.getenv("RUNPILOT_PASS", "admin123"))}


def check_login(user: str, pwd: str) -> bool:
    stored = USERS.get(user)
    return stored is not None and hmac.compare_digest(stored, _hash(pwd))


def login_page():
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown(f"<h1 style='text-align:center'>🚀 {APP_NAME}</h1>", unsafe_allow_html=True)
        st.markdown(
            "<p style='text-align:center'>Test run sheet manager</p>", unsafe_allow_html=True
        )
        with st.form("login"):
            user = st.text_input("Username")
            pwd = st.text_input("Password", type="password")
            ok = st.form_submit_button("Login", use_container_width=True)
        if ok:
            if check_login(user.strip(), pwd):
                st.session_state.logged_in = True
                st.session_state.user = user.strip()
                st.rerun()
            else:
                st.error("Invalid username or password.")


# ------------------------------------------------------------------ helpers
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()


def need_data() -> bool:
    if st.session_state.get("df") is None:
        st.warning("Please upload an Excel sheet first (Option 1).")
        return False
    return True


# ------------------------------------------------------------------ option 1
def page_upload():
    st.header("1. Upload Excel sheet")
    file = st.file_uploader("Choose test run sheet", type=["xlsx", "xls", "csv"])
    if not file:
        return
    try:
        if file.name.lower().endswith(".csv"):
            df = pd.read_csv(file)
        else:
            xls = pd.ExcelFile(file)
            sheet = st.selectbox("Sheet", xls.sheet_names)
            df = xls.parse(sheet)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not read file: {exc}")
        return

    st.session_state.df = df
    st.session_state.file_name = file.name
    st.success(f"Loaded {len(df)} rows and {len(df.columns)} columns from {file.name}")
    st.dataframe(df, use_container_width=True)


# ------------------------------------------------------------------ option 2
def page_analysis():
    st.header("2. Test case count, duplicates and VLOOKUP")
    if not need_data():
        return
    df: pd.DataFrame = st.session_state.df

    tab_count, tab_dup, tab_lookup = st.tabs(["Total count", "Find & remove duplicates", "VLOOKUP"])

    # ---- total count
    with tab_count:
        id_col = st.selectbox("Test case ID / name column", df.columns, key="count_col")
        total_rows = len(df)
        total_cases = df[id_col].notna().sum()
        unique_cases = df[id_col].dropna().nunique()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total rows", total_rows)
        c2.metric("Total test cases", int(total_cases))
        c3.metric("Unique test cases", int(unique_cases))

        st.subheader("Verify / status summary")
        status_col = st.selectbox(
            "Status column (e.g. Result, Verdict, Status)", ["(none)"] + list(df.columns)
        )
        if status_col != "(none)":
            summary = df[status_col].fillna("(blank)").value_counts().reset_index()
            summary.columns = [status_col, "Count"]
            st.dataframe(summary, use_container_width=True)
            st.bar_chart(summary.set_index(status_col))

    # ---- duplicates
    with tab_dup:
        cols = st.multiselect(
            "Columns that define a duplicate (empty = whole row)", list(df.columns)
        )
        subset = cols or None
        keep = st.radio("Keep", ["first", "last"], horizontal=True)
        dup_mask = df.duplicated(subset=subset, keep=keep)
        dup_count = int(dup_mask.sum())
        clean = df.drop_duplicates(subset=subset, keep=keep)

        c1, c2, c3 = st.columns(3)
        c1.metric("Rows before", len(df))
        c2.metric("Duplicates found", dup_count)
        c3.metric("Rows after removal", len(clean))

        if dup_count:
            with st.expander("Show duplicate rows"):
                st.dataframe(df[dup_mask], use_container_width=True)
        if st.button("Remove duplicates and apply"):
            st.session_state.df = clean.reset_index(drop=True)
            st.success(f"Removed {dup_count} duplicate rows. Sheet now has {len(clean)} rows.")
        st.download_button(
            "Download cleaned sheet",
            to_excel_bytes(clean),
            file_name="cleaned_" + os.path.splitext(st.session_state.file_name)[0] + ".xlsx",
        )

    # ---- vlookup
    with tab_lookup:
        st.write("Look up values from a second sheet, like Excel VLOOKUP.")
        lk_file = st.file_uploader("Lookup sheet", type=["xlsx", "xls", "csv"], key="lookup")
        if lk_file:
            try:
                if lk_file.name.lower().endswith(".csv"):
                    lk = pd.read_csv(lk_file)
                else:
                    lx = pd.ExcelFile(lk_file)
                    lk = lx.parse(st.selectbox("Lookup sheet tab", lx.sheet_names))
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not read lookup file: {exc}")
                return
            main_key = st.selectbox("Key column in main sheet", df.columns)
            lk_key = st.selectbox("Key column in lookup sheet", lk.columns)
            ret_cols = st.multiselect(
                "Column(s) to bring back", [c for c in lk.columns if c != lk_key]
            )
            if ret_cols:
                lk_small = lk[[lk_key] + ret_cols].drop_duplicates(subset=lk_key, keep="first")
                merged = df.merge(
                    lk_small, how="left", left_on=main_key, right_on=lk_key, suffixes=("", "_lookup")
                )
                found = merged[ret_cols[0] if ret_cols[0] in merged else ret_cols[0] + "_lookup"].notna().sum()
                c1, c2 = st.columns(2)
                c1.metric("Matched", int(found))
                c2.metric("Not found (#N/A)", len(merged) - int(found))
                st.dataframe(merged, use_container_width=True)
                st.download_button("Download VLOOKUP result", to_excel_bytes(merged),
                                   file_name="vlookup_result.xlsx")


# ------------------------------------------------------------------ option 3
def page_cb_upload():
    st.header("3. Upload test run sheet to CB (Codebeamer)")
    if not need_data():
        return
    df: pd.DataFrame = st.session_state.df

    with st.form("cb"):
        base_url = st.text_input("CB base URL", placeholder="https://codebeamer.company.com/cb")
        tracker_id = st.text_input("Tracker ID")
        c1, c2 = st.columns(2)
        cb_user = c1.text_input("CB username")
        cb_pass = c2.text_input("CB password / API token", type="password")
        name_col = st.selectbox("Column used as item Name", df.columns)
        desc_cols = st.multiselect("Columns added to Description", [c for c in df.columns if c != name_col])
        dry_run = st.checkbox("Dry run (do not send, only preview)", value=True)
        go = st.form_submit_button("Start upload")

    if not go:
        return
    if not (base_url and tracker_id and cb_user and cb_pass) and not dry_run:
        st.error("Fill in all CB connection fields.")
        return

    url = f"{base_url.rstrip('/')}/rest/v3/trackers/{tracker_id}/items"
    bar = st.progress(0.0)
    ok, failed, errors = 0, 0, []

    for i, (_, row) in enumerate(df.iterrows(), start=1):
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
                    errors.append({"row": i, "status": r.status_code, "response": r.text[:200]})
            except requests.RequestException as exc:
                failed += 1
                errors.append({"row": i, "status": "error", "response": str(exc)})
        bar.progress(i / len(df))

    c1, c2 = st.columns(2)
    c1.metric("Uploaded" if not dry_run else "Would upload", ok)
    c2.metric("Failed", failed)
    if errors:
        st.dataframe(pd.DataFrame(errors), use_container_width=True)
    if dry_run:
        st.info("Dry run only. Untick 'Dry run' to send the data to CB.")
        st.json({"url": url, "example_payload": payload})


# ------------------------------------------------------------------ main
def dashboard():
    with st.sidebar:
        st.markdown(f"## 🚀 {APP_NAME}")
        st.write(f"Signed in as **{st.session_state.user}**")
        choice = st.radio(
            "Menu",
            ["Dashboard", "1. Upload Excel", "2. Count / Duplicates / VLOOKUP", "3. Upload to CB"],
        )
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()

    if choice == "Dashboard":
        st.title(f"{APP_NAME} Dashboard")
        df = st.session_state.get("df")
        c1, c2, c3 = st.columns(3)
        c1.metric("Sheet loaded", st.session_state.get("file_name", "None"))
        c2.metric("Rows", 0 if df is None else len(df))
        c3.metric("Columns", 0 if df is None else len(df.columns))
        st.markdown("### Choose an option from the left menu")
        a, b, c = st.columns(3)
        a.markdown("<div class='card'><h3>1. Upload Excel</h3><p>Load your test run sheet.</p></div>", unsafe_allow_html=True)
        b.markdown("<div class='card'><h3>2. Analysis</h3><p>Test case count, duplicates, VLOOKUP.</p></div>", unsafe_allow_html=True)
        c.markdown("<div class='card'><h3>3. Upload to CB</h3><p>Push the sheet to Codebeamer.</p></div>", unsafe_allow_html=True)
    elif choice.startswith("1"):
        page_upload()
    elif choice.startswith("2"):
        page_analysis()
    else:
        page_cb_upload()


if st.session_state.get("logged_in"):
    dashboard()
else:
    login_page()
