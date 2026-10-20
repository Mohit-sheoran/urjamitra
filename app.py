import math
import os
import re
import time
import google.generativeai as genai
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image
import streamlit as st

# --- 1. GLOBAL CONFIG & CONSTANTS ---
st.set_page_config(
    page_title="UrjaMitra | National Solar & PM-KUSUM Copilot",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

SCHEME_CONFIG = {
    "last_verified": "October 2026",
    "residential_slabs": {
        1: {"subsidy": 30000, "label": "1 kW Slab"},
        2: {"subsidy": 60000, "label": "2 kW Slab"},
        3: {"subsidy": 78000, "label": "3 kW+ Slab (Capped)"},
    },
    "benchmark_cost_per_kw": 58000,
    "agri_pumps": {
        3: {"kw": 3.0, "benchmark": 155000, "desc": "3 HP Submersible / Surface"},
        5: {"kw": 5.0, "benchmark": 240000, "desc": "5 HP High-Discharge Pump"},
        7.5: {
            "kw": 7.5,
            "benchmark": 345000,
            "desc": "7.5 HP Deep Water Table Pump",
        },
        10: {
            "kw": 10.0,
            "benchmark": 460000,
            "desc": "10 HP Commercial / Multi-Acre Pump",
        },
    },
}

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
        "discom": "UPPCL (PVVNL / DVVNL)",
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
        "discom": "BSES / Tata Power-DDL",
        "regulator": "DERC",
        "agri_agency": "EE&REM Delhi",
        "tariff": 8.00,
        "insolation": 4.5,
        "kusum_state_sub": 30,
    },
    "Maharashtra": {
        "discom": "MSEDCL (Mahavitaran)",
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

# --- 2. MODERN DESIGN SYSTEM & CSS ---
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+Devanagari:wght@400;500;700&display=swap');

    :root {
        --primary: #059669;
        --primary-dark: #047857;
        --accent: #F59E0B;
        --bg-gradient: linear-gradient(180deg, #F8FAFC 0%, #EFF6FF 100%);
        --card-bg: #FFFFFF;
        --text-main: #0F172A;
        --text-muted: #64748B;
        --border-color: #E2E8F0;
        --radius: 14px;
        --shadow: 0 4px 20px rgba(15, 23, 42, 0.06);
    }

    @media (prefers-color-scheme: dark) {
        :root {
            --bg-gradient: linear-gradient(180deg, #0B0F19 0%, #111827 100%);
            --card-bg: #1F2937;
            --text-main: #F9FAFB;
            --text-muted: #9CA3AF;
            --border-color: #374151;
            --shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }
    }

    .stApp {
        background: var(--bg-gradient);
        color: var(--text-main);
        font-family: 'Inter', 'Noto Sans Devanagari', sans-serif;
        max-width: 100vw;
        overflow-x: hidden;
    }

    #MainMenu, footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Responsive Mobile Adjustments */
    @media (max-width: 768px) {
        .hero-container { padding: 18px !important; }
        .hero-title { font-size: 1.6rem !important; }
        .kpi-value { font-size: 1.3rem !important; }
    }

    /* Hero Banner */
    .hero-container {
        background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 65%, #047857 100%);
        padding: 32px 36px;
        border-radius: var(--radius);
        color: #FFFFFF;
        margin-bottom: 24px;
        box-shadow: 0 15px 35px -10px rgba(15, 23, 42, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.15);
        position: relative;
        overflow: hidden;
    }
    .hero-badge {
        background: rgba(245, 158, 11, 0.25);
        border: 1px solid #F59E0B;
        color: #FCD34D;
        padding: 5px 14px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        display: inline-block;
        margin-bottom: 12px;
    }
    .hero-title {
        font-size: 2.4rem;
        font-weight: 800;
        margin: 0;
        color: #FFFFFF;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .pulse-sun {
        display: inline-block;
        animation: pulse 2.5s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.15); opacity: 0.8; }
        100% { transform: scale(1); opacity: 1; }
    }
    .hero-subtitle {
        font-size: 1.05rem;
        color: #E2E8F0;
        margin-top: 8px;
        font-weight: 400;
    }
    .hero-chips {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin-top: 16px;
    }
    .hero-chip {
        background: rgba(255, 255, 255, 0.12);
        padding: 6px 14px;
        border-radius: 8px;
        font-size: 0.82rem;
        font-weight: 600;
        color: #F8FAFC;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    /* KPI Cards */
    .kpi-card {
        background: var(--card-bg);
        padding: 20px;
        border-radius: var(--radius);
        box-shadow: var(--shadow);
        border: 1px solid var(--border-color);
        border-top: 5px solid var(--accent);
        height: 100%;
        transition: transform 0.2s ease;
    }
    .kpi-card:hover { transform: translateY(-3px); }
    .kpi-card.green { border-top-color: var(--primary); }
    .kpi-card.blue { border-top-color: #3B82F6; }
    .kpi-card.purple { border-top-color: #8B5CF6; }

    .kpi-title {
        font-size: 0.78rem;
        font-weight: 700;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: var(--text-main);
        margin: 0;
        line-height: 1.2;
    }
    .kpi-sub {
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--primary);
        margin-top: 8px;
    }

    /* Info Strip */
    .info-strip {
        background: var(--card-bg);
        border-left: 5px solid #0284C7;
        padding: 14px 18px;
        border-radius: 10px;
        box-shadow: var(--shadow);
        margin-bottom: 20px;
        font-size: 0.9rem;
        color: var(--text-main);
        border-top: 1px solid var(--border-color);
        border-right: 1px solid var(--border-color);
        border-bottom: 1px solid var(--border-color);
    }

    /* Buttons */
    div.stButton > button {
        background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.65rem 1.4rem;
        font-weight: 700;
        font-size: 0.95rem;
        box-shadow: 0 4px 12px rgba(5, 150, 105, 0.25);
        transition: all 0.2s ease;
        width: 100%;
    }
    div.stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(5, 150, 105, 0.35);
    }

    /* Outlined secondary buttons */
    .stDownloadButton > button {
        background: transparent !important;
        color: var(--primary) !important;
        border: 2px solid var(--primary) !important;
        border-radius: 10px;
        font-weight: 700;
        width: 100%;
    }
    .stDownloadButton > button:hover {
        background: var(--primary) !important;
        color: white !important;
    }

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: var(--border-color);
        padding: 6px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 10px 16px;
        font-weight: 700;
        color: var(--text-muted);
    }
    .stTabs [aria-selected="true"] {
        background-color: var(--card-bg) !important;
        color: var(--text-main) !important;
        box-shadow: var(--shadow);
    }

    /* Paper Letter Card */
    .paper-letter {
        background: #FFFFFF;
        color: #1E293B;
        padding: 40px;
        border-radius: 8px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        font-family: 'Times New Roman', serif;
        font-size: 1.1rem;
        line-height: 1.6;
        border: 1px solid #CBD5E1;
        margin-bottom: 20px;
    }

    /* Stepper / Timeline */
    .stepper-container {
        display: flex;
        justify-content: space-between;
        margin: 25px 0;
        position: relative;
        flex-wrap: wrap;
        gap: 15px;
    }
    .step-item {
        flex: 1;
        background: var(--card-bg);
        padding: 16px;
        border-radius: 12px;
        border: 1px solid var(--border-color);
        box-shadow: var(--shadow);
        position: relative;
        min-width: 180px;
    }
    .step-num {
        background: var(--primary);
        color: white;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 0.85rem;
        margin-bottom: 8px;
    }
    .step-title {
        font-weight: 700;
        font-size: 0.92rem;
        color: var(--text-main);
        margin-bottom: 4px;
    }
    .step-desc {
        font-size: 0.78rem;
        color: var(--text-muted);
    }

    /* BoM Table Styling */
    .bom-table {
        width: 100%;
        border-collapse: collapse;
        background: var(--card-bg);
        border-radius: 10px;
        overflow: hidden;
        box-shadow: var(--shadow);
        border: 1px solid var(--border-color);
    }
    .bom-table th {
        background: #0F172A;
        color: white;
        padding: 12px 16px;
        text-align: left;
        font-size: 0.85rem;
    }
    .bom-table td {
        padding: 12px 16px;
        border-bottom: 1px solid var(--border-color);
        font-size: 0.88rem;
        color: var(--text-main);
    }
    .bom-table tr:nth-child(even) { background-color: rgba(0,0,0,0.02); }

    /* Footer Disclaimer */
    .app-footer {
        text-align: center;
        margin-top: 40px;
        padding: 20px;
        font-size: 0.8rem;
        color: var(--text-muted);
        border-top: 1px solid var(--border-color);
    }
</style>
""",
    unsafe_allow_html=True,
)

# --- 3. STATE-SPECIFIC DATABASE & SECURE SECRETS ---
try:
  configured_key = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
  configured_key = ""

# Session state initialization
if "report_text" not in st.session_state:
  st.session_state.report_text = ""
if "letter_text" not in st.session_state:
  st.session_state.letter_text = ""
if "faq_history" not in st.session_state:
  st.session_state.faq_history = []

# --- 4. TOP BAR & LANGUAGE SELECTOR ---
_, col_lang = st.columns([4, 1])
with col_lang:
  lang = st.selectbox(
      "🌐 भाषा / Language",
      ["English", "हिंदी (Hindi)"],
      label_visibility="collapsed",
  )

is_hindi = lang == "हिंदी (Hindi)"

# --- 5. REDESIGNED HERO BANNER ---
if is_hindi:
  st.markdown(
      """
    <div class="hero-container">
        <div class="hero-badge">🇮🇳 एमएनआरई (MNRE) एवं पीएम-कुसुम मानकों पर आधारित</div>
        <h1 class="hero-title"><span class="pulse-sun">☀️</span> ऊर्जा मित्र (UrjaMitra)</h1>
        <p class="hero-subtitle">एआई-संचालित सोलर साइज़िंग, पीएम सूर्य घर एवं पीएम-कुसुम सब्सिडी, कोटेशन ऑडिट और डिस्कॉम नेट-मीटरिंग सहायक</p>
        <div class="hero-chips">
            <span class="hero-chip">💡 सब्सिडी ₹78,000 तक</span>
            <span class="hero-chip">🌐 द्विभाषी (Bilingual)</span>
            <span class="hero-chip">🔍 कोटेशन एआई ऑडिटर</span>
        </div>
    </div>
    """,
      unsafe_allow_html=True,
  )
else:
  st.markdown(
      """
    <div class="hero-container">
        <div class="hero-badge">🇮🇳 Grounded in Official MNRE & State Discom Regulations</div>
        <h1 class="hero-title"><span class="pulse-sun">☀️</span> UrjaMitra (ऊर्जा मित्र)</h1>
        <p class="hero-subtitle">Next-Gen Solar Engineering Copilot • PM Surya Ghar & PM-KUSUM Sizing • Multimodal Quote Auditor • Discom Legal Drafter</p>
        <div class="hero-chips">
            <span class="hero-chip">💡 Subsidy up to ₹78,000</span>
            <span class="hero-chip">🌐 Bilingual Support</span>
            <span class="hero-chip">🔍 Quote Auditor</span>
        </div>
    </div>
    """,
      unsafe_allow_html=True,
  )

# --- 6. SIDEBAR INPUTS & DEMO MODE ---
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

demo_mode = st.sidebar.checkbox(
    "🚀 डेमो मोड चालू करें (Demo Mode)"
    if is_hindi
    else "🚀 Enable Demo Mode (No API Key Required)",
    value=not bool(api_key),
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

# --- 7. DETERMINISTIC ENGINE WITH BUG FIXES ---
if not is_agri:
  unit_rate = state_info["tariff"]
  daily_gen_per_kw = state_info["insolation"]
  est_monthly_units = monthly_bill / unit_rate
  req_kw = est_monthly_units / (daily_gen_per_kw * 30)
  max_kw_by_roof = roof_area / 95.0
  raw_kw = max(1.0, min(req_kw, max_kw_by_roof))

  # Fix 1: Choose final integer kW first using math.floor(x + 0.5), then look up subsidy slab
  display_kw = max(
      1, min(10, math.floor(raw_kw + 0.5))
  )  # Capped at reasonable residential limit

  if display_kw == 1:
    subsidy_amount = SCHEME_CONFIG["residential_slabs"][1]["subsidy"]
  elif display_kw == 2:
    subsidy_amount = SCHEME_CONFIG["residential_slabs"][2]["subsidy"]
  else:
    subsidy_amount = SCHEME_CONFIG["residential_slabs"][3][
        "subsidy"
    ]  # 3kW+ capped slab

  bench_gross_cost = display_kw * SCHEME_CONFIG["benchmark_cost_per_kw"]
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
  # Agri mode sizing logic & expandable explanation
  if water_depth > 200 or land_acres > 10:
    recommended_hp = 10
    solar_kw = 10.0
  elif water_depth > 120 or land_acres > 6:
    recommended_hp = 7.5
    solar_kw = 7.5
  elif water_depth > 60 or land_acres > 3:
    recommended_hp = 5
    solar_kw = 5.0
  else:
    recommended_hp = 3
    solar_kw = 3.0

  if "DC" in pump_type:
    solar_kw *= 1.15  # DC efficiency buffer

  display_kw = round(solar_kw, 1)
  bench_gross_cost = SCHEME_CONFIG["agri_pumps"].get(
      recommended_hp, SCHEME_CONFIG["agri_pumps"][5]
  )["benchmark"]
  total_sub_pct = 30 + state_info["kusum_state_sub"]
  subsidy_amount = round(bench_gross_cost * (total_sub_pct / 100.0))
  net_estimated_cost = max(0, bench_gross_cost - subsidy_amount)
  annual_savings = round(monthly_diesel_spend * 10)
  payback_years = (
      round(net_estimated_cost / annual_savings, 1) if annual_savings > 0 else 0
  )
  co2_offset_tons = round(recommended_hp * 1.4, 1)

  capacity_label = f"{recommended_hp} HP Pump ({display_kw} kW)"
  capacity_sub = f"Sufficient for {land_acres} Acres @ {water_depth}ft"
  subsidy_sub = f"{total_sub_pct}% Subsidy ({state_info['agri_agency']})"
  scheme_name = f"PM-KUSUM Component-B ({state_info['agri_agency']})"

# --- 8. STATE REGULATORY & METRIC CARDS DISPLAY ---
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
        <div class="kpi-title">{"अनुमानित सरकारी सब्सिडी" if is_hindi else "Estimated Govt Subsidy"}</div>
        <div class="kpi-value">₹{subsidy_amount:,}</div>
        <div class="kpi-sub">🏛️ {subsidy_sub} (Estimate)</div>
    </div>
    """,
      unsafe_allow_html=True,
  )

