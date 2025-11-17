import os
import io
import json
import uuid
import base64
import tempfile
from datetime import datetime, date
from typing import Dict, Any, List

import streamlit as st
from PIL import Image
import matplotlib.pyplot as plt
import pandas as pd
from fpdf import FPDF  # fpdf2
import google.generativeai as genai
import requests
from streamlit_lottie import st_lottie


st.set_page_config(
    page_title="EcoVision • Smart Waste Analyzer",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
body {
  background: linear-gradient(-45deg, #0ea5e9, #22c55e, #4ade80, #2dd4bf);
  background-size: 400% 400%;
  animation: gradientMove 12s ease infinite;
}
@keyframes gradientMove {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
.ecov-card {
  border-radius: 1.25rem;
  padding: 1.25rem;
  box-shadow: 0 10px 25px rgba(0,0,0,0.08);
  background: rgba(255,255,255,0.15);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255,255,255,0.25);
  color: #f8fafc;
}
.ecov-gradient {
  background: linear-gradient(135deg, #ffffff, #d1fae5, #a5f3fc);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.ecov-subtle { color:#e2e8f0 }
</style>
""", unsafe_allow_html=True)

# =====================================================
# Constants & Storage
# =====================================================
STATS_FILE = "ecovision_stats.json"
FONTS_DIR = "fonts"
UNICODE_FONT_PATH = os.path.join(FONTS_DIR, "DejaVuSans.ttf")

# PDF layout constants (mm)
PAGE_W = 210.0
PAGE_H = 297.0
MARGIN = 15.0
EFF_W = PAGE_W - 2 * MARGIN

IMPACT_LABELS: List[str] = [
    "Greenhouse Emissions",
    "Soil Contamination",
    "Water Pollution",
    "Energy Use",
]

ECO_TIPS = [
    "Carry a reusable bottle and refill instead of buying plastic.",
    "Keep separate bins for dry and wet waste to boost recycling quality.",
    "Say no to single-use cutlery—travel with a compact reusable set.",
    "Compost your kitchen scraps to cut methane from landfills.",
    "Buy in bulk and choose minimal packaging to reduce waste.",
    "Fix and reuse glass jars as storage containers.",
    "Switch to rechargeable batteries to cut e-waste.",
    "Donate old electronics to certified e-waste recyclers.",
    "Bring your own shopping bag—avoid plastic carry bags.",
    "Use cloth towels instead of paper for everyday cleaning."
]

def eco_tip_of_the_day() -> str:
    idx = date.today().toordinal() % len(ECO_TIPS)
    return ECO_TIPS[idx]

@st.cache_data(show_spinner=False)
def load_stats() -> Dict[str, Any]:
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"history": []}
    return {"history": []}

def save_stats(data: Dict[str, Any]):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        load_stats.clear()  # bust cache
    except Exception as e:
        st.warning(f"Couldn't save stats: {e}")

if "history" not in st.session_state:
    st.session_state.history = load_stats().get("history", [])


def load_lottie_url(url: str):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None

def load_lottie_any(urls: List[str]):
    for u in urls:
        data = load_lottie_url(u)
        if data:
            return data
    return None

def fig_pie_impact(impact: Dict[str, float]) -> bytes:
    sizes = [max(0, float(impact.get(k, 0))) for k in IMPACT_LABELS]
    s = sum(sizes)
    if s <= 0:
        sizes = [25, 25, 25, 25]
    fig, ax = plt.subplots(figsize=(4.5, 4.5), dpi=170)
    ax.pie(sizes, startangle=90, autopct='%1.1f%%')
    ax.axis('equal')
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.read()

def _register_unicode_font(pdf: FPDF) -> bool:
    """
    Registers a Unicode TTF font (DejaVuSans). Returns True if added, else False.
    """
    if os.path.exists(UNICODE_FONT_PATH):
        pdf.add_font("DejaVu", "", UNICODE_FONT_PATH, uni=True)
        pdf.set_font("DejaVu", "", 12)
        return True
    return False

def store_result(image_bytes: bytes, result: Dict[str, Any]) -> Dict[str, Any]:
    rec_id = str(uuid.uuid4())
    ts = datetime.now().isoformat(timespec='seconds')
    entry = {
        "id": rec_id,
        "timestamp": ts,
        "category": result.get("category", "mixed"),
        "confidence": result.get("confidence", 0.0),
        "disposal_steps": result.get("disposal_steps", []),
        "impact_breakdown": result.get("impact_breakdown", {}),
        "notes": result.get("notes", ""),
        "image_b64": base64.b64encode(image_bytes).decode("utf-8"),
    }
    st.session_state.history.insert(0, entry)
    save_stats({"history": st.session_state.history})
    return entry


API_KEY = os.getenv("GEMINI_API_KEY", "")
if API_KEY:
    genai.configure(api_key=API_KEY)

def call_gemini_for_waste(image: Image.Image) -> Dict[str, Any]:
    """Ask Gemini to classify waste, give disposal steps and impact split. Returns a dict."""
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = (
        "You are EcoVision, an environmental waste expert. "
        "Given an image of waste, output STRICT JSON with keys: "
        "category(one of: organic, plastic, paper, metal, glass, e-waste, textile, hazardous, mixed), "
        "confidence(0-1), disposal_steps(array of 3-6 short imperative steps), "
        "impact_breakdown(object with keys 'Greenhouse Emissions','Soil Contamination','Water Pollution','Energy Use' each 0-100 summing to 100), "
        "notes(short string <= 180 chars). Return ONLY JSON."
    )

    resp = model.generate_content([image, prompt])
    text = (resp.text or "").strip()

    # Extract JSON
    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1:
        raise RuntimeError(f"Gemini did not return JSON. Raw: {text[:200]}")
    data = json.loads(text[first:last + 1])

    # Normalize and clamp
    imp = data.get("impact_breakdown", {})
    total = sum(float(imp.get(k, 0)) for k in IMPACT_LABELS) or 1
    data["impact_breakdown"] = {k: round(float(imp.get(k, 0)) * 100 / total, 1) for k in IMPACT_LABELS}
    data["category"] = str(data.get("category", "mixed")).lower()
    data["confidence"] = float(data.get("confidence", 0.55))
    data["disposal_steps"] = list(data.get("disposal_steps", []))[:6]
    data["notes"] = str(data.get("notes", ""))[:180]
    return data 

def _safe_cell(pdf: FPDF, txt: str, h: float = 8, ln: int = 1, font_name: str = "Helvetica", font_size: int = 12, color=(0,0,0)):
    pdf.set_x(MARGIN)
    pdf.set_font(font_name, "", font_size)
    pdf.set_text_color(*color)
    pdf.cell(EFF_W, h, txt, ln=ln)

def _safe_multicell(pdf: FPDF, txt: str, h: float = 7, font_name: str = "Helvetica", font_size: int = 12, color=(0,0,0)):
    pdf.set_x(MARGIN)
    pdf.set_font(font_name, "", font_size)
    pdf.set_text_color(*color)
    pdf.multi_cell(EFF_W, h, txt)

def _place_two_images(pdf: FPDF, img1_path: str, img2_path: str, w1: float, w2: float, gutter: float = 6.0):
    """
    Place two images side-by-side within margins, keeping aspect ratio.
    Advances Y to the maximum of the two heights + padding.
    """
    with Image.open(img1_path) as im1:
        i1w, i1h = im1.size
    with Image.open(img2_path) as im2:
        i2w, i2h = im2.size

    h1 = w1 * (i1h / i1w)
    h2 = w2 * (i2h / i2w)

    if (w1 + gutter + w2) > EFF_W:
        scale = EFF_W / (w1 + gutter + w2)
        w1 *= scale; w2 *= scale; h1 *= scale; h2 *= scale

    x1 = MARGIN
    x2 = MARGIN + w1 + gutter
    y = pdf.get_y()

    pdf.image(img1_path, x=x1, y=y, w=w1)
    pdf.image(img2_path, x=x2, y=y, w=w2)

    pdf.set_y(y + max(h1, h2) + 5.0)
    pdf.set_x(MARGIN)

def make_pdf_report(record: Dict[str, Any], pie_png: bytes, title: str = "EcoVision Report") -> bytes:
    pdf = FPDF(unit="mm", format="A4")
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.set_auto_page_break(auto=True, margin=MARGIN)
    unicode_ok = _register_unicode_font(pdf)
    font_name = "DejaVu" if unicode_ok else "Helvetica"

    pdf.add_page()

    # Header
    _safe_cell(pdf, (title if unicode_ok else title.replace("•", "-")), h=10, ln=1, font_name=font_name, font_size=20, color=(0,0,0))
    _safe_cell(pdf, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", h=8, ln=1, font_name=font_name, font_size=11, color=(100,100,100))
    pdf.ln(2)

    # Side-by-side images inside margins
    with tempfile.TemporaryDirectory() as td:
        waste_img_path = os.path.join(td, "waste.png")
        pie_img_path = os.path.join(td, "pie.png")

        with open(waste_img_path, "wb") as f:
            f.write(base64.b64decode(record["image_b64"]))
        with open(pie_img_path, "wb") as f:
            f.write(pie_png)

        # Safe widths that always fit: 72 + 6 + 72 = 150 ≤ 180 (effective)
        _place_two_images(pdf, waste_img_path, pie_img_path, w1=72.0, w2=72.0, gutter=6.0)

    # Analysis Summary
    _safe_cell(pdf, "Analysis Summary", h=9, ln=1, font_name=font_name, font_size=14)
    sep = " • " if unicode_ok else " - "
    cat_text = record.get('category', '-').title()
    conf_text = f"{round(record.get('confidence', 0) * 100, 1)}%"
    _safe_cell(pdf, f"Category: {cat_text}{sep}Confidence: {conf_text}", h=8, ln=1, font_name=font_name, font_size=12)
    notes = record.get("notes", "-");  notes = notes if unicode_ok else notes.replace("•", "-")
    _safe_multicell(pdf, f"Notes: {notes}", h=7, font_name=font_name, font_size=12)

    # What Image Shows
    pdf.ln(1)
    _safe_cell(pdf, "What This Image Shows:", h=8, ln=1, font_name=font_name, font_size=13)
    _safe_multicell(
        pdf,
        f"This appears to show {record.get('category','mixed')} waste. "
        f"The materials visible require proper sorting and handling to prevent contamination.",
        h=7, font_name=font_name, font_size=12
    )

    # How to Recycle / Dispose
    pdf.ln(1)
    _safe_cell(pdf, "How to Recycle / Dispose It:", h=8, ln=1, font_name=font_name, font_size=13)
    for i, step in enumerate(record.get("disposal_steps", []), start=1):
        s = step if unicode_ok else step.replace("•", "-")
        _safe_multicell(pdf, f"{i}. {s}", h=7, font_name=font_name, font_size=12)

    # Harmful Effects
    pdf.ln(1)
    _safe_cell(pdf, "Why Improper Disposal Is Harmful:", h=8, ln=1, font_name=font_name, font_size=13)
    _safe_multicell(
        pdf,
        "Improper disposal can contaminate soil and water, attract pests, "
        "release greenhouse gases and toxins, and harm local ecosystems and health.",
        h=7, font_name=font_name, font_size=12
    )

    # Eco Tip of the Day
    pdf.ln(1)
    _safe_cell(pdf, "Eco Tip of the Day:", h=8, ln=1, font_name=font_name, font_size=13)
    _safe_multicell(pdf, eco_tip_of_the_day(), h=7, font_name=font_name, font_size=12)

    # Impact Breakdown
    pdf.ln(1)
    _safe_cell(pdf, "Impact Breakdown (%):", h=8, ln=1, font_name=font_name, font_size=13)
    for k in IMPACT_LABELS:
        v = record.get("impact_breakdown", {}).get(k, 0)
        _safe_cell(pdf, f"- {k}: {v}%", h=7, ln=1, font_name=font_name, font_size=12)

    # Footer
    pdf.ln(5)
    pdf.set_y(PAGE_H - MARGIN + 2)
    pdf.set_x(MARGIN)
    footer = "EcoVision • Automated insight. Human responsibility."
    if not unicode_ok:
        footer = footer.replace("•", "-")
    _safe_cell(pdf, footer, h=8, ln=1, font_name=font_name, font_size=10, color=(120,120,120))


    result = pdf.output(dest="S")
    if isinstance(result, (bytes, bytearray)):
        return bytes(result)
    elif isinstance(result, str):
        return result.encode("latin-1", errors="ignore")
    else:
        raise TypeError(f"Unexpected PDF output type: {type(result)}")


left, right = st.columns([0.65, 0.35])
with left:
    st.markdown("<h1 class='ecov-gradient'>EcoVision</h1>", unsafe_allow_html=True)
    st.caption("AI-powered waste analysis & eco guidance")
with right:
    st.markdown("<div class='ecov-card'>", unsafe_allow_html=True)
    st.metric("Analyses", len(st.session_state.history))
    cats_series = (
        pd.Series([h["category"] for h in st.session_state.history]).value_counts()
        if st.session_state.history else pd.Series(dtype=int)
    )
    if not cats_series.empty:
        st.metric("Top Category", f"{cats_series.index[0].title()} ({int(cats_series.iloc[0])})")
    else:
        st.metric("Top Category", "—")
    st.markdown("</div>", unsafe_allow_html=True)


section = st.sidebar.radio(
    "Navigate",
    ("About", "Waste Analyser", "Download Report", "Dashboard"),
    index=0,
)


LOTTIE_URLS = {
    "about": [
        "https://lottie.host/9ed0e12e-72f5-41b2-8c8d-f5df653ae444/2xhpMZgMuR.json",  # Earth
        "https://assets9.lottiefiles.com/packages/lf20_tutvdkg0.json",               # Nature
        "https://assets10.lottiefiles.com/packages/lf20_u4yrau.json",               # Recycling
    ],
    "analyser": [
        "https://assets2.lottiefiles.com/packages/lf20_msdmfngy.json",
        "https://assets9.lottiefiles.com/packages/lf20_u4yrau.json",
    ],
    "report": [
        "https://assets9.lottiefiles.com/packages/lf20_1pxqjqps.json",
        "https://assets9.lottiefiles.com/packages/lf20_tutvdkg0.json",
    ],
    "dashboard": [
        "https://assets2.lottiefiles.com/private_files/lf30_editor_kq3z0q.json",
        "https://assets2.lottiefiles.com/packages/lf20_msdmfngy.json",
    ],
}


if section == "About":
    st.markdown(
        """
        ### Why EcoVision?
        EcoVision helps you understand **what kind of waste** you're dealing with and how to **dispose of it responsibly**.
        Upload a photo, and our AI (Google Gemini) will classify the waste, estimate its **environmental impact**, and provide **step-by-step disposal guidance**.
        """
    )

    # --- Lottie in the middle ---
    earth_anim = load_lottie_any(LOTTIE_URLS["about"])
    if earth_anim:
        st_lottie(earth_anim, height=360)
    else:
        st.info("Animation unavailable right now. (Network blocked or URL down.)")

    st.markdown(
        """
        **Key features**
        - Smart image-based waste classification  
        - Impact pie chart (emissions, soil, water, energy)  
        - Actionable disposal steps  
        - One-click PDF report  
        - Dashboard of recent analyses
        """
    )

elif section == "Waste Analyser":
    up = st.file_uploader(
        "Upload a clear photo of the waste",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=False,
    )

    col1, col2 = st.columns([0.55, 0.45])

    with col1:
        if up:
            img = Image.open(up).convert("RGB")
            st.image(img, caption="Uploaded image", use_container_width=True)
        else:
            st.write("\n")
            st.markdown("<div class='ecov-subtle'>No image uploaded yet.</div>", unsafe_allow_html=True)

        # --- Lottie in the middle of the section (left column) ---
        ana_anim = load_lottie_any(LOTTIE_URLS["analyser"])
        if ana_anim:
            st_lottie(ana_anim, height=260)

    with col2:
        st.markdown("<div class='ecov-card'>", unsafe_allow_html=True)
        st.subheader("AI Analysis")
        analyze_clicked = st.button("Analyze with Gemini", use_container_width=True, disabled=not up)
        if analyze_clicked and up:
            try:
                with st.spinner("Analyzing with Gemini 2.5 Flash…"):
                    result = call_gemini_for_waste(img)
                    pie_png = fig_pie_impact(result.get("impact_breakdown", {}))
                    buf = io.BytesIO(); img.save(buf, format="PNG")
                    record = store_result(buf.getvalue(), result)
                st.success("Analysis complete.")
                st.session_state["last_result"] = record
                st.session_state["last_pie"] = pie_png
            except Exception as e:
                st.error(f"Analysis failed: {e}")

        if "last_result" in st.session_state:
            rec = st.session_state["last_result"]
            st.markdown(f"**Category:** {rec['category'].title()}")
            st.markdown(f"**Confidence:** {round(rec['confidence']*100,1)}%")
            if rec.get("notes"):
                st.caption(rec["notes"])

            st.markdown("### What this image shows")
            st.write(
                f"This appears to show **{rec['category']}** waste. "
                f"Sort it correctly to prevent contamination and improve recycling quality."
            )

            st.markdown("### How to recycle / dispose it")
            for i, step in enumerate(rec.get("disposal_steps", []), start=1):
                st.markdown(f"{i}. {step}")

            st.markdown("### Why not to spread it (harmful effects)")
            st.write(
                "Improper disposal can contaminate soil and water, attract pests, "
                "release toxins and greenhouse gases, and harm local ecosystems and health."
            )

            st.markdown("### Eco Tip of the Day")
            st.info(eco_tip_of_the_day())

            st.image(st.session_state["last_pie"], caption="Impact breakdown", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

elif section == "Download Report":
    st.subheader("Download Report")

    
    rep_anim = load_lottie_any(LOTTIE_URLS["report"])
    if rep_anim:
        st_lottie(rep_anim, height=300)

    if not st.session_state.history:
        st.warning("No analyses yet. Go to 'Waste Analyser' first.")
    else:
        options = {f"{h['timestamp']} • {h['category'].title()}": i for i, h in enumerate(st.session_state.history)}
        sel = st.selectbox("Select an analysis", list(options.keys()))
        rec = st.session_state.history[options[sel]]
        pie_png = fig_pie_impact(rec.get("impact_breakdown", {}))
        try:
            pdf_bytes = make_pdf_report(rec, pie_png)
            st.download_button(
                label="Download PDF Report",
                data=pdf_bytes,
                file_name=f"EcoVision_{rec['timestamp'].replace(':','-')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"PDF creation failed: {e}")
        st.image(pie_png, caption="Impact breakdown", use_container_width=True)
        st.write("\n")
        st.json({k: rec[k] for k in ["category", "confidence", "notes"]})


else:
    st.subheader("Dashboard")

    dash_anim = load_lottie_any(LOTTIE_URLS["dashboard"])
    if dash_anim:
        st_lottie(dash_anim, height=300)

    if not st.session_state.history:
        st.info("No data yet. Run an analysis first.")
    else:
        df = pd.DataFrame([
            {
                "Timestamp": h["timestamp"],
                "Category": h["category"].title(),
                "Confidence %": round(h["confidence"] * 100, 1),
                **{k: h["impact_breakdown"].get(k, 0) for k in IMPACT_LABELS},
            }
            for h in st.session_state.history
        ])

        # Filters
        c1, c2 = st.columns([0.7, 0.3])
        with c1:
            st.subheader("Recent Analyses")
        with c2:
            cats = sorted(df["Category"].unique())
            cat_filter = st.multiselect("Filter by category", cats, default=cats)
        dff = df[df["Category"].isin(cat_filter)]

        st.dataframe(dff, use_container_width=True, hide_index=True)

        counts = dff["Category"].value_counts().sort_index()
        if not counts.empty:
            fig, ax = plt.subplots(figsize=(7, 3.5), dpi=160)
            ax.bar(counts.index, counts.values)
            ax.set_title("Analyses by Category")
            ax.set_ylabel("Count")
            ax.set_xlabel("")
            plt.xticks(rotation=25)
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

        st.caption("Data is stored locally in ecovision_stats.json.")
