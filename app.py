import os
import re
import time
import google.generativeai as genai
import pandas as pd
from PIL import Image
import streamlit as st

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="UrjaMitra | National Solar & PM-KUSUM Copilot",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- DESIGNER CUSTOM CSS (FIXING HORIZONTAL OVERFLOW & STRETCHING) ---
st.markdown(
    """
<style>
    /* Prevent horizontal stretching & page overflow */
    .stApp {
        background: linear-gradient(180deg, #F8FAFC 0%, #EFF6FF 100%);
        color: #0F172A;
        overflow-x: hidden;
    }
    
    /* Constrain tables and text areas to avoid right-side blowout */
    table {
        width: 100% !important;
        table-layout: auto !important;
        word-break: break-word;
    }
    
    .element-container, .stMarkdown, .stTable, div[data-testid="stHorizontalBlock"] {
        max-width: 100%;
    }

    /* Hero Banner Styling */
    .hero-container {
        background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 60%, #047857 100%);
        padding: 24px 28px;
        border-radius: 16px;
        color: #FFFFFF;
        margin-bottom: 20px;
        box-shadow: 0 10px 25px -8px rgba(15, 23, 42, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-sizing: border-box;
    }
    .hero-badge {
        background: rgba(245, 158, 11, 0.2);
        border: 1px solid #F59E0B;
        color: #FCD34D;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        display: inline-block;
        margin-bottom: 8px;
    }
    .hero-title {
        font-size: 2.1rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
        color: #FFFFFF;
    }
    .hero-subtitle {
        font-size: 0.95rem;
        color: #E2E8F0;
        margin-top: 6px;
        font-weight: 400;
    }

    /* Custom KPI Metric Cards */
    .kpi-card {
        background: #FFFFFF;
        padding: 16px 18px;
        border-radius: 14px;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
        border: 1px solid #E2E8F0;
        border-top: 5px solid #F59E0B;
        box-sizing: border-box;
        height: 100%;
    }
    .kpi-card.green { border-top-color: #10B981; }
    .kpi-card.blue { border-top-color: #3B82F6; }
    .kpi-card.purple { border-top-color: #8B5CF6; }

    .kpi-title {
        font-size: 0.78rem;
        font-weight: 700;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: #0F172A;
        margin: 0;
        line-height: 1.2;
    }
    .kpi-sub {
        font-size: 0.78rem;
        font-weight: 600;
        color: #059669;
        margin-top: 6px;
    }

    /* Section Containers */
    .info-strip {
        background: #FFFFFF;
        border-left: 5px solid #0284C7;
        padding: 12px 16px;
        border-radius: 8px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.03);
        margin-bottom: 16px;
        font-size: 0.88rem;
        box-sizing: border-box;
    }

    /* Primary Action Buttons */
    div.stButton > button {
        background: linear-gradient(135deg, #059669 0%, #047857 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.55rem 1.2rem;
        font-weight: 700;
        font-size: 0.92rem;
        box-shadow: 0 4px 10px rgba(5, 150, 105, 0.2);
        width: 100%;
    }
    div.stButton > button:hover {
        background: linear-gradient(135deg, #047857 0%, #065F46 100%);
        color: #FFFFFF;
    }

    /* Tabs Polish */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #E2E8F0;
        padding: 4px;
        border-radius: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 8px 14px;
        font-weight: 700;
        font-size: 0.88rem;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# --- STATE-SPECIFIC DATABASE ---
STATE_DB = {
    "Haryana": {
        "discom": "DHBVN / UHBVN",
        "regulator": "HERC",
        "agri_agency": "HAREDA",
        "tariff": 6.75,
        "insolation": 4.6,
        "kusum_state_sub": 45,
    },
    "Rajasthan": {
        "discom": "JVVNL / AVVNL / JdVVNL",
        "regulator": "RERC",
        "agri_agency": "RRECL",
        "tariff": 7.50,
        "insolation": 5.1,
        "kusum_state_sub": 30,
    },
    "Uttar Pradesh": {
        "discom": "UPPCL",
        "regulator": "UPERC",
        "agri_agency": "UPNEDA",
        "tariff": 7.00,
        "insolation": 4.5,
        "kusum_state_sub": 30,
    },
    "Punjab": {
        "discom": "PSPCL",
        "regulator": "PSERC",
        "agri_agency": "PEDA",
        "tariff": 6.80,
        "insolation": 4.5,
        "kusum_state_sub": 30,
    },
    "Delhi": {
        "discom": "BSES / Tata Power",
        "regulator": "DERC",
        "agri_agency": "EE&REM Delhi",
        "tariff": 8.00,
        "insolation": 4.5,
        "kusum_state_sub": 30,
    },
    "Maharashtra": {
        "discom": "MSEDCL",
        "regulator": "MERC",
        "agri_agency": "MEDA",
        "tariff": 8.50,
        "insolation": 4.7,
        "kusum_state_sub": 30,
    },
    "Other": {
        "discom": "State DISCOM",
        "regulator": "SERC",
        "agri_agency": "SNA / MNRE",
        "tariff": 7.00,
        "insolation": 4.5,
        "kusum_state_sub": 30,
    },
}

configured_key = st.secrets.get("GEMINI_API_KEY", "")

# --- LANGUAGE SELECTOR ---
_, col_lang = st.columns([4, 1])
with col_lang:
  lang = st.selectbox(
      "🌐 भाषा / Language",
      ["English", "हिंदी (Hindi)"],
      label_visibility="collapsed",
  )

is_hindi = lang == "हिंदी (Hindi)"

# --- HERO BANNER ---
if is_hindi:
  st.markdown(
      """
    <div class="hero-container">
        <div class="hero-badge">🇮🇳 एमएनआरई (MNRE) एवं पीएम-कुसुम मानकों पर आधारित</div>
        <h1 class="hero-title">☀️ ऊर्जा मित्र (UrjaMitra)</h1>
        <p class="hero-subtitle">एआई-संचालित सोलर साइज़िंग, पीएम सूर्य घर एवं पीएम-कुसुम सब्सिडी, कोटेशन ऑडिट और डिस्कॉम नेट-मीटरिंग सहायक</p>
    </div>
    """,
      unsafe_allow_html=True,
  )
else:
  st.markdown(
      """
    <div class="hero-container">
        <div class="hero-badge">🇮🇳 Grounded in Official MNRE & State Discom Regulations</div>
        <h1 class="hero-title">☀️ UrjaMitra (ऊर्जा मित्र)</h1>
        <p class="hero-subtitle">Next-Gen Solar Engineering Copilot • PM Surya Ghar & PM-KUSUM Sizing • Multimodal Quote Auditor • Discom Legal Drafter</p>
    </div>
    """,
      unsafe_allow_html=True,
  )

# --- SIDEBAR INPUTS ---
st.sidebar.markdown(
    "### ⚙️ " + ("उपभोक्ता प्रोफ़ाइल" if is_hindi else "Consumer Profile")
)

if configured_key:
  api_key = configured_key
  st.sidebar.success(
      "🔑 "
      + (
          "API Key सुरक्षित रूप से जुड़ी है"
          if is_hindi
          else "API Key Connected Securely"
      )
  )
else:
  api_key = st.sidebar.text_input(
      "🔑 Enter Gemini API Key",
      type="password",
      help="Add GEMINI_API_KEY to Streamlit Secrets or enter here.",
  )

state = st.sidebar.selectbox("📍 राज्य / State", list(STATE_DB.keys()))
state_info = STATE_DB[state]

mode_options = (
    ["🏠 घरेलू रूफटॉप (PM Surya Ghar)", "🌾 कृषि सोलर पंप (PM-KUSUM)"]
    if is_hindi
    else [
        "🏠 Residential Rooftop (PM Surya Ghar)",
        "🌾 Agricultural Pump (PM-KUSUM)",
    ]
)
selected_mode = st.sidebar.radio(
    "⚡ कनेक्शन श्रेणी / Sector Mode", mode_options
)
is_agri = "PM-KUSUM" in selected_mode

st.sidebar.markdown("---")

if not is_agri:
  st.sidebar.markdown(
      "#### 🏠 " + ("घरेलू विवरण" if is_hindi else "Residential Parameters")
  )
  monthly_bill = st.sidebar.number_input(
      "औसत मासिक बिजली बिल (₹)" if is_hindi else "Avg. Monthly Power Bill (₹)",
      min_value=300,
      max_value=100000,
      value=2500,
      step=100,
  )
  roof_area = st.sidebar.number_input(
      "उपलब्ध छत क्षेत्रफल (वर्ग फुट)"
      if is_hindi
      else "Shadow-Free Roof Area (sq. ft.)",
      min_value=50,
      max_value=20000,
      value=350,
      step=50,
  )
  sanctioned_load = st.sidebar.number_input(
      "मौजूदा स्वीकृत लोड (kW)" if is_hindi else "Existing Sanctioned Load (kW)",
      min_value=1.0,
      max_value=50.0,
      value=2.0,
      step=1.0,
  )
else:
  st.sidebar.markdown(
      "#### 🌾 "
      + ("कृषि एवं सिंचाई विवरण" if is_hindi else "Agricultural & Pump Specs")
  )
  land_acres = st.sidebar.number_input(
      "सिंचित भूमि (एकड़)" if is_hindi else "Irrigated Farmland (Acres)",
      min_value=1.0,
      max_value=100.0,
      value=5.0,
      step=1.0,
  )
  water_depth = st.sidebar.slider(
      "भूजल स्तर की गहराई (फीट)" if is_hindi else "Water Table Depth (Feet)",
      min_value=20,
      max_value=400,
      value=120,
      step=10,
  )
  pump_type = st.sidebar.selectbox(
      "पंप प्रकार / Pump Type",
      [
          "Submersible DC (सबमर्सिबल डीसी)",
          "Submersible AC (सबमर्सिबल एसी)",
          "Surface Mono-block (सरफेस पंप)",
      ],
  )
  monthly_diesel_spend = st.sidebar.number_input(
      "मासिक डीजल/बिजली खर्च (₹)"
      if is_hindi
      else "Monthly Diesel/Power Spend (₹)",
      min_value=1000,
      max_value=100000,
      value=6000,
      step=500,
  )

st.sidebar.markdown("---")
st.sidebar.markdown(
    "#### 🔍 " + ("विक्रेता कोटेशन ऑडिट" if is_hindi else "Vendor Quote & OCR")
)
vendor_quote = st.sidebar.number_input(
    "विक्रेता द्वारा मांगा गया कुल मूल्य (₹)"
    if is_hindi
    else "Installer Quoted Total (₹)",
    min_value=0,
    value=0,
    step=5000,
)

uploaded_file = st.sidebar.file_uploader(
    "📸 कोटेशन या बिल का फोटो अपलोड करें"
    if is_hindi
    else "📸 Upload Quote / Bill Image (Optional)",
    type=["png", "jpg", "jpeg"],
)

# --- DETERMINISTIC ENGINE ---
if not is_agri:
  unit_rate = state_info["tariff"]
  daily_gen_per_kw = state_info["insolation"]
  est_monthly_units = monthly_bill / unit_rate
  req_kw = est_monthly_units / (daily_gen_per_kw * 30)

  max_kw_by_roof = roof_area / 95.0
  raw_kw = max(1.0, min(req_kw, max_kw_by_roof))

  if raw_kw < 1.5:
    display_kw = 1
    subsidy_amount = 30000
  elif raw_kw < 2.5:
    display_kw = 2
    subsidy_amount = 60000
  else:
    display_kw = min(10, int(round(raw_kw)))
    subsidy_amount = 78000

  bench_gross_cost = display_kw * 58000
  net_estimated_cost = max(0, bench_gross_cost - subsidy_amount)
  annual_units = round(display_kw * daily_gen_per_kw * 365)
  annual_savings = round(annual_units * unit_rate)
  payback_years = (
      round(net_estimated_cost / annual_savings, 1) if annual_savings > 0 else 0
  )
  co2_offset_tons = round(annual_units * 0.82 / 1000, 1)

  capacity_label = f"{display_kw} kW Rooftop"
  capacity_sub = f"Generates ~{round(display_kw * daily_gen_per_kw)} Units/Day"
  subsidy_sub = "Central MNRE Direct DBT"
  scheme_name = "PM Surya Ghar Muft Bijli Yojana"

else:
  if water_depth > 200 or land_acres > 10:
    recommended_hp = 10
    solar_kw = 10.0
    bench_gross_cost = 460000
  elif water_depth > 120 or land_acres > 6:
    recommended_hp = 7.5
    solar_kw = 7.5
    bench_gross_cost = 345000
  elif water_depth > 60 or land_acres > 3:
    recommended_hp = 5
    solar_kw = 5.0
    bench_gross_cost = 240000
  else:
    recommended_hp = 3
    solar_kw = 3.0
    bench_gross_cost = 155000

  display_kw = solar_kw
  total_sub_pct = 30 + state_info["kusum_state_sub"]
  subsidy_amount = round(bench_gross_cost * (total_sub_pct / 100.0))
  net_estimated_cost = max(0, bench_gross_cost - subsidy_amount)
  annual_savings = round(monthly_diesel_spend * 10)
  payback_years = (
      round(net_estimated_cost / annual_savings, 1) if annual_savings > 0 else 0
  )
  co2_offset_tons = round(recommended_hp * 1.4, 1)

  capacity_label = f"{recommended_hp} HP ({solar_kw} kW)"
  capacity_sub = f"Sufficient for {land_acres} Acres @ {water_depth}ft"
  subsidy_sub = f"{total_sub_pct}% Subsidy ({state_info['agri_agency']})"
  scheme_name = f"PM-KUSUM ({state_info['agri_agency']})"

# --- REGULATORY STRIP ---
st.markdown(
    f"""
<div class="info-strip">
    <b>🏛️ {"सक्रिय नियामक क्षेत्र" if is_hindi else "Active Jurisdiction"}:</b> {state} &nbsp;|&nbsp;
    <b>⚡ {"डिस्कॉम" if is_hindi else "Utility"}:</b> {state_info['discom']} ({state_info['regulator']}) &nbsp;|&nbsp;
    <b>☀️ {"सौर विकिरण" if is_hindi else "Solar Insolation"}:</b> {state_info['insolation']} kWh/kW/day &nbsp;|&nbsp;
    <b>📜 {"योजना" if is_hindi else "Active Scheme"}:</b> {scheme_name}
</div>
""",
    unsafe_allow_html=True,
)

# --- KPI CARDS ---
k1, k2, k3, k4 = st.columns(4)

with k1:
  st.markdown(
      f"""
    <div class="kpi-card">
        <div class="kpi-title">{"सुझाई गई क्षमता" if is_hindi else "Recommended System"}</div>
        <div class="kpi-value">{capacity_label}</div>
        <div class="kpi-sub">⚡ {capacity_sub}</div>
    </div>
    """,
      unsafe_allow_html=True,
  )

with k2:
  st.markdown(
      f"""
    <div class="kpi-card green">
        <div class="kpi-title">{"कुल सरकारी सब्सिडी" if is_hindi else "Eligible Govt Subsidy"}</div>
        <div class="kpi-value">₹{subsidy_amount:,}</div>
        <div class="kpi-sub">🏛️ {subsidy_sub}</div>
    </div>
    """,
      unsafe_allow_html=True,
  )

with k3:
  st.markdown(
      f"""
    <div class="kpi-card blue">
        <div class="kpi-title">{"आपकी शुद्ध लागत" if is_hindi else "Net Citizen Investment"}</div>
        <div class="kpi-value">₹{net_estimated_cost:,}</div>
        <div class="kpi-sub">💰 Benchmark: ₹{bench_gross_cost:,}</div>
    </div>
    """,
      unsafe_allow_html=True,
  )

with k4:
  st.markdown(
      f"""
    <div class="kpi-card purple">
        <div class="kpi-title">{"लागत वसूली समय" if is_hindi else "Payback & Eco Impact"}</div>
        <div class="kpi-value">{payback_years} {"वर्ष" if is_hindi else "Years"}</div>
        <div class="kpi-sub">🌱 Saves ₹{annual_savings:,}/yr • {co2_offset_tons}T CO₂</div>
    </div>
    """,
      unsafe_allow_html=True,
  )

st.write("")


# --- AI DISPATCHERS ---
def get_candidate_models(key: str):
  genai.configure(api_key=key)
  candidates = [
      "models/gemini-3.8-flash",
      "models/gemma-4-26b-a4b-it",
      "models/gemma-2-27b-it",
      "models/gemma-2-9b-it",
  ]
  try:
    for m in genai.list_models():
      if (
          "generateContent" in m.supported_generation_methods
          and "1.5" not in m.name
          and "2.5" not in m.name
          and m.name not in candidates
      ):
        candidates.append(m.name)
  except Exception:
    pass
  return candidates


def stream_ai_response(
    key: str, prompt, placeholder, status_box, pil_image=None
):
  candidates = get_candidate_models(key)
  last_err = None
  for model_name in candidates:
    try:
      display_name = model_name.replace("models/", "")
      status_box.info(f"⚡ AI Engine ({display_name}) analyzing...")
      model = genai.GenerativeModel(model_name)

      content_payload = [prompt, pil_image] if pil_image is not None else prompt
      response = model.generate_content(content_payload, stream=True)

      full_text = ""
      for chunk in response:
        if chunk.text:
          full_text += chunk.text
          placeholder.markdown(full_text)

      return full_text, display_name
    except Exception as e:
      err_str = str(e)
      last_err = e
      if (
          "429" in err_str
          or "404" in err_str
          or "image" in err_str.lower()
          or "multimodal" in err_str.lower()
      ):
        if pil_image is not None and "gemma" in model_name:
          try:
            response = model.generate_content(prompt, stream=True)
            full_text = ""
            for chunk in response:
              if chunk.text:
                full_text += chunk.text
                placeholder.markdown(full_text)
            return full_text, display_name
          except Exception:
            continue
        continue
      else:
        raise e
  raise last_err if last_err else RuntimeError("All available AI models busy.")


def generate_ai_text(key: str, prompt: str):
  candidates = get_candidate_models(key)
  last_err = None
  for model_name in candidates:
    try:
      display_name = model_name.replace("models/", "")
      model = genai.GenerativeModel(model_name)
      res = model.generate_content(prompt)
      return res.text, display_name
    except Exception as e:
      err_str = str(e)
      last_err = e
      if "429" in err_str or "404" in err_str:
        continue
      else:
        raise e
  raise last_err if last_err else RuntimeError("All available AI models busy.")


def extract_clean_letter(raw_text: str) -> str:
  matches = re.findall(r"<LETTER>([\s\S]*?)</LETTER>", raw_text, re.IGNORECASE)
  if matches:
    longest = max(matches, key=len).strip()
    if len(longest) > 150:
      return longest

  if "<LETTER>" in raw_text or "<letter>" in raw_text:
    parts = re.split(r"<LETTER>", raw_text, flags=re.IGNORECASE)
    last_part = parts[-1]
    if "</LETTER>" in last_part or "</letter>" in last_part:
      clean = re.split(r"</LETTER>", last_part, flags=re.IGNORECASE)[0].strip()
    else:
      clean = last_part.strip()
    if len(clean) > 150:
      return clean

  lines = raw_text.splitlines()
  letter_lines = []
  capturing = False
  for line in lines:
    stripped = line.strip()
    if not capturing:
      if not (
          stripped.startswith("*")
          or stripped.startswith("-")
          or stripped.startswith("•")
          or stripped.startswith("o ")
          or stripped.startswith("(")
      ):
        if (
            stripped.startswith("To,")
            or stripped.startswith("सेवा में,")
            or (stripped.startswith("Date:") and len(stripped) < 40)
            or (stripped.startswith("दिनांक:") and len(stripped) < 40)
        ):
          capturing = True
          letter_lines.append(line)
    else:
      letter_lines.append(line)

  if len(letter_lines) >= 8:
    return "\n".join(letter_lines).strip()
  return raw_text.strip()


# --- TABS ---
tab_advisory, tab_roi, tab_letter, tab_faq = st.tabs([
    (
        "📑 एआई विशेषज्ञ ऑडिट एवं रिपोर्ट"
        if is_hindi
        else "📑 AI Expert Report & Quote Audit"
    ),
    (
        "📈 25-वर्षीय बचत एवं इंजीनियरिंग BoM"
        if is_hindi
        else "📈 25-Year ROI & Engineering BoM"
    ),
    (
        "✉️ आधिकारिक आवेदन पत्र (SDO/HAREDA)"
        if is_hindi
        else "✉️ Official SDO / KUSUM Application"
    ),
    "💬 " + ("सौर सहायक (AI Q&A)" if is_hindi else "Interactive Solar Copilot"),
])

# --- TAB 1: REPORT & QUOTE AUDIT ---
with tab_advisory:
  if uploaded_file is not None:
    st.success(
        "📸 "
        + (
            "कोटेशन/बिल इमेज अपलोड हो गई है! एआई इसका विज़न ऑडिट करेगा।"
            if is_hindi
            else "Document image attached! Multimodal Vision Audit active."
        )
    )
  elif vendor_quote > 0:
    diff = vendor_quote - bench_gross_cost
    if diff > 15000:
      st.warning(
          f"⚠️ Installer quote (₹{vendor_quote:,}) is ₹{diff:,} above the fair MNRE benchmark (₹{bench_gross_cost:,})."
      )
    else:
      st.info(
          f"✅ Installer quote (₹{vendor_quote:,}) is within fair market benchmark (₹{bench_gross_cost:,})."
      )
  else:
    st.write(
        "💡 "
        + (
            "संपूर्ण तकनीकी व्यवहार्यता, सब्सिडी प्रक्रिया और सुरक्षा ऑडिट के लिए नीचे क्लिक करें।"
            if is_hindi
            else "Generate a customized engineering feasibility study, subsidy roadmap, and vendor price audit."
        )
    )

  if st.button(
      "🚀 "
      + (
          "विस्तृत एआई ऑडिट रिपोर्ट तैयार करें"
          if is_hindi
          else "Generate AI Engineering & Subsidy Report"
      )
  ):
    if not api_key:
      st.error("कृपया API Key दर्ज करें। / Please enter a valid Gemini API key.")
    else:
      status_box = st.empty()
      report_box = st.empty()
      start_time = time.time()
      try:
        pil_img = Image.open(uploaded_file) if uploaded_file else None
        if pil_img:
          st.image(pil_img, caption="Uploaded Quotation / Bill", width=300)

        quote_context = (
            f"Vendor Quoted Total: Rs. {vendor_quote:,} (Benchmark is Rs."
            f" {bench_gross_cost:,})."
            if vendor_quote > 0
            else "No vendor quote entered."
        )
        img_instruction = (
            "If an image is attached, extract the quoted price, panel brand,"
            " inverter specs, and audit them strictly."
            if pil_img
            else ""
        )

        if not is_agri:
          mode_details = f"""
Sector: Residential On-Grid Rooftop ({scheme_name})
State & Utility: {state} ({state_info['discom']} / {state_info['regulator']})
Monthly Bill: Rs. {monthly_bill} | Sanctioned Load: {sanctioned_load} kW | Roof Area: {roof_area} sq. ft.
Recommended System: {display_kw} kW | Eligible Subsidy: Rs. {subsidy_amount:,} | Net Cost: Rs. {net_estimated_cost:,}
Expected Annual Savings: Rs. {annual_savings:,} | Payback: {payback_years} Years
{quote_context}
"""
        else:
          mode_details = f"""
Sector: Agricultural Solar Water Pump ({scheme_name})
State & Agency: {state} ({state_info['agri_agency']} / {state_info['discom']})
Farmland: {land_acres} Acres | Water Table Depth: {water_depth} Feet | Pump Type: {pump_type}
Recommended Pump: {capacity_label} | Eligible Subsidy: Rs. {subsidy_amount:,} | Farmer Net Share: Rs. {net_estimated_cost:,}
Annual Diesel/Power Savings: Rs. {annual_savings:,} | Payback: {payback_years} Years
{quote_context}
"""

        prompt = f"""
You are UrjaMitra, Senior Solar Engineering & Policy Consultant for India's MNRE schemes.
Analyze the following profile and output a clean, authoritative Markdown report in {lang}.
{img_instruction}
DO NOT include raw scratchpad calculations or planning notes. Begin immediately with '# ☀️ UrjaMitra Technical & Financial Audit Report'.

Profile:
{mode_details}

Include these exact 4 sections:
1. Executive Engineering Feasibility
2. Step-by-Step Subsidy Claim Roadmap
3. Fair-Price & Component Audit (Compare vendor quote vs benchmark Rs. {bench_gross_cost:,}. Warn about DCR domestic solar cell requirements).
4. Critical Electrical Protection Checklist (3 separate Earthing pits, Lightning Arrestor, DCDB/ACDB Surge Protection).
"""
        full_rep, used_model = stream_ai_response(
            api_key, prompt, report_box, status_box, pil_img
        )
        latency = round(time.time() - start_time, 2)
        status_box.empty()
        st.success(
            f"✅ Completed in {latency}s | Engine: {used_model} | Cost: $0.00 (Free Tier)"
        )

        st.download_button(
            label="📥 "
            + (
                "ऑडिट रिपोर्ट डाउनलोड करें (.md)"
                if is_hindi
                else "Download Official Audit Report (.md)"
            ),
            data=full_rep,
            file_name=f"UrjaMitra_Solar_Report_{state}_{display_kw}kW.md",
            mime="text/markdown",
        )
      except Exception as e:
        status_box.empty()
        st.error(f"Error calling AI API: {str(e)}")

# --- TAB 2: ROI CHART & BOM ---
with tab_roi:
  col_chart, col_bom = st.columns([1.15, 1])

  with col_chart:
    st.markdown(
        "#### 📈 "
        + (
            "25-वर्षीय संचयी वित्तीय लाभ (₹)"
            if is_hindi
            else "25-Year Cumulative Wealth Trajectory (₹)"
        )
    )
    years = list(range(1, 26))
    cum_cashflow = []
    current_bal = -net_estimated_cost
    for y in years:
      yr_saving = annual_savings * ((1.025) ** (y - 1))
      current_bal += yr_saving
      cum_cashflow.append(round(current_bal))

    df_roi = pd.DataFrame({
        "Year": years,
        "Net Cumulative Profit (₹)": cum_cashflow,
    }).set_index("Year")

    st.area_chart(df_roi, color="#10B981", height=300)
    total_25yr_wealth = cum_cashflow[-1]
    st.info(
        f"💎 **25-Year Net Tax-Free Wealth Created:** ₹{total_25yr_wealth:,} (Initial investment of ₹{net_estimated_cost:,} recovered in {payback_years} years)."
    )

  with col_bom:
    st.markdown(
        "#### ⚡ "
        + (
            "इलेक्ट्रिकल इंजीनियरिंग BoM (अनिवार्य मानक)"
            if is_hindi
            else "Electrical Engineering BoM & Safety Specs"
        )
    )

    if not is_agri and display_kw > sanctioned_load:
      st.warning(
          f"⚠️ **Load Enhancement Required:** Recommended plant ({display_kw} kW) exceeds sanctioned load ({sanctioned_load} kW)."
      )

    phase_type = (
        "Single Phase (230V AC)"
        if display_kw <= 3 and not is_agri
        else "Three Phase (415V AC)"
    )
    panel_count = max(2, round((display_kw * 1000) / 545))

    bom_data = [
        {
            "Component": "Solar PV Modules",
            "Specification": (
                f"{panel_count} Nos. × 545Wp Mono-PERC / TOPCon (ALMM & DCR"
                " Certified)"
            ),
        },
        {
            "Component": (
                "Inverter / Pump Controller"
                if is_agri
                else "Grid-Tied String Inverter"
            ),
            "Specification": (
                f"{display_kw} kW, {phase_type}, IP65 Rated, >97.5% Efficiency"
            ),
        },
        {
            "Component": "Mounting Structure",
            "Specification": (
                "Hot-Dip Galvanized Iron (GI, min 80 microns), 150 km/h Wind"
                " Rated"
            ),
        },
        {
            "Component": "DC Solar Cable",
            "Specification": (
                "4.0 sq.mm EN 50618 Tinned Copper, UV & XLPO Insulated"
            ),
        },
        {
            "Component": "DCDB (DC Protection)",
            "Specification": (
                "600V/1000V DC MCB + 15A Cylindrical Fuse + Type-2 DC SPD"
            ),
        },
        {
            "Component": "ACDB (AC Protection)",
            "Specification": (
                f"{'32A DP' if display_kw <= 3 else '32A TPN'} MCB + Type-2 AC"
                " SPD"
            ),
        },
        {
            "Component": "Earthing & Lightning",
            "Specification": (
                "3 Separate Chemical Earthing Pits (DC, AC, LA) < 5 Ohms +"
                " ESE/Spike LA"
            ),
        },
    ]
    st.table(pd.DataFrame(bom_data))

# --- TAB 3: APPLICATION LETTER ---
with tab_letter:
  st.write(
      "📄 "
      + (
          f"{state_info['discom']} / {state_info['agri_agency']} के लिए तुरंत प्रिंट करने योग्य आधिकारिक आवेदन पत्र।"
          if is_hindi
          else f"Generate an executive, print-ready application addressed to {state_info['discom']} or {state_info['agri_agency']} with standard 'XXXX' redaction placeholders."
      )
  )

  if st.button(
      "📝 "
      + (
          "आधिकारिक आवेदन पत्र तैयार करें"
          if is_hindi
          else "Draft Official Application Letter"
      )
  ):
    if not api_key:
      st.error("Please enter a valid Gemini API key.")
    else:
      with st.spinner("Drafting formal utility application..."):
        start_time = time.time()
        try:
          target_authority = (
              f"Project Officer, {state_info['agri_agency']} /"
              f" {state_info['discom']}"
              if is_agri
              else f"The Sub-Divisional Officer (SDO), {state_info['discom']}"
          )

          if is_hindi:
            letter_prompt = f"""
आप भारतीय विद्युत नियामक एवं प्रशासनिक प्रारूपण के विशेषज्ञ हैं।
{scheme_name} के अंतर्गत {state} के संबंधित अधिकारी ({target_authority}) को {capacity_label} सोलर सिस्टम की स्वीकृति हेतु एक अत्यंत उच्च स्तरीय, कानूनी रूप से परिपूर्ण और औपचारिक आवेदन पत्र लिखें।

आवेदक विवरण:
सभी व्यक्तिगत विवरणों के लिए पेशेवर 'XXXX' प्रारूप का उपयोग करें:
- आवेदक का नाम: XXXX
- खाता / आवेदन संख्या: XXXXXXXXXXXX
- मीटर / खसरा संख्या: XXXXXXXX
- पता: मकान/खेत नं. XXX, ग्राम/सेक्टर XXXX, जिला XXXX, {state}
- मोबाइल नंबर: +91-XXXXXXXXXX

सख्त निर्देश:
पूरे औपचारिक पत्र को अनिवार्य रूप से <LETTER> और </LETTER> टैग के भीतर ही लिखें।
टैग के बाहर या अंदर कोई भी योजना नोट्स या रूपरेखा न लिखें।
"""
          else:
            letter_prompt = f"""
You are an executive legal and administrative drafting expert in Indian utility regulations ({state_info['regulator']}).
Draft an authoritative, highly formal, single-page application letter addressed to {target_authority}, {state}.
Request: Technical Feasibility Approval and Sanction for a {capacity_label} solar installation under {scheme_name}.

Applicant Redaction / Details:
Use professional 'XXXX' placeholders for all consumer credentials:
- Consumer Name: XXXX
- Consumer Account / Land Khasra No.: XXXXXXXXXXXX
- Existing Meter Number: XXXXXXXX
- Existing Sanctioned Load: {sanctioned_load if not is_agri else 'N/A'} kW
- Installation Address: Premises No. XXX, Sector/Village XXXX, District XXXX, {state}
- Contact Number: +91-XXXXXXXXXX
- Email: xxxx@email.com

STRICT STRUCTURAL REQUIREMENT:
Enclose the ENTIRE formal letter inside <LETTER> and </LETTER> tags.
Do NOT write planning outlines, scratchpads, or commentary.
Begin directly inside the tags with:

To,
{target_authority},
{state}.
"""
          raw_output, used_model = generate_ai_text(api_key, letter_prompt)
          clean_letter = extract_clean_letter(raw_output)

          latency = round(time.time() - start_time, 2)
          st.success(
              f"✅ Drafted via {used_model} in {latency}s | Ready to print"
          )

          st.markdown(clean_letter)

          st.download_button(
              label="📥 "
              + (
                  "आवेदन पत्र डाउनलोड करें (.txt)"
                  if is_hindi
                  else "Download Print-Ready Letter (.txt)"
              ),
              data=clean_letter,
              file_name=f"Official_Solar_Application_{state}.txt",
              mime="text/plain",
          )

          with st.expander(
              "📋 "
              + (
                  "कॉपी करने के लिए यहाँ क्लिक करें"
                  if is_hindi
                  else "Click here to Copy Plain Text"
              )
          ):
            st.text_area("Letter Text", value=clean_letter, height=280)

        except Exception as e:
          st.error(f"Error generating letter: {str(e)}")

# --- TAB 4: AI COPILOT Q&A ---
with tab_faq:
  st.markdown(
      "#### 💬 "
      + (
          "पीएम सूर्य घर एवं पीएम-कुसुम विशेषज्ञ से पूछें"
          if is_hindi
          else "Ask the MNRE & Discom Regulatory Copilot"
      )
  )
  user_q = st.text_input(
      "अपना प्रश्न यहाँ लिखें (उदा. 'क्या डीसीआर पैनल अनिवार्य हैं?' या 'हरियाणा में 5 HP पंप पर कितनी सब्सिडी है?'):"
      if is_hindi
      else "Ask about DCR vs Non-DCR panels, net-metering export rates, load enhancement, or PM-KUSUM subsidies:"
  )
  if st.button("⚡ उत्तर प्राप्त करें" if is_hindi else "⚡ Get Expert Answer") and user_q:
    if not api_key:
      st.error("Please enter a valid Gemini API key.")
    else:
      status_box = st.empty()
      faq_box = st.empty()
      start_time = time.time()
      try:
        faq_prompt = f"""
You are UrjaMitra, the official solar engineering and policy copilot for {state} ({state_info['discom']} / {state_info['agri_agency']}).
Answer this citizen question accurately, practically, and concisely in {lang}:
Question: "{user_q}"
Cite official MNRE, PM Surya Ghar, PM-KUSUM, and {state_info['regulator']} guidelines. Begin directly with the answer.
"""
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemma-4-26b-a4b-it")
        response = model.generate_content(faq_prompt, stream=True)

        full_text = ""
        for chunk in response:
          if chunk.text:
            full_text += chunk.text
            faq_box.markdown(full_text)

        latency = round(time.time() - start_time, 2)
        status_box.empty()
        st.success(f"✅ Answered via gemma-4-26b-a4b-it in {latency}s")
      except Exception as e:
        status_box.empty()
        st.error(f"Error: {str(e)}")