with k3:
  st.markdown(
      f"""
    <div class="kpi-card blue">
        <div class="kpi-title">{"आपकी शुद्ध लागत" if is_hindi else "Est. Net Investment"}</div>
        <div class="kpi-value">₹{net_estimated_cost:,}</div>
        <div class="kpi-sub">💰 Benchmark: ₹{bench_gross_cost:,} (Estimate)</div>
    </div>
    """,
      unsafe_allow_html=True,
  )

with k4:
  st.markdown(
      f"""
    <div class="kpi-card purple">
        <div class="kpi-title">{"लागत वसूली समय" if is_hindi else "Est. Payback & Impact"}</div>
        <div class="kpi-value">{payback_years} {"वर्ष" if is_hindi else "Years"}</div>
        <div class="kpi-sub">🌱 Saves ₹{annual_savings:,}/yr • {co2_offset_tons}T CO₂</div>
    </div>
    """,
      unsafe_allow_html=True,
  )

st.write("")

# Bill Comparison / Agri Calculation Expander
if not is_agri:
  st.info(
      f"💡 **Bill Impact Analysis (Estimate):** Your monthly bill of `₹{monthly_bill:,}` drops to near `₹0` after solar installation, saving approx `₹{annual_savings:,}` every year."
  )
else:
  with st.expander(
      "🔍 कृषि पंप क्षमता गणना कैसे की जाती है? (How we calculated this pump HP)"
  ):
    st.write(
        f"""
        - **Water Table Depth:** `{water_depth} ft` requires substantial head pressure.
        - **Irrigated Area:** `{land_acres} Acres` determines required daily water discharge volume.
        - **Selected Pump Type:** `{pump_type}` combined with solar array oversizing yields a reliable **{recommended_hp} HP** off-grid/hybrid setup.
        - **Estimated Benchmark Cost:** `₹{bench_gross_cost:,}` under MNRE PM-KUSUM benchmarks.
        """
    )

