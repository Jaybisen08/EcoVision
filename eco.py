import streamlit as st
from PIL import Image
import io, os, json, requests
from datetime import datetime
import matplotlib.pyplot as plt
from fpdf import FPDF
import numpy as np
import google.generativeai as genai
from streamlit_lottie import st_lottie

STATS_FILE = "ecovision_stats.json"
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    st.warning("⚠️ Gemini API key not found. Set it as environment variable: GEMINI_API_KEY.")
else:
    genai.configure(api_key=API_KEY)

def load_lottie_url(url):
    try:
        r = requests.get(url)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    return []

def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

def image_to_pil(uploaded_file):
    try:
        img = Image.open(uploaded_file).convert("RGB")
        return img
    except Exception as e:
        st.error(f"Error opening image: {e}")
        return None

def green_score_from_image(pil_img):
    arr = np.array(pil_img)
    r, g, b = arr[:,:,0]/255.0, arr[:,:,1]/255.0, arr[:,:,2]/255.0
    green_mask = (g > 0.35) & (g > r + 0.06) & (g > b + 0.06)
    green_ratio = green_mask.mean()
    score = int(min(100, max(0, round(green_ratio * 140))))
    return score, green_ratio

def create_donut_chart(score):
    fig, ax = plt.subplots(figsize=(4,4))
    sizes = [score, 100 - score]
    ax.pie(sizes, startangle=90, wedgeprops=dict(width=0.35))
    ax.set_aspect('equal')
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf

def generate_certificate(name, event_text, score):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 12, "Certificate of Participation", ln=1, align='C')
    pdf.ln(6)
    pdf.set_font("Arial", '', 14)
    pdf.multi_cell(0, 8, f"This is to certify that {name} has participated in {event_text}.")
    pdf.ln(6)
    pdf.set_font("Arial", '', 12)
    pdf.multi_cell(0, 7, f"Eco Vision Score: {score} / 100")
    pdf.ln(12)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 6, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=1)
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    pdf_buffer = io.BytesIO(pdf_bytes)
    return pdf_buffer

def ai_feedback_gemini(score, ratio, context):
    if not API_KEY:
        return "Gemini API key missing. Please configure GEMINI_API_KEY."
    prompt = f"You are an environmental analysis expert. Based on an eco score of {score} and a green ratio of {ratio:.3f}, give concise feedback and suggestions for improvement. Context: {context}."
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error using Gemini API: {e}"

page_bg = """
<style>
[data-testid="stAppViewContainer"] {
background: linear-gradient(120deg, #d9f2d9, #b2dfb2, #a6e3b0);
background-attachment: fixed;
}
[data-testid="stSidebar"] {
background: #1b4332;
color: #f1f8e9;
border-right: 2px solid #74c69d;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
color: #f1f8e9 !important;
}
</style>
"""
st.markdown(page_bg, unsafe_allow_html=True)
st.set_page_config(page_title="Eco Vision 🌱", page_icon="🌿", layout="wide")

st.sidebar.title("🌿 Eco Vision Menu")
page = st.sidebar.radio("Navigate to:", ["About", "Analyzer", "Download Your Report", "Dashboard"])
user_name = st.sidebar.text_input("👤 Your Name", value="Guest")
event_text = st.sidebar.text_input("📝 Event / Context", value="Eco Vision Analysis")
enable_pdf = st.sidebar.checkbox("📜 Generate Certificate PDF", value=True)

if page == "About":
    st.title("🌍 Eco Vision — Simple Environmental Image Analyzer")
    st.markdown("""
    **Eco Vision** uses AI and image analysis to estimate how “green” an environment is based on an uploaded image.  
    Whether it's a park, rooftop, or satellite photo — you’ll receive a quick eco score and insights.
    """)
    lottie_about = load_lottie_url("https://assets1.lottiefiles.com/packages/lf20_8wREpI.json")
    if lottie_about:
        st_lottie(lottie_about, height=300, key="about_anim")
    st.markdown("""
    ### ✨ Features
    - AI-powered environmental feedback (Gemini 1.5 Flash)
    - Real-time eco scoring
    - Visual reports and downloadable PDFs
    - Nature-inspired interface
    - Tracks previous analyses
    """)

elif page == "Analyzer":
    st.title("🔍 Environmental Analyzer")
    st.markdown("Upload an image (JPG, PNG) to analyze its green coverage:")
    uploaded = st.file_uploader("📤 Upload Image", type=["jpg", "jpeg", "png"])
    if uploaded:
        img = image_to_pil(uploaded)
        if img:
            st.image(img, caption="Uploaded Image", use_container_width=True)
            with st.spinner("Analyzing environmental health..."):
                score, green_ratio = green_score_from_image(img)
            st.subheader(f"🌱 Eco Score: {score} / 100")
            st.caption(f"🌿 Green pixel ratio: {green_ratio:.3f}")
            chart_buf = create_donut_chart(score)
            st.image(chart_buf, caption="Eco Score (Donut Chart)", use_container_width=True)
            st.markdown("### 🌍 AI Recommendations")
            feedback = ai_feedback_gemini(score, green_ratio, event_text)
            st.success(feedback)
            stats = load_stats()
            stats.append({
                "name": user_name,
                "timestamp": datetime.now().isoformat(),
                "score": score,
                "green_ratio": green_ratio,
                "event": event_text
            })
            save_stats(stats)
            st.session_state['latest_score'] = score
            st.session_state['chart'] = chart_buf
    else:
        st.info("📸 Upload an image to start analysis.")

elif page == "Download Your Report":
    st.title("📄 Download Your Report")
    if 'latest_score' in st.session_state:
        score = st.session_state['latest_score']
        chart_buf = st.session_state['chart']
        st.image(chart_buf, caption="Your Eco Vision Chart", use_container_width=True)
        if enable_pdf:
            pdf_bytes = generate_certificate(user_name, event_text, score)
            st.download_button(
                "📜 Download Certificate (PDF)",
                data=pdf_bytes.getvalue(),
                file_name=f"EcoVision_Report_{user_name.replace(' ', '_')}.pdf",
                mime="application/pdf"
            )
        st.download_button(
            "📊 Download Chart (PNG)",
            data=chart_buf.getvalue(),
            file_name="EcoVision_Chart.png",
            mime="image/png"
        )
    else:
        st.warning("⚠️ No analysis data available. Run the Analyzer first!")

elif page == "Dashboard":
    st.title("📊 Eco Vision Dashboard")
    stats = load_stats()
    if stats:
        st.write("### Recent Analyses 🕒")
        for s in reversed(stats[-8:]):
            st.write(f"{s['timestamp']} — {s['name']} — Score: {s['score']} — {s['event']}")
    else:
        st.info("No analyses yet. Run the Analyzer to generate results!")
    st.markdown("---")
    st.caption("💚 Built with Streamlit and Google Gemini AI — for a greener planet 🌍")