# WhatsApp Share Button
whatsapp_text = f"☀️ UrjaMitra Solar Assessment for {state}:\nRecommended System: {capacity_label}\nEst. Subsidy: ₹{subsidy_amount:,}\nEst. Net Cost: ₹{net_estimated_cost:,}\nPayback: {payback_years} Years!\nCalculated via UrjaMitra Copilot."
whatsapp_url = f"https://api.whatsapp.com/send?text={urllib.parse.quote(whatsapp_text) if 'urllib' in globals() else whatsapp_text}"
st.markdown(
    f'<div style="margin-bottom: 20px;"><a href="{whatsapp_url}" target="_blank" style="background:#25D366; color:white; padding:8px 16px; border-radius:8px; text-decoration:none; font-weight:700; font-size:0.85rem;">💬 Share Assessment on WhatsApp</a></div>',
    unsafe_allow_html=True,
)


# --- 9. CACHED MODEL DISCOVERY & AI DISPATCHERS ---
@st.cache_data(ttl=3600)
def get_cached_candidate_models(key: str):
  try:
    genai.configure(api_key=key)
    candidates = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-3.8-flash"]
    for m in genai.list_models():
      if (
          "generateContent" in m.supported_generation_methods
          and "flash" in m.name.lower()
          and m.name not in candidates
      ):
        candidates.append(m.name)
    return candidates
  except Exception:
    return ["gemini-2.5-flash", "gemini-2.0-flash"]


def generate_ai_text_safe(key: str, prompt: str, pil_image=None):
  if demo_mode or not key:
    return (
        """# ☀️ UrjaMitra Demo Report (Demo Mode Active)
1. **Executive Feasibility:** Your location in **"""
        + state
        + """** receives excellent solar insolation (~"""
        + str(state_info["insolation"])
        + """ kWh/kW/day). The recommended **"""
        + capacity_label
        + """** fits your parameters perfectly.
2. **Subsidy Roadmap:** Register on the official portal, apply for technical feasibility with **"""
        + state_info["discom"]
        + """**, install via empanelled vendor, and receive direct subsidy credit.
3. **Quote Audit:** Your entered quote is compared against MNRE benchmark costs (₹"""
        + f"{bench_gross_cost:,}"
        + """). Ensure DCR-compliant domestic solar cells are used.
4. **Safety & Protection:** Mandate 3 separate chemical earthing pits, Type-2 AC/DC surge protection devices (SPDs), and a lightning arrestor.
""",
        "Demo-Mode-Engine",
    )

  candidates = get_cached_candidate_models(key)
  genai.configure(api_key=key)
  last_err = None
  for model_name in candidates:
    try:
      model = genai.GenerativeModel(model_name)
      payload = [prompt, pil_image] if pil_image is not None else prompt
      res = model.generate_content(payload)
      return res.text, model_name
    except Exception as e:
      last_err = e
      continue
  raise last_err if last_err else RuntimeError("All available AI models busy.")


def extract_clean_letter(raw_text: str) -> str:
  matches = re.findall(r"<LETTER>([\s\S]*?)</LETTER>", raw_text, re.IGNORECASE)
  if matches:
    longest = max(matches, key=len).strip()
    if len(longest) > 100:
      return longest
  return raw_text.strip()


# --- 10. MAIN TABS ---
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

# --- TAB 1: REPORT & QUOTE AUDIT WITH VISUAL TIMELINE STEPPER ---
with tab_advisory:
  if uploaded_file is not None:
    st.success(
        "📸 "
        + (
            "कोटेशन/बिल इमेज संलग्न है!"
            if is_hindi
            else "Document attached for Vision Audit."
        )
    )
  elif vendor_quote > 0:
    diff = vendor_quote - bench_gross_cost
    if diff > 15000:
      st.warning(
          f"⚠️ Installer quote (₹{vendor_quote:,}) is ₹{diff:,} above the MNRE benchmark (₹{bench_gross_cost:,} Estimate)."
      )
    else:
      st.info(
          f"✅ Installer quote (₹{vendor_quote:,}) is within fair market benchmark (₹{bench_gross_cost:,} Estimate)."
      )

  # Visual Vertical Stepper / Timeline Roadmap
  st.markdown(
      f"#### 🗺️ {'सब्सिडी एवं स्थापना रोडमैप' if is_hindi else 'Subsidy & Installation Roadmap'} ({scheme_name})"
  )
  if not is_agri:
    st.markdown(
        """
        <div class="stepper-container">
            <div class="step-item"><div class="step-num">1</div><div class="step-title">Portal Registration</div><div class="step-desc">Register on pmsuryaghar.gov.in with consumer details.</div></div>
            <div class="step-item"><div class="step-num">2</div><div class="step-title">DISCOM Feasibility</div><div class="step-desc">Submit online application to local utility for grid approval.</div></div>
            <div class="step-item"><div class="step-num">3</div><div class="step-title">Vendor Installation</div><div class="step-desc">Execute installation via an MNRE-empanelled vendor.</div></div>
            <div class="step-item"><div class="step-num">4</div><div class="step-title">Net Metering Inspection</div><div class="step-desc">Utility inspects site and installs bidirectional net meter.</div></div>
            <div class="step-item"><div class="step-num">5</div><div class="step-title">Subsidy Direct DBT</div><div class="step-desc">Subsidy credited directly to your bank account within 30 days.</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
  else:
    st.markdown(
        f"""
        <div class="stepper-container">
            <div class="step-item"><div class="step-num">1</div><div class="step-title">State Agency Portal</div><div class="step-desc">Apply on {state_info['agri_agency']} portal with land records.</div></div>
            <div class="step-item"><div class="step-num">2</div><div class="step-title">Site Verification</div><div class="step-desc">Joint inspection of water table and land by engineers.</div></div>
            <div class="step-item"><div class="step-num">3</div><div class="step-title">Beneficiary Share</div><div>Deposit your 25-30% share with the empanelled vendor.</div></div>
            <div class="step-item"><div class="step-num">4</div><div class="step-title">Pump Commissioning</div><div class="step-desc">Installation and commissioning of solar water pump.</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

  if st.button(
      "🚀 "
      + (
          "विस्तृत एआई ऑडिट रिपोर्ट तैयार करें"
          if is_hindi
          else "Generate AI Engineering & Subsidy Report"
      )
  ):
    if not api_key and not demo_mode:
      st.error(
          "कृपया API Key दर्ज करें या डेमो मोड चालू करें। / Please enter API Key or enable Demo Mode."
      )
    else:
      with st.status(
          "⚡ Generating comprehensive AI engineering report...", expanded=True
      ) as status:
        start_time = time.time()
        try:
          pil_img = Image.open(uploaded_file) if uploaded_file else None
          if pil_img:
            st.image(pil_img, caption="Uploaded Document", width=250)

          quote_context = (
              f"Vendor Quoted Total: Rs. {vendor_quote:,} (Benchmark is Rs."
              f" {bench_gross_cost:,})."
              if vendor_quote > 0
              else "No vendor quote entered."
          )
          prompt = f"""
You are UrjaMitra, Senior Solar Engineering & Policy Consultant for India's MNRE schemes.
Analyze the following profile and output a clean, authoritative Markdown report in {lang}.
Profile: State: {state}, Scheme: {scheme_name}, Recommended: {capacity_label}, Subsidy: Rs. {subsidy_amount:,}, Net Cost: Rs. {net_estimated_cost:,}, Annual Savings: Rs. {annual_savings:,}, Payback: {payback_years} Years. {quote_context}
Include these exact 4 sections:
1. Executive Engineering Feasibility
2. Step-by-Step Subsidy Claim Roadmap
3. Fair-Price & Component Audit (Compare quote vs benchmark Rs. {bench_gross_cost:,}).
4. Critical Electrical Protection Checklist (Earthing, Lightning Arrestor, ACDB/DCDB SPDs).
"""
          full_rep, used_model = generate_ai_text_safe(
              api_key, prompt, pil_img
          )
          st.session_state.report_text = full_rep
          latency = round(time.time() - start_time, 2)
          status.update(
              label=f"✅ Report generated via {used_model} in {latency}s!",
              state="complete",
          )
        except Exception as e:
          status.update(label="❌ Generation failed", state="error")
          st.error(f"Error: {str(e)}")

  if st.session_state.report_text:
    st.markdown(st.session_state.report_text)
    st.download_button(
        label="📥 "
        + (
            "ऑडिट रिपोर्ट डाउनलोड करें (.md)"
            if is_hindi
            else "Download Official Audit Report (.md)"
        ),
        data=st.session_state.report_text,
        file_name=f"UrjaMitra_Solar_Report_{state}_{display_kw}kW.md",
        mime="text/markdown",
    )

# --- TAB 2: PLOTLY CHARTS & BoM TABLE ---
with tab_roi:
  col_chart1, col_chart2 = st.columns(2)

  with col_chart1:
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
      # Fix 2: Explicitly apply 3% tariff/diesel growth and 0.5% panel degradation annually
      degraded_savings = annual_savings * ((0.995) ** (y - 1))
      inflated_savings = degraded_savings * ((1.03) ** (y - 1))
      current_bal += inflated_savings
      cum_cashflow.append(round(current_bal))

    df_roi = pd.DataFrame(
        {"Year": years, "Cumulative Net Savings (₹)": cum_cashflow}
    )

    fig_roi = px.area(
        df_roi,
        x="Year",
        y="Cumulative Net Savings (₹)",
        color_discrete_sequence=["#10B981"],
    )
    fig_roi.add_vline(
        x=payback_years,
        line_dash="dash",
        line_color="#F59E0B",
        annotation_text=f"Payback: {payback_years} Yr",
        annotation_position="top left",
    )
    fig_roi.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=280,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(200,200,200,0.2)"),
    )
    st.plotly_chart(fig_roi, use_container_width=True, config={"displayModeBar": False})

  with col_chart2:
    st.markdown(
        "#### 🥧 "
        + (
            "सब्सिडी बनाम नागरिक निवेश"
            if is_hindi
            else "Subsidy vs Citizen Investment"
        )
    )
    fig_pie = go.Figure(
        data=[
            go.Pie(
                labels=["Govt Subsidy", "Net Citizen Share"],
                values=[subsidy_amount, net_estimated_cost],
                hole=0.5,
                marker=dict(colors=["#10B981", "#3B82F6"]),
            )
        ]
    )
    fig_pie.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=280,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
    )
    st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})

  if vendor_quote > 0:
    st.markdown(
        "#### 📊 "
        + (
            "कोटेशन तुलना (Installer Quote vs Benchmark)"
            if is_hindi
            else "Quote vs Benchmark Cost Comparison"
        )
    )
    fig_bar = px.bar(
        x=["Installer Quote", "MNRE Benchmark Gross", "Net Cost after Subsidy"],
        y=[vendor_quote, bench_gross_cost, net_estimated_cost],
        color=["Installer Quote", "MNRE Benchmark Gross", "Net Cost after Subsidy"],
        color_discrete_map={
            "Installer Quote": (
                "#EF4444" if vendor_quote > bench_gross_cost else "#10B981"
            ),
            "MNRE Benchmark Gross": "#3B82F6",
            "Net Cost after Subsidy": "#F59E0B",
        },
    )
    fig_bar.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=240,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

  st.write("---")
  st.markdown(
      "#### ⚡ "
      + (
          "इलेक्ट्रिकल इंजीनियरिंग BoM (अनिवार्य मानक)"
          if is_hindi
          else "Electrical Engineering BoM & Safety Specs"
      )
  )

  phase_type = (
      "Single Phase (230V AC)"
      if display_kw <= 3 and not is_agri
      else "Three Phase (415V AC)"
  )
  panel_count = max(2, round((display_kw * 1000) / 545))

  bom_html = f"""
    <table class="bom-table">
        <tr><th>Component</th><th>Specification / Standard</th></tr>
        <tr><td>☀️ Solar PV Modules</td><td>{panel_count} Nos. × 545Wp Mono-PERC / TOPCon (ALMM & DCR Certified)</td></tr>
        <tr><td>🔌 Inverter / Controller</td><td>{display_kw} kW, {phase_type}, IP65 Rated, >97.5% Efficiency</td></tr>
        <tr><td>🏗️ Mounting Structure</td><td>Hot-Dip Galvanized Iron (GI, min 80 microns), 150 km/h Wind Rated</td></tr>
        <tr><td>🚡 DC Solar Cable</td><td>4.0 sq.mm EN 50618 Tinned Copper, UV & XLPO Insulated</td></tr>
        <tr><td>🛡️ DCDB Protection</td><td>600V/1000V DC MCB + 15A Cylindrical Fuse + Type-2 DC SPD</td></tr>
        <tr><td>⚡ ACDB Protection</td><td>{"32A DP" if display_kw <= 3 else "32A TPN"} MCB + Type-2 AC Surge Protection Device</td></tr>
        <tr><td>🌍 Earthing & Lightning</td><td>3 Separate Chemical Earthing Pits (DC, AC, LA) < 5 Ohms + ESE/Spike LA</td></tr>
    </table>
    """
  st.markdown(bom_html, unsafe_allow_html=True)

# --- TAB 3: APPLICATION LETTER WITH PAPER CARD ---
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
    if not api_key and not demo_mode:
      st.error("Please enter API Key or enable Demo Mode.")
    else:
      with st.status(
          "📄 Drafting formal utility application...", expanded=True
      ) as status:
        start_time = time.time()
        try:
          target_authority = (
              f"Project Officer, {state_info['agri_agency']} /"
              f" {state_info['discom']}"
              if is_agri
              else f"The Sub-Divisional Officer (SDO), {state_info['discom']}"
          )

          letter_prompt = f"""
You are an executive legal and administrative drafting expert in Indian utility regulations ({state_info['regulator']}).
Draft an authoritative, highly formal, single-page application letter addressed to {target_authority}, {state}.
Request: Technical Feasibility Approval and Sanction for a {capacity_label} solar installation under {scheme_name}.
Use professional 'XXXX' placeholders for Consumer Name, Account No., Meter No., and Address.
Enclose the ENTIRE formal letter inside <LETTER> and </LETTER> tags.
"""
          raw_output, _ = generate_ai_text_safe(api_key, letter_prompt)
          clean_letter = extract_clean_letter(raw_output)
          st.session_state.letter_text = clean_letter
          status.update(label="✅ Letter successfully drafted!", state="complete")
        except Exception as e:
          status.update(label="❌ Drafting failed", state="error")
          st.error(f"Error: {str(e)}")

  if st.session_state.letter_text:
    col_l, col_r = st.columns([3, 1])
    with col_l:
      st.markdown(
          f'<div class="paper-letter"><pre style="white-space: pre-wrap; font-family: inherit; background: transparent; border: none; color: inherit;">{st.session_state.letter_text}</pre></div>',
          unsafe_allow_html=True,
      )
    with col_r:
      st.markdown("#### Actions")
      st.download_button(
          label="📥 Download (.txt)",
          data=st.session_state.letter_text,
          file_name=f"Official_Solar_Application_{state}.txt",
          mime="text/plain",
      )

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
      "अपना प्रश्न यहाँ लिखें:"
      if is_hindi
      else "Ask about DCR vs Non-DCR panels, net-metering export rates, or subsidies:"
  )
  if st.button("⚡ उत्तर प्राप्त करें" if is_hindi else "⚡ Get Expert Answer") and user_q:
    if not api_key and not demo_mode:
      st.error("Please enter API Key or enable Demo Mode.")
    else:
      faq_box = st.empty()
      try:
        faq_prompt = f"""
You are UrjaMitra, the official solar engineering and policy copilot for {state} ({state_info['discom']} / {state_info['agri_agency']}).
Answer accurately and concisely in {lang}: "{user_q}"
Cite official MNRE and {state_info['regulator']} guidelines.
"""
        ans, _ = generate_ai_text_safe(api_key, faq_prompt)
        st.session_state.faq_history.append((user_q, ans))
      except Exception as e:
        st.error(f"Error: {str(e)}")

  for q, a in reversed(st.session_state.faq_history):
    st.markdown(f"**Q: {q}**")
    st.markdown(f"{a}")
    st.write("---")

# --- FOOTER DISCLAIMER ---
st.markdown(
    """
<div class="app-footer">
    ⚠️ <b>Disclaimer:</b> Estimates for guidance only. Verify subsidy amounts, technical specifications, and electricity tariffs with MNRE / your local DISCOM before proceeding with procurement or installation.
</div>
""",
    unsafe_allow_html=True,
)
