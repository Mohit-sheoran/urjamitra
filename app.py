"""UrjaMitra - National Solar & PM-KUSUM Copilot (Streamlit).

Hybrid design: a deterministic Python engine does sizing, subsidy, ROI, BoM,
roadmap and the application letter instantly (0 tokens). The LLM is used only
for short personalised insights, quote-image audit, letter polishing and Q&A.
"""

import datetime as dt
import hashlib
import html
import io
import math
import re
import time
import urllib.parse

import plotly.graph_objects as go
import streamlit as st
from PIL import Image

try:
  from google import genai
  from google.genai import types

  HAS_GENAI = True
except Exception:  # package missing -> app still runs in demo mode
  HAS_GENAI = False

st.set_page_config(
    page_title="UrjaMitra | Solar & PM-KUSUM Copilot",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------
# 1. CONFIG  (all scheme numbers are editable assumptions - verify before use)
# ----------------------------------------------------------------------------
CFG = {
    "slabs": {1: 30000, 2: 60000, 3: 78000},  # PM Surya Ghar, capped at 3 kW+
    "cost_per_kw": 58000,
    "pump_cost": {3: 155000, 5: 240000, 7.5: 345000, 10: 460000},
    "array_kwp_per_hp": {"DC": 1.0, "AC": 1.25, "SURFACE": 1.25},
    "central_kusum_pct": 30,
    "grid_co2_kg_per_kwh": 0.82,
    "tariff_growth": 0.03,
    "degradation": 0.005,
    "baseline_tokens": 1800,  # rough size of a "full LLM" report, for comparison
}

STATE_DB = {
    "Haryana": {"discom": "DHBVN / UHBVN", "regulator": "HERC", "agri_agency": "HAREDA", "tariff": 6.75, "insolation": 4.6, "kusum_state_sub": 45},
    "Rajasthan": {"discom": "JVVNL / AVVNL / JdVVNL", "regulator": "RERC", "agri_agency": "RRECL", "tariff": 7.50, "insolation": 5.1, "kusum_state_sub": 30},
    "Uttar Pradesh": {"discom": "UPPCL (PVVNL / DVVNL)", "regulator": "UPERC", "agri_agency": "UPNEDA", "tariff": 7.00, "insolation": 4.5, "kusum_state_sub": 30},
    "Punjab": {"discom": "PSPCL", "regulator": "PSERC", "agri_agency": "PEDA", "tariff": 6.80, "insolation": 4.5, "kusum_state_sub": 30},
    "Delhi": {"discom": "BSES / Tata Power-DDL", "regulator": "DERC", "agri_agency": "EE&REM Delhi", "tariff": 8.00, "insolation": 4.5, "kusum_state_sub": 30},
    "Maharashtra": {"discom": "MSEDCL (Mahavitaran)", "regulator": "MERC", "agri_agency": "MEDA", "tariff": 8.50, "insolation": 4.7, "kusum_state_sub": 30},
    "Other": {"discom": "State DISCOM", "regulator": "SERC", "agri_agency": "SNA / MNRE", "tariff": 7.00, "insolation": 4.5, "kusum_state_sub": 30},
}

AUTO = "Auto (best available flash model)"

# ----------------------------------------------------------------------------
# 2. DESIGN SYSTEM (light theme - also set in .streamlit/config.toml)
# ----------------------------------------------------------------------------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+Devanagari:wght@400;500;700&display=swap');
:root{--primary:#059669;--primary-dark:#047857;--accent:#F59E0B;--card:#FFFFFF;--text:#0F172A;--muted:#64748B;--border:#E2E8F0;--radius:14px;--shadow:0 4px 20px rgba(15,23,42,.06);}
.stApp{background:linear-gradient(180deg,#F8FAFC 0%,#EFF6FF 100%);color:var(--text);font-family:'Inter','Noto Sans Devanagari',sans-serif;}
.block-container{padding-top:1.2rem;max-width:1250px;}
/* Hide menu/footer but KEEP the header: it holds the sidebar toggle button */
#MainMenu,footer{visibility:hidden;}
[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none;}
header[data-testid="stHeader"]{background:transparent;}
section[data-testid="stSidebar"]{background:#FFFFFF;border-right:1px solid var(--border);}
.hero-container{background:linear-gradient(135deg,#0F172A 0%,#1E3A8A 65%,#047857 100%);padding:30px 34px;border-radius:var(--radius);color:#fff;margin-bottom:22px;box-shadow:0 15px 35px -10px rgba(15,23,42,.4);border:1px solid rgba(255,255,255,.15);}
.hero-badge{background:rgba(245,158,11,.25);border:1px solid #F59E0B;color:#FCD34D;padding:5px 14px;border-radius:999px;font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.5px;display:inline-block;margin-bottom:12px;}
.hero-title{font-size:2.3rem;font-weight:800;margin:0;color:#fff;display:flex;align-items:center;gap:12px;}
.pulse-sun{display:inline-block;animation:pulse 2.5s infinite;}
@keyframes pulse{0%{transform:scale(1);opacity:1}50%{transform:scale(1.15);opacity:.8}100%{transform:scale(1);opacity:1}}
.hero-subtitle{font-size:1.02rem;color:#E2E8F0;margin-top:8px;}
.hero-chips{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px;}
.hero-chip{background:rgba(255,255,255,.12);padding:6px 14px;border-radius:8px;font-size:.82rem;font-weight:600;color:#F8FAFC;border:1px solid rgba(255,255,255,.1);}
.info-strip{background:var(--card);border-left:5px solid #0284C7;padding:14px 18px;border-radius:10px;box-shadow:var(--shadow);margin-bottom:18px;font-size:.9rem;border:1px solid var(--border);border-left:5px solid #0284C7;}
.kpi-card{background:var(--card);padding:20px;border-radius:var(--radius);box-shadow:var(--shadow);border:1px solid var(--border);border-top:5px solid var(--accent);height:100%;transition:transform .2s ease;}
.kpi-card:hover{transform:translateY(-3px);}
.kpi-card.green{border-top-color:var(--primary);}.kpi-card.blue{border-top-color:#3B82F6;}.kpi-card.purple{border-top-color:#8B5CF6;}
.kpi-title{font-size:.76rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;}
.kpi-value{font-size:1.75rem;font-weight:800;margin:0;line-height:1.2;}
.kpi-sub{font-size:.8rem;font-weight:600;color:var(--primary);margin-top:8px;}
div.stButton>button,div[data-testid="stFormSubmitButton"]>button{background:linear-gradient(135deg,var(--primary),var(--primary-dark));color:#fff;border:none;border-radius:10px;padding:.6rem 1.2rem;font-weight:700;box-shadow:0 4px 12px rgba(5,150,105,.25);width:100%;transition:all .2s ease;}
div.stButton>button:hover,div[data-testid="stFormSubmitButton"]>button:hover{transform:translateY(-1px);box-shadow:0 6px 16px rgba(5,150,105,.35);color:#fff;}
.stDownloadButton>button{background:transparent!important;color:var(--primary)!important;border:2px solid var(--primary)!important;border-radius:10px;font-weight:700;width:100%;}
.stDownloadButton>button:hover{background:var(--primary)!important;color:#fff!important;}
.stTabs [data-baseweb="tab-list"]{gap:8px;background:var(--border);padding:6px;border-radius:12px;}
.stTabs [data-baseweb="tab"]{border-radius:8px;padding:10px 16px;font-weight:700;color:var(--muted);}
.stTabs [aria-selected="true"]{background:var(--card)!important;color:var(--text)!important;box-shadow:var(--shadow);}
.stepper-container{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0 22px 0;}
.step-item{flex:1;min-width:170px;background:var(--card);padding:16px;border-radius:12px;border:1px solid var(--border);box-shadow:var(--shadow);}
.step-num{background:var(--primary);color:#fff;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.85rem;margin-bottom:8px;}
.step-title{font-weight:700;font-size:.92rem;margin-bottom:4px;}
.step-desc{font-size:.78rem;color:var(--muted);line-height:1.4;}
.bom-table{width:100%;border-collapse:collapse;background:var(--card);border-radius:10px;overflow:hidden;box-shadow:var(--shadow);border:1px solid var(--border);}
.bom-table th{background:#0F172A;color:#fff;padding:12px 16px;text-align:left;font-size:.85rem;}
.bom-table td{padding:12px 16px;border-bottom:1px solid var(--border);font-size:.88rem;}
.bom-table tr:nth-child(even){background:rgba(0,0,0,.02);}
.eff-bar{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0;}
.eff-chip{background:#0F172A;color:#38BDF8;padding:7px 12px;border-radius:8px;font-size:.78rem;font-family:monospace;border:1px solid #334155;}
.eff-chip.good{color:#34D399;}
.paper-letter{background:#fff;color:#1E293B;padding:36px 40px;border-radius:8px;box-shadow:0 10px 30px rgba(0,0,0,.1);font-family:'Times New Roman',serif;font-size:1.05rem;line-height:1.65;border:1px solid #CBD5E1;margin-bottom:16px;}
.app-footer{text-align:center;margin-top:36px;padding:18px;font-size:.8rem;color:var(--muted);border-top:1px solid var(--border);}
@media (max-width:768px){.hero-title{font-size:1.5rem;}.kpi-value{font-size:1.3rem;}.hero-container{padding:18px;}}
</style>
""",
    unsafe_allow_html=True,
)


def H(markup: str):
  """Render HTML on a single line (blank lines/indents break Markdown HTML)."""
  st.markdown(re.sub(r"\n\s*", "", markup), unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# 3. STATE, SECRETS, LANGUAGE
# ----------------------------------------------------------------------------
try:
  configured_key = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
  configured_key = ""

for _k, _v in {
    "rule_report": "",
    "ai_text": "",
    "report_sig": None,
    "metrics": None,
    "faq_history": [],
    "polished_text": "",
    "polished_sig": "",
}.items():
  if _k not in st.session_state:
    st.session_state[_k] = _v

_, col_lang = st.columns([4, 1])
with col_lang:
  lang = st.selectbox(
      "Language", ["English", "हिंदी (Hindi)"], label_visibility="collapsed"
  )
is_hindi = lang.startswith("हिंदी")
lang_name = "Hindi (Devanagari script)" if is_hindi else "English"


def t(en: str, hi: str) -> str:
  return hi if is_hindi else en


# ----------------------------------------------------------------------------
# 4. HERO
# ----------------------------------------------------------------------------
H(f"""
<div class="hero-container">
<div class="hero-badge">{t("🇮🇳 Built on MNRE · PM Surya Ghar · PM-KUSUM rules", "🇮🇳 एमएनआरई · पीएम सूर्य घर · पीएम-कुसुम नियमों पर आधारित")}</div>
<h1 class="hero-title"><span class="pulse-sun">☀️</span> UrjaMitra (ऊर्जा मित्र)</h1>
<p class="hero-subtitle">{t("Instant solar sizing & subsidy math · AI only where it adds value · Quote auditor · Discom letter drafter", "त्वरित सोलर साइज़िंग व सब्सिडी गणना · एआई केवल जहाँ ज़रूरी · कोटेशन ऑडिट · डिस्कॉम आवेदन पत्र")}</p>
<div class="hero-chips">
<span class="hero-chip">⚡ {t("Rule engine + targeted AI", "रूल इंजन + लक्षित एआई")}</span>
<span class="hero-chip">💡 {t("Subsidy up to ₹78,000", "सब्सिडी ₹78,000 तक")}</span>
<span class="hero-chip">🌐 English / हिंदी</span>
</div>
</div>
""")

# ----------------------------------------------------------------------------
# 5. SIDEBAR
# ----------------------------------------------------------------------------
sb = st.sidebar
sb.markdown("### ⚙️ " + t("Consumer Profile", "उपभोक्ता प्रोफ़ाइल"))

if configured_key:
  api_key = configured_key
  sb.success("🔑 " + t("API key connected securely", "API Key सुरक्षित रूप से जुड़ी है"))
else:
  api_key = sb.text_input(
      "🔑 Gemini API Key",
      type="password",
      help="Add GEMINI_API_KEY to Streamlit secrets, or paste it here.",
  )

state = sb.selectbox("📍 " + t("State", "राज्य"), list(STATE_DB.keys()))
si = STATE_DB[state]

mode_res = "🏠 " + t("Residential Rooftop (PM Surya Ghar)", "घरेलू रूफटॉप (PM Surya Ghar)")
mode_agri = "🌾 " + t("Agricultural Pump (PM-KUSUM)", "कृषि सोलर पंप (PM-KUSUM)")
is_agri = sb.radio("⚡ " + t("Sector", "श्रेणी"), [mode_res, mode_agri]) == mode_agri
sb.markdown("---")

if not is_agri:
  sb.markdown("#### 🏠 " + t("Residential Parameters", "घरेलू विवरण"))
  monthly_bill = sb.number_input(t("Avg. Monthly Power Bill (₹)", "औसत मासिक बिजली बिल (₹)"), 300, 100000, 2500, 100)
  roof_area = sb.number_input(t("Shadow-Free Roof Area (sq. ft.)", "उपलब्ध छत क्षेत्रफल (वर्ग फुट)"), 50, 20000, 350, 50)
  sanctioned_load = sb.number_input(t("Existing Sanctioned Load (kW)", "मौजूदा स्वीकृत लोड (kW)"), 1.0, 50.0, 2.0, 1.0)
else:
  sb.markdown("#### 🌾 " + t("Agricultural & Pump Specs", "कृषि एवं सिंचाई विवरण"))
  land_acres = sb.number_input(t("Irrigated Farmland (Acres)", "सिंचित भूमि (एकड़)"), 1.0, 100.0, 5.0, 1.0)
  water_depth = sb.slider(t("Water Table Depth (Feet)", "भूजल स्तर की गहराई (फीट)"), 20, 400, 120, 10)
  pump_type = sb.selectbox(
      t("Pump Type", "पंप प्रकार"),
      ["Submersible DC (सबमर्सिबल डीसी)", "Submersible AC (सबमर्सिबल एसी)", "Surface Mono-block (सरफेस पंप)"],
  )
  monthly_diesel_spend = sb.number_input(t("Monthly Diesel/Power Spend (₹)", "मासिक डीजल/बिजली खर्च (₹)"), 1000, 100000, 6000, 500)

sb.markdown("---")
sb.markdown("#### 🔍 " + t("Vendor Quote & OCR", "विक्रेता कोटेशन ऑडिट"))
vendor_quote = sb.number_input(t("Installer Quoted Total (₹)", "विक्रेता द्वारा मांगा गया कुल मूल्य (₹)"), min_value=0, value=0, step=5000)
uploaded_file = sb.file_uploader(
    "📸 " + t("Upload Quote / Bill Image (Optional)", "कोटेशन या बिल का फोटो (वैकल्पिक)"),
    type=["png", "jpg", "jpeg"],
)

# ----------------------------------------------------------------------------
# 6. AI LAYER (google-genai SDK): streaming, low-thinking, cached, fail-fast
# ----------------------------------------------------------------------------
_BLOCK = ("image", "tts", "audio", "live", "native", "robotics", "computer", "embedding", "exp", "gemma")


def _version_key(name: str):
  m = re.search(r"gemini-(\d+)(?:\.(\d+))?", name)
  major, minor = (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)
  return (major, minor, 0 if "preview" in name else 1, 0 if "lite" in name else 1)


@st.cache_data(ttl=600, show_spinner=False)
def list_models(key: str):
  """Discover real model names for this key (cached) instead of hardcoding."""
  try:
    client = genai.Client(api_key=key)
    names = []
    for m in client.models.list():
      name = m.name.replace("models/", "")
      acts = getattr(m, "supported_actions", None) or []
      if "generateContent" in acts and name.startswith("gemini") and "flash" in name and not any(b in name for b in _BLOCK):
        names.append(name)
    names = sorted(set(names), key=_version_key, reverse=True)
    return names or ["gemini-2.5-flash", "gemini-2.0-flash"]
  except Exception:
    return ["gemini-2.5-flash", "gemini-2.0-flash"]


@st.cache_resource(show_spinner=False)
def get_client(key: str):
  return genai.Client(
      api_key=key, http_options=types.HttpOptions(timeout=40_000)
  )


@st.cache_resource(show_spinner=False)
def response_cache():
  return {}


def classify(e: Exception) -> str:
  s = str(e).lower()
  if re.search(r"\b(401|403)\b", s) or "api key" in s or "api_key" in s or "permission" in s or "unauthenticated" in s:
    return "auth"
  if re.search(r"\b429\b", s) or "resource_exhausted" in s or "quota" in s or "rate limit" in s:
    return "quota"
  if re.search(r"\b(404|503)\b", s) or "not_found" in s or "unavailable" in s or "overloaded" in s:
    return "gone"
  return "other"


def friendly_error(e: Exception) -> str:
  k = classify(e)
  if k == "auth":
    return "API key was rejected. Check the key (and that the Generative Language API is enabled)."
  if k == "quota":
    return "Free-tier quota / rate limit hit (429). Wait a minute, or pick another model in the sidebar."
  if k == "gone":
    return "The selected model is unavailable. Pick another one under 'AI engine' in the sidebar."
  return f"{type(e).__name__}: {e}"


def _stream_once(model, contents, cfg, placeholder):
  t0 = time.time()
  ttft, text, in_tok, out_tok = None, "", 0, 0
  for chunk in get_client(api_key).models.generate_content_stream(model=model, contents=contents, config=cfg):
    piece = getattr(chunk, "text", None) or ""
    if piece:
      if ttft is None:
        ttft = time.time() - t0
      text += piece
      if placeholder is not None:
        placeholder.markdown(text + " ▌")
    um = getattr(chunk, "usage_metadata", None)
    if um:
      in_tok = getattr(um, "prompt_token_count", None) or in_tok
      out_tok = getattr(um, "candidates_token_count", None) or out_tok
  if placeholder is not None:
    placeholder.markdown(text)
  if not text.strip():
    raise RuntimeError("Model returned an empty answer (token budget probably spent on thinking).")
  return {"text": text, "ttft": ttft or 0.0, "in_tok": in_tok, "out_tok": out_tok}


def _call_model(model, contents, max_tokens, placeholder):
  """Try to switch thinking off / low (big latency win); fall back if the model rejects it."""
  last = None
  for variant in ({"thinking_budget": 0}, {"thinking_level": "low"}, None):
    try:
      kw = {"temperature": 0.2, "max_output_tokens": max_tokens if variant else max_tokens * 3}
      if variant:
        kw["thinking_config"] = types.ThinkingConfig(**variant)
      return _stream_once(model, contents, types.GenerateContentConfig(**kw), placeholder)
    except Exception as e:  # noqa: BLE001
      if classify(e) in ("auth", "quota", "gone"):
        raise
      last = e
  raise last


def run_llm(prompt, img=None, img_key="", placeholder=None, max_tokens=600):
  cache = response_cache()
  ck = hashlib.sha256(f"{engine_choice}|{prompt}|{img_key}".encode()).hexdigest()
  if ck in cache:
    r = dict(cache[ck])
    r.update(cached=True, ttft=0.0, latency=0.0, in_tok=0, out_tok=0)
    if placeholder is not None:
      placeholder.markdown(r["text"])
    return r

  found = list_models(api_key)
  if engine_choice != AUTO:
    models = [engine_choice] + [m for m in found if m != engine_choice][:1]
  else:
    models = found[:2]

  contents = [img, prompt] if img is not None else prompt
  t_start, errors = time.time(), []
  for m in models:
    try:
      if placeholder is not None:
        placeholder.info(f"⏳ Contacting {m} …")
      r = _call_model(m, contents, max_tokens, placeholder)
      r.update(model=m, cached=False, latency=round(time.time() - t_start, 2))
      r["ttft"] = round(r["ttft"], 2)
      cache[ck] = dict(r)
      return r
    except Exception as e:  # noqa: BLE001
      errors.append(e)
      if classify(e) in ("quota", "gone"):
        continue
      raise
  raise errors[-1]


def prep_image(f):
  img = Image.open(io.BytesIO(f.getvalue())).convert("RGB")
  img.thumbnail((1024, 1024))  # smaller image = fewer tokens, faster response
  return img


# ----------------------------------------------------------------------------
# 7. DETERMINISTIC ENGINE
# ----------------------------------------------------------------------------
def build_cashflow(net_cost, yr1_saving, years=25):
  g = (1 + CFG["tariff_growth"]) * (1 - CFG["degradation"])
  bal, series, payback = -net_cost, [-net_cost], None
  for y in range(1, years + 1):
    s = yr1_saving * g ** (y - 1)
    prev = bal
    bal += s
    if payback is None and bal >= 0 and s > 0:
      payback = (y - 1) + (-prev) / s
    series.append(round(bal))
  return series, (round(payback, 1) if payback is not None else None)


if not is_agri:
  rate, yield_kw = si["tariff"], si["insolation"]
  monthly_units = monthly_bill / rate
  req_kw = monthly_units / (yield_kw * 30)
  roof_cap = roof_area / 95.0
  raw_kw = max(1.0, min(req_kw, roof_cap))
  display_kw = max(1, min(10, math.floor(raw_kw + 0.5), math.floor(roof_cap)))
  subsidy_amount = CFG["slabs"][min(display_kw, 3)]
  bench_gross_cost = display_kw * CFG["cost_per_kw"]
  annual_units = round(display_kw * yield_kw * 365)
  used_units = min(annual_units, monthly_units * 12)  # credit only what you consume
  annual_savings = round(used_units * rate)
  offset_pct = min(100, round(annual_units / (monthly_units * 12) * 100))
  co2_tons = round(annual_units * CFG["grid_co2_kg_per_kwh"] / 1000, 1)
  capacity_label = f"{display_kw} kW Rooftop"
  capacity_sub = t(f"≈{round(display_kw * yield_kw)} units/day · {offset_pct}% of usage", f"≈{round(display_kw * yield_kw)} यूनिट/दिन · {offset_pct}% खपत")
  subsidy_sub = t("Central MNRE direct DBT", "केंद्र MNRE सीधे DBT")
  scheme_name = "PM Surya Ghar Muft Bijli Yojana"
else:
  if water_depth > 200 or land_acres > 10:
    hp = 10
  elif water_depth > 120 or land_acres > 6:
    hp = 7.5
  elif water_depth > 60 or land_acres > 3:
    hp = 5
  else:
    hp = 3
  pump_key = "DC" if "DC" in pump_type else ("AC" if "AC" in pump_type else "SURFACE")
  display_kw = round(hp * CFG["array_kwp_per_hp"][pump_key], 1)
  bench_gross_cost = CFG["pump_cost"][hp]
  total_sub_pct = CFG["central_kusum_pct"] + si["kusum_state_sub"]
  farmer_pct = max(0, 100 - total_sub_pct)
  subsidy_amount = round(bench_gross_cost * total_sub_pct / 100)
  annual_savings = round(monthly_diesel_spend * 10)
  co2_tons = round(hp * 1.4, 1)
  capacity_label = f"{hp:g} HP Pump ({display_kw:g} kWp)"
  capacity_sub = t(f"For {land_acres:g} acres @ {water_depth} ft", f"{land_acres:g} एकड़ @ {water_depth} फीट के लिए")
  subsidy_sub = f"{total_sub_pct}% ({si['agri_agency']})"
  scheme_name = f"PM-KUSUM Component-B ({si['agri_agency']})"

net_estimated_cost = max(0, bench_gross_cost - subsidy_amount)
cash_series, payback_years = build_cashflow(net_estimated_cost, annual_savings)
payback_label = f"{payback_years:g}" if payback_years is not None else ">25"


def quote_verdict():
  if vendor_quote <= 0:
    return None
  diff = vendor_quote - bench_gross_cost
  if diff > 15000:
    return ("warn", t(f"⚠️ Quote ₹{vendor_quote:,} is ₹{diff:,} ({diff / bench_gross_cost * 100:.0f}%) above the benchmark ₹{bench_gross_cost:,}. Negotiate or get a second quote.", f"⚠️ कोटेशन ₹{vendor_quote:,} बेंचमार्क ₹{bench_gross_cost:,} से ₹{diff:,} अधिक है। मोलभाव करें या दूसरा कोटेशन लें।"))
  if vendor_quote < 0.75 * bench_gross_cost:
    return ("low", t(f"⚠️ Quote ₹{vendor_quote:,} is unusually low vs benchmark ₹{bench_gross_cost:,}. Check ALMM/DCR modules, inverter brand, warranty and what is excluded.", f"⚠️ कोटेशन ₹{vendor_quote:,} बेंचमार्क ₹{bench_gross_cost:,} से काफ़ी कम है। ALMM/DCR मॉड्यूल, इन्वर्टर, वारंटी जाँचें।"))
  return ("ok", t(f"✅ Quote ₹{vendor_quote:,} is within a fair range of the benchmark ₹{bench_gross_cost:,}.", f"✅ कोटेशन ₹{vendor_quote:,} बेंचमार्क ₹{bench_gross_cost:,} के उचित दायरे में है।"))


# ----------------------------------------------------------------------------
# 8. HEADER STRIP + KPI CARDS
# ----------------------------------------------------------------------------
H(f"""
<div class="info-strip">
<b>🏛️ {t("Jurisdiction", "क्षेत्र")}:</b> {state} &nbsp;|&nbsp;
<b>⚡ {t("Utility", "डिस्कॉम")}:</b> {si['discom']} ({si['regulator']}) &nbsp;|&nbsp;
<b>☀️ {t("Insolation", "सौर विकिरण")}:</b> {si['insolation']} kWh/kW/day &nbsp;|&nbsp;
<b>📜 {t("Scheme", "योजना")}:</b> {scheme_name}
</div>
""")


def kpi(cls, title, value, sub):
  return f'<div class="kpi-card {cls}"><div class="kpi-title">{title}</div><div class="kpi-value">{value}</div><div class="kpi-sub">{sub}</div></div>'


k1, k2, k3, k4 = st.columns(4)
k1.markdown(kpi("", t("Recommended System", "सुझाई गई क्षमता"), capacity_label, "⚡ " + capacity_sub), unsafe_allow_html=True)
k2.markdown(kpi("green", t("Est. Govt Subsidy", "अनुमानित सब्सिडी"), f"₹{subsidy_amount:,}", "🏛️ " + subsidy_sub), unsafe_allow_html=True)
k3.markdown(kpi("blue", t("Est. Net Investment", "अनुमानित शुद्ध लागत"), f"₹{net_estimated_cost:,}", f"💰 {t('Benchmark', 'बेंचमार्क')} ₹{bench_gross_cost:,}"), unsafe_allow_html=True)
k4.markdown(kpi("purple", t("Est. Payback", "लागत वसूली समय"), f"{payback_label} {t('Years', 'वर्ष')}", f"🌱 ₹{annual_savings:,}/{t('yr', 'वर्ष')} · {co2_tons}T CO₂"), unsafe_allow_html=True)
st.write("")

if not is_agri:
  new_bill = max(0, round(monthly_bill * (1 - offset_pct / 100)))
  st.info(t(
      f"💡 **Bill impact (estimate):** your ₹{monthly_bill:,}/month bill falls to about ₹{new_bill:,} (before fixed charges), saving ≈ ₹{annual_savings:,} a year.",
      f"💡 **बिल पर असर (अनुमान):** ₹{monthly_bill:,}/माह का बिल लगभग ₹{new_bill:,} रह जाएगा (फ़िक्स्ड चार्ज छोड़कर), सालाना बचत ≈ ₹{annual_savings:,}।",
  ))
  if roof_area < 95:
    st.warning(t("Your shadow-free roof area is below ~95 sq. ft. per kW; even 1 kW may not fit.", "आपकी छत का क्षेत्रफल 1 kW के लिए (~95 वर्ग फुट) से कम है।"))
else:
  with st.expander("🔍 " + t("How we calculated this pump size", "पंप क्षमता की गणना कैसे हुई")):
    st.markdown(t(
        f"- **Pump size:** depth `{water_depth} ft` and `{land_acres:g} acres` → **{hp:g} HP** (tiered rule).\n"
        f"- **Solar array:** {hp:g} HP × {CFG['array_kwp_per_hp'][pump_key]} kWp/HP ({pump_key} pump assumption) = **{display_kw:g} kWp**.\n"
        f"- **Subsidy:** (30% central + {si['kusum_state_sub']}% state) × benchmark ₹{bench_gross_cost:,} = **₹{subsidy_amount:,}**; your share ≈ {farmer_pct}%.\n"
        f"- **Savings:** monthly spend ₹{monthly_diesel_spend:,} × 10 cropping months.",
        f"- **पंप क्षमता:** गहराई `{water_depth} फीट` और `{land_acres:g} एकड़` → **{hp:g} HP**।\n"
        f"- **सोलर ऐरे:** {hp:g} HP × {CFG['array_kwp_per_hp'][pump_key]} kWp/HP = **{display_kw:g} kWp**।\n"
        f"- **सब्सिडी:** (30% केंद्र + {si['kusum_state_sub']}% राज्य) × ₹{bench_gross_cost:,} = **₹{subsidy_amount:,}**; आपका हिस्सा ≈ {farmer_pct}%।\n"
        f"- **बचत:** मासिक खर्च ₹{monthly_diesel_spend:,} × 10 फसल माह।",
    ))

wa_text = f"☀️ UrjaMitra Solar Assessment ({state})\nSystem: {capacity_label}\nEst. subsidy: ₹{subsidy_amount:,}\nEst. net cost: ₹{net_estimated_cost:,}\nPayback: {payback_label} years"
wa_url = "https://api.whatsapp.com/send?text=" + urllib.parse.quote(wa_text)
H(f'<div style="margin-bottom:18px;"><a href="{wa_url}" target="_blank" style="background:#25D366;color:#fff;padding:8px 16px;border-radius:8px;text-decoration:none;font-weight:700;font-size:.85rem;">💬 {t("Share on WhatsApp", "WhatsApp पर साझा करें")}</a></div>')

# ----------------------------------------------------------------------------
# 9. AI ENGINE SIDEBAR CONTROLS (needs helpers above)
# ----------------------------------------------------------------------------
ai_ready = bool(api_key) and HAS_GENAI
engine_choice = AUTO
with sb.expander("🧠 " + t("AI engine & efficiency", "एआई इंजन व दक्षता")):
  if not HAS_GENAI:
    st.warning("`google-genai` is not installed - add it to requirements.txt. Running in demo mode.")
  demo_mode = st.checkbox(t("Demo mode (no API calls)", "डेमो मोड (बिना API)"), value=not ai_ready)
  smart_skip = st.checkbox(t("Smart-skip AI when the quote is fair", "कोटेशन उचित हो तो एआई छोड़ें"), value=True)
  if ai_ready and not demo_mode:
    engine_choice = st.selectbox("Model", [AUTO] + list_models(api_key))
use_ai = ai_ready and not demo_mode


# ----------------------------------------------------------------------------
# 10. REPORT BUILDERS (instant, 0 tokens)
# ----------------------------------------------------------------------------
def build_rule_report() -> str:
  if is_agri:
    feas = t(
        f"Water table **{water_depth} ft** and **{land_acres:g} acres** point to a **{hp:g} HP** pump. Recommended array ≈ **{display_kw:g} kWp** for a {pump_key} pump.",
        f"भूजल **{water_depth} फीट** और **{land_acres:g} एकड़** के लिए **{hp:g} HP** पंप उपयुक्त है। सुझाया गया ऐरे ≈ **{display_kw:g} kWp**।",
    )
  else:
    feas = t(
        f"Your bill implies ~**{req_kw:.1f} kW**; your roof can host ~**{roof_cap:.1f} kW**. A **{display_kw} kW** plant makes ~**{annual_units:,} units/yr** (≈{offset_pct}% of your usage).",
        f"आपके बिल के अनुसार ~**{req_kw:.1f} kW** चाहिए; छत पर ~**{roof_cap:.1f} kW** लग सकता है। **{display_kw} kW** प्लांट से ~**{annual_units:,} यूनिट/वर्ष** (≈{offset_pct}% खपत)।",
    )
    if display_kw > sanctioned_load:
      feas += t(
          f" ⚠️ This exceeds your sanctioned load ({sanctioned_load:g} kW): apply for load enhancement with {si['discom']}.",
          f" ⚠️ यह स्वीकृत लोड ({sanctioned_load:g} kW) से अधिक है: {si['discom']} में लोड वृद्धि हेतु आवेदन करें।",
      )
  v = quote_verdict()
  quote = v[1] if v else t("No installer quote entered. Enter one in the sidebar to audit it.", "कोई कोटेशन दर्ज नहीं है। ऑडिट के लिए साइडबार में दर्ज करें।")
  comp = t(
      "Only **ALMM-listed, DCR-compliant** modules qualify for the central subsidy. Ask for cell + module manufacturer certificates and the DCR declaration before paying any advance.",
      "केंद्रीय सब्सिडी केवल **ALMM-सूचीबद्ध व DCR-अनुरूप** मॉड्यूल पर मिलती है। अग्रिम भुगतान से पहले सेल व मॉड्यूल निर्माता प्रमाणपत्र व DCR घोषणा माँगें।",
  )
  prot = t(
      "3 separate chemical earthing pits (DC, AC, lightning arrestor, each < 5 Ω) · lightning arrestor · DCDB/ACDB with Type-2 surge protection · hot-dip GI structure (min 80 µm).",
      "3 अलग केमिकल अर्थिंग पिट (DC, AC, LA; प्रत्येक < 5 Ω) · लाइटनिंग अरेस्टर · Type-2 सर्ज प्रोटेक्शन सहित DCDB/ACDB · हॉट-डिप GI स्ट्रक्चर (न्यूनतम 80 µm)।",
  )
  return (
      f"### ☀️ {t('Instant Engineering Audit', 'त्वरित इंजीनियरिंग ऑडिट')} · {scheme_name}\n\n"
      f"**1. {t('Feasibility', 'व्यवहार्यता')}** - {feas}\n\n"
      f"**2. {t('Quote audit', 'कोटेशन ऑडिट')}** - {quote}\n\n"
      f"**3. {t('Compliance', 'अनुपालन')}** - {comp}\n\n"
      f"**4. {t('Protection checklist', 'सुरक्षा चेकलिस्ट')}** - {prot}\n"
  )


def demo_insights() -> str:
  return t(
      f"- **Feasibility:** {state} gets ~{si['insolation']} kWh/kW/day, so a {capacity_label} setup is well supported.\n"
      f"- **Subsidy:** estimated ₹{subsidy_amount:,} under {scheme_name}; keep Aadhaar-linked bank details ready for DBT.\n"
      f"- **Quote:** compare line items against the ₹{bench_gross_cost:,} benchmark.\n\n"
      "_Demo mode: sample text, no API call. Add a Gemini key for live analysis._",
      f"- **व्यवहार्यता:** {state} में ~{si['insolation']} kWh/kW/दिन मिलता है, इसलिए {capacity_label} उपयुक्त है।\n"
      f"- **सब्सिडी:** {scheme_name} में अनुमानित ₹{subsidy_amount:,}; DBT के लिए आधार-लिंक्ड बैंक खाता तैयार रखें।\n"
      f"- **कोटेशन:** ₹{bench_gross_cost:,} बेंचमार्क से लाइन-आइटम मिलाएँ।\n\n"
      "_डेमो मोड: नमूना पाठ, कोई API कॉल नहीं। लाइव विश्लेषण के लिए Gemini key जोड़ें।_",
  )


def show_metrics(slot):
  m = st.session_state.metrics
  if not m:
    return
  total = m["in"] + m["out"]
  saved = max(0, round((1 - total / CFG["baseline_tokens"]) * 100))
  chips = [
      f'<span class="eff-chip">⚡ TTFT {m["ttft"]}s</span>',
      f'<span class="eff-chip">⏱ {m["latency"]}s</span>',
      f'<span class="eff-chip">🔤 {m["in"]} in / {m["out"]} out tokens</span>',
      f'<span class="eff-chip good">📉 ~{saved}% {t("fewer tokens than a full-LLM report", "कम टोकन (पूर्ण-LLM रिपोर्ट की तुलना में)")}</span>',
      f'<span class="eff-chip">🧠 {html.escape(m["note"])}</span>',
  ]
  slot.markdown(f'<div class="eff-bar">{"".join(chips)}</div>', unsafe_allow_html=True)


def build_letter() -> str:
  today = dt.date.today().strftime("%d %B %Y")
  addr = f"Premises/Khasra No. XXX, Village/Sector XXXX, District XXXX, {state}"
  if is_hindi:
    to = f"परियोजना अधिकारी, {si['agri_agency']} / {si['discom']}" if is_agri else f"उप-मंडल अधिकारी (SDO), {si['discom']}"
    if is_agri:
      body = (f"मैं, XXXX, पता {addr}, खसरा/खाता संख्या XXXXXXXXXXXX, {land_acres:g} एकड़ सिंचित भूमि (भूजल स्तर लगभग {water_depth} फीट) का स्वामी/किसान हूँ। "
              f"मैं {scheme_name} के अंतर्गत {capacity_label} स्टैंडअलोन सोलर वॉटर पंप ({pump_type.split('(')[0].strip()}) लगवाना चाहता/चाहती हूँ।\n\n"
              "अनुरोध है कि आवेदन की जाँच कर स्थल-सत्यापन कराएँ और स्वीकृति प्रदान करें। मैं निर्धारित लाभार्थी अंशदान जमा करूँगा/करूँगी तथा केवल सूचीबद्ध विक्रेता से ALMM/DCR-अनुरूप उपकरण लगवाऊँगा/लगवाऊँगी।")
      encl = "भूमि अभिलेख, आधार कार्ड, बैंक पासबुक, फोटो"
    else:
      body = (f"मैं, XXXX, उपभोक्ता खाता संख्या XXXXXXXXXXXX, मीटर संख्या XXXXXXXX, स्वीकृत लोड {sanctioned_load:g} kW, निवासी {addr}, "
              f"{scheme_name} के अंतर्गत {display_kw} kW ग्रिड-कनेक्टेड रूफटॉप सोलर प्लांट लगवाना चाहता/चाहती हूँ।\n\n"
              "अनुरोध है कि (1) तकनीकी व्यवहार्यता स्वीकृति, (2) आवश्यकता होने पर लोड वृद्धि, तथा (3) कमीशनिंग के बाद नेट-मीटरिंग व बाइ-डायरेक्शनल मीटर की व्यवस्था करें। "
              f"मैं {si['regulator']} के नियमों का पालन करूँगा/करूँगी और सूचीबद्ध विक्रेता से ALMM/DCR-अनुरूप मॉड्यूल लगवाऊँगा/लगवाऊँगी।")
      encl = "नवीनतम बिजली बिल, आधार कार्ड, स्वामित्व प्रमाण, फोटो"
    return (f"सेवा में,\n{to},\n{state}.\n\nदिनांक: {today}\n\nविषय: {scheme_name} के अंतर्गत {capacity_label} सोलर संयंत्र हेतु आवेदन।\n\nमहोदय/महोदया,\n\n{body}\n\n"
            f"संलग्न: {encl}\n\nभवदीय,\nXXXX\nमोबाइल: +91-XXXXXXXXXX\nईमेल: xxxx@email.com")
  to = f"The Project Officer, {si['agri_agency']} / {si['discom']}" if is_agri else f"The Sub-Divisional Officer (SDO), {si['discom']}"
  if is_agri:
    body = (f"I, XXXX, a farmer of {addr}, Khasra/Khata No. XXXXXXXXXXXX, cultivating {land_acres:g} acres of irrigated land (water table about {water_depth} ft), "
            f"wish to install a standalone {capacity_label} solar water pump ({pump_type.split('(')[0].strip()}) under {scheme_name}.\n\n"
            "I request you to kindly examine my application, arrange site verification and grant sanction. I undertake to pay the prescribed beneficiary share and to use only ALMM/DCR-compliant equipment from an empanelled vendor.")
    encl = "Land records, Aadhaar card, bank passbook, photograph"
  else:
    body = (f"I, XXXX, Consumer Account No. XXXXXXXXXXXX, Meter No. XXXXXXXX, sanctioned load {sanctioned_load:g} kW, residing at {addr}, "
            f"wish to install a {display_kw} kW grid-connected rooftop solar plant under {scheme_name}.\n\n"
            "I request you to kindly (1) grant technical feasibility approval, (2) process a load enhancement if required, and (3) arrange net-metering and a bidirectional meter after commissioning. "
            f"I will comply with {si['regulator']} regulations and use ALMM/DCR-compliant modules from an empanelled vendor.")
    encl = "Latest electricity bill, Aadhaar card, proof of ownership, photograph"
  return (f"To,\n{to},\n{state}.\n\nDate: {today}\n\nSubject: Application for {capacity_label} solar installation under {scheme_name}.\n\nRespected Sir/Madam,\n\n{body}\n\n"
          f"Enclosures: {encl}\n\nYours faithfully,\nXXXX\nMobile: +91-XXXXXXXXXX\nEmail: xxxx@email.com")


# ----------------------------------------------------------------------------
# 11. TABS
# ----------------------------------------------------------------------------
tab_report, tab_roi, tab_letter, tab_faq = st.tabs([
    "📑 " + t("AI Report & Quote Audit", "एआई रिपोर्ट व कोटेशन ऑडिट"),
    "📈 " + t("25-Year ROI & BoM", "25-वर्षीय बचत व BoM"),
    "✉️ " + t("Official Application", "आधिकारिक आवेदन पत्र"),
    "💬 " + t("Solar Copilot Q&A", "सौर सहायक (Q&A)"),
])

# ---- TAB 1 -----------------------------------------------------------------
with tab_report:
  verdict = quote_verdict()
  if uploaded_file is not None:
    st.success("📸 " + t("Quote image attached - the AI will read it (price, panel brand, inverter).", "कोटेशन इमेज संलग्न है - एआई इसे पढ़ेगा (मूल्य, पैनल ब्रांड, इन्वर्टर)।"))
  elif verdict:
    {"warn": st.warning, "low": st.warning, "ok": st.success}[verdict[0]](verdict[1])

  st.markdown("#### 🗺️ " + t("Subsidy & Installation Roadmap", "सब्सिडी व स्थापना रोडमैप") + f" · {scheme_name}")
  if not is_agri:
    steps = [
        (t("Portal registration", "पोर्टल पंजीकरण"), t("Register on pmsuryaghar.gov.in with consumer details.", "pmsuryaghar.gov.in पर उपभोक्ता विवरण से पंजीकरण करें।")),
        (t("DISCOM feasibility", "डिस्कॉम व्यवहार्यता"), t("Apply online to the local utility for grid approval.", "ग्रिड स्वीकृति हेतु स्थानीय डिस्कॉम में ऑनलाइन आवेदन करें।")),
        (t("Vendor installation", "विक्रेता द्वारा स्थापना"), t("Install through an MNRE-empanelled vendor.", "MNRE-सूचीबद्ध विक्रेता से प्लांट लगवाएँ।")),
        (t("Net-meter inspection", "नेट-मीटर निरीक्षण"), t("Utility inspects the site and fits a bidirectional meter.", "डिस्कॉम निरीक्षण कर बाइ-डायरेक्शनल मीटर लगाता है।")),
        (t("Subsidy via DBT", "सब्सिडी (DBT)"), t("Subsidy is credited to your bank account after commissioning is verified.", "कमीशनिंग सत्यापन के बाद सब्सिडी बैंक खाते में आती है।")),
    ]
  else:
    steps = [
        (t("State agency portal", "राज्य एजेंसी पोर्टल"), t(f"Apply on the {si['agri_agency']} portal with land records.", f"भूमि अभिलेख के साथ {si['agri_agency']} पोर्टल पर आवेदन करें।")),
        (t("Site verification", "स्थल सत्यापन"), t("Officials verify the land and water source.", "अधिकारी भूमि व जल स्रोत का सत्यापन करते हैं।")),
        (t("Pay your share", "अपना हिस्सा जमा करें"), t(f"Pay your ~{farmer_pct}% beneficiary share as per state process.", f"राज्य प्रक्रिया अनुसार अपना ~{farmer_pct}% लाभार्थी अंश जमा करें।")),
        (t("Commissioning", "कमीशनिंग"), t("Vendor installs and commissions the pump; remaining subsidy is released.", "विक्रेता पंप लगाकर चालू करता है; शेष सब्सिडी जारी होती है।")),
    ]
  H('<div class="stepper-container">' + "".join(f'<div class="step-item"><div class="step-num">{i}</div><div class="step-title">{a}</div><div class="step-desc">{b}</div></div>' for i, (a, b) in enumerate(steps, 1)) + "</div>")

  clicked = st.button("🚀 " + t("Generate Engineering & Subsidy Report", "इंजीनियरिंग व सब्सिडी रिपोर्ट तैयार करें"))
  metrics_slot = st.empty()
  sig = (state, is_agri, display_kw, vendor_quote, uploaded_file.name if uploaded_file else "", is_hindi)

  if clicked:
    st.session_state.rule_report = build_rule_report()
    st.session_state.report_sig = sig
    st.session_state.ai_text = ""
    st.session_state.metrics = None

  if st.session_state.rule_report:
    if st.session_state.report_sig != sig:
      st.caption("ℹ️ " + t("Inputs changed since this report - click Generate to refresh.", "इनपुट बदल गए हैं - रिपोर्ट अपडेट करने हेतु Generate दबाएँ।"))
    st.markdown(st.session_state.rule_report)

  ai_slot = st.empty()
  ai_err = None

  def render_ai(text):
    with ai_slot.container():
      st.markdown("#### ✨ " + t("AI Insights", "एआई इनसाइट्स"))
      st.markdown(text)

  if clicked:
    skip_ai = smart_skip and verdict is not None and verdict[0] == "ok" and uploaded_file is None
    if skip_ai:
      st.session_state.metrics = {"ttft": 0.0, "latency": 0.0, "in": 0, "out": 0, "note": "AI skipped - rule engine was enough"}
      ai_slot.info("⚡ " + t("Quote is fair and no image attached, so no AI call was needed (0 tokens).", "कोटेशन उचित है और कोई इमेज नहीं, इसलिए एआई कॉल की ज़रूरत नहीं पड़ी (0 टोकन)।"))
    elif not use_ai:
      st.session_state.ai_text = demo_insights()
      st.session_state.metrics = {"ttft": 0.0, "latency": 0.0, "in": 0, "out": 0, "note": "Demo mode - no API call"}
      render_ai(st.session_state.ai_text)
    else:
      try:
        img = prep_image(uploaded_file) if uploaded_file else None
        img_key = hashlib.md5(uploaded_file.getvalue()).hexdigest() if uploaded_file else ""
        img_line = "An image of the installer quote/bill is attached: extract the quoted price, panel brand/wattage and inverter, and audit them against the benchmark." if img else ""
        prompt = (
            f"You are UrjaMitra, a solar engineering consultant for Indian government schemes. Reply in {lang_name}. Max 150 words, no preamble, no headings.\n"
            f"Give exactly 3 bullets: (1) the main feasibility risk for this profile, (2) one subsidy-claim pitfall for {scheme_name}, (3) a quote audit against the benchmark. {img_line}\n"
            f"Facts already computed (do not recompute): state {state}; system {capacity_label}; est. subsidy Rs {subsidy_amount:,}; est. net cost Rs {net_estimated_cost:,}; "
            f"benchmark Rs {bench_gross_cost:,}; installer quote {('Rs ' + format(vendor_quote, ',')) if vendor_quote else 'not provided'}."
        )
        with ai_slot.container():
          st.markdown("#### ✨ " + t("AI Insights", "एआई इनसाइट्स"))
          live = st.empty()
          res = run_llm(prompt, img, img_key, live, max_tokens=500)
        st.session_state.ai_text = res["text"]
        st.session_state.metrics = {
            "ttft": res["ttft"], "latency": res["latency"], "in": res["in_tok"], "out": res["out_tok"],
            "note": "cache hit" if res["cached"] else res["model"],
        }
      except Exception as e:  # noqa: BLE001
        ai_err = friendly_error(e)
  elif st.session_state.ai_text:
    render_ai(st.session_state.ai_text)

  show_metrics(metrics_slot)
  if ai_err:
    st.error("❌ " + ai_err)
    st.caption(t("The instant audit above still works without AI.", "ऊपर का त्वरित ऑडिट बिना एआई के भी काम करता है।"))

  if st.session_state.rule_report:
    st.download_button(
        "📥 " + t("Download report (.md)", "रिपोर्ट डाउनलोड करें (.md)"),
        data=st.session_state.rule_report + "\n\n" + st.session_state.ai_text,
        file_name=f"UrjaMitra_Report_{state}_{display_kw:g}kW.md",
        mime="text/markdown",
    )

  with st.expander("💡 " + t("How UrjaMitra uses AI efficiently", "UrjaMitra एआई का कुशल उपयोग कैसे करता है")):
    st.markdown(t(
        "- **Deterministic core:** sizing, subsidy slabs, ROI, BoM, roadmap and the application letter are computed in Python - instant, free, reproducible.\n"
        "- **Targeted LLM calls:** only short insights, quote-image audit, letter polish and Q&A; thinking is switched off/low, output is capped, images are downscaled.\n"
        "- **Smart skip + cache:** fair quote with no image → no AI call; identical requests are served from cache with 0 tokens.\n"
        "- **Fail fast:** real model names are discovered for your key, with one fallback; errors are shown instead of silent retries.",
        "- **डिटरमिनिस्टिक कोर:** साइज़िंग, सब्सिडी, ROI, BoM, रोडमैप और आवेदन पत्र Python में तुरंत बनते हैं।\n"
        "- **लक्षित LLM कॉल:** केवल छोटे इनसाइट्स, कोटेशन-इमेज ऑडिट, पत्र सुधार और Q&A; थिंकिंग कम/बंद, आउटपुट सीमित, इमेज छोटी।\n"
        "- **स्मार्ट स्किप + कैश:** उचित कोटेशन व इमेज नहीं → एआई कॉल नहीं; वही अनुरोध कैश से (0 टोकन)।\n"
        "- **फ़ेल-फ़ास्ट:** आपकी key के असली मॉडल खोजे जाते हैं, एक फ़ॉलबैक के साथ।",
    ))

# ---- TAB 2 -----------------------------------------------------------------
def show_chart(fig):
  try:
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
  except TypeError:  # older Streamlit
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def style_fig(fig, h=290):
  fig.update_layout(
      margin=dict(l=10, r=10, t=10, b=10), height=h,
      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
      font=dict(family="Inter, sans-serif", color="#334155"),
  )
  return fig


with tab_roi:
  c1, c2 = st.columns(2)
  with c1:
    st.markdown("#### 📈 " + t("25-Year Cumulative Savings (₹)", "25-वर्षीय संचयी बचत (₹)"))
    fig = go.Figure(go.Scatter(
        x=list(range(0, 26)), y=cash_series, mode="lines", fill="tozeroy",
        line=dict(color="#10B981", width=3), fillcolor="rgba(16,185,129,.18)",
        hovertemplate="Year %{x}<br>₹%{y:,.0f}<extra></extra>",
    ))
    if payback_years is not None:
      fig.add_vline(x=payback_years, line_dash="dash", line_color="#F59E0B", annotation_text=f"Payback {payback_years:g} yr", annotation_position="top left")
    fig.update_xaxes(title="Year", showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(148,163,184,.25)")
    show_chart(style_fig(fig))
    st.caption(t(f"Assumes {CFG['tariff_growth'] * 100:g}% yearly tariff growth and {CFG['degradation'] * 100:g}% panel degradation.", f"मान्यता: {CFG['tariff_growth'] * 100:g}% वार्षिक टैरिफ वृद्धि और {CFG['degradation'] * 100:g}% पैनल क्षरण।"))
    st.info(t(f"💎 **25-year net benefit:** ₹{cash_series[-1]:,} after recovering your ₹{net_estimated_cost:,} investment.", f"💎 **25 वर्ष का शुद्ध लाभ:** ₹{cash_series[-1]:,} (₹{net_estimated_cost:,} निवेश वसूलने के बाद)।"))
  with c2:
    st.markdown("#### 🥧 " + t("Subsidy vs Your Investment", "सब्सिडी बनाम आपका निवेश"))
    pie = go.Figure(go.Pie(labels=[t("Govt subsidy", "सरकारी सब्सिडी"), t("Your share", "आपका हिस्सा")], values=[subsidy_amount, net_estimated_cost], hole=0.55, marker=dict(colors=["#10B981", "#3B82F6"])))
    pie.update_layout(legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"))
    show_chart(style_fig(pie))

  if vendor_quote > 0:
    st.markdown("#### 📊 " + t("Installer Quote vs Benchmark", "कोटेशन बनाम बेंचमार्क"))
    labels = [t("Installer quote", "विक्रेता कोटेशन"), t("Benchmark (gross)", "बेंचमार्क (कुल)"), t("Net after subsidy", "सब्सिडी के बाद शुद्ध")]
    bar = go.Figure(go.Bar(x=labels, y=[vendor_quote, bench_gross_cost, net_estimated_cost], marker_color=["#EF4444" if vendor_quote > bench_gross_cost + 15000 else "#10B981", "#3B82F6", "#F59E0B"], text=[f"₹{v:,}" for v in (vendor_quote, bench_gross_cost, net_estimated_cost)], textposition="outside"))
    show_chart(style_fig(bar, 260))

  st.markdown("---")
  st.markdown("#### ⚡ " + t("Electrical BoM & Safety Specs", "इलेक्ट्रिकल BoM व सुरक्षा मानक"))
  if not is_agri and display_kw > sanctioned_load:
    st.warning(t(f"⚠️ **Load enhancement required:** plant ({display_kw} kW) exceeds sanctioned load ({sanctioned_load:g} kW). Apply with {si['discom']}.", f"⚠️ **लोड वृद्धि आवश्यक:** प्लांट ({display_kw} kW) स्वीकृत लोड ({sanctioned_load:g} kW) से अधिक है। {si['discom']} में आवेदन करें।"))
  phase = "Single Phase (230V AC)" if (not is_agri and display_kw <= 3) else "Three Phase (415V AC)"
  panels = max(2, round(display_kw * 1000 / 545))
  rows = [
      ("☀️", t("Solar PV modules", "सोलर पीवी मॉड्यूल"), f"{panels} × 545 Wp Mono-PERC / TOPCon (ALMM &amp; DCR certified)"),
      ("🔌", t("Pump controller / VFD", "पंप कंट्रोलर / VFD") if is_agri else t("Grid-tied inverter", "ग्रिड-टाई इन्वर्टर"), f"{display_kw:g} kW, {phase}, IP65, &gt;97.5% efficiency"),
      ("🏗️", t("Mounting structure", "माउंटिंग स्ट्रक्चर"), "Hot-dip galvanised iron (min 80 microns), 150 km/h wind rated"),
      ("🧵", t("DC cable", "डीसी केबल"), "4 sq.mm EN 50618 tinned copper, UV &amp; XLPO insulated"),
      ("🛡️", "DCDB", "600V/1000V DC MCB + 15A fuse + Type-2 DC SPD"),
      ("⚡", "ACDB", f"{'32A DP' if (not is_agri and display_kw <= 3) else '32A TPN'} MCB + Type-2 AC SPD"),
      ("🌍", t("Earthing &amp; lightning", "अर्थिंग व लाइटनिंग"), "3 separate chemical earthing pits (DC, AC, LA) &lt; 5 Ω + ESE/spike lightning arrestor"),
  ]
  H('<table class="bom-table"><tr><th>' + t("Component", "घटक") + "</th><th>" + t("Specification / Standard", "विनिर्देश / मानक") + "</th></tr>" + "".join(f"<tr><td>{i} {n}</td><td>{s}</td></tr>" for i, n, s in rows) + "</table>")

# ---- TAB 3 -----------------------------------------------------------------
with tab_letter:
  st.write("📄 " + t(f"A print-ready application to {si['agri_agency'] if is_agri else si['discom']} is generated instantly from your inputs (XXXX = fill in your details).", f"आपके इनपुट से {si['agri_agency'] if is_agri else si['discom']} के लिए आवेदन पत्र तुरंत तैयार है (XXXX = अपना विवरण भरें)।"))
  base_letter = build_letter()
  letter_sig = hashlib.md5(base_letter.encode()).hexdigest()
  shown = st.session_state.polished_text if st.session_state.polished_sig == letter_sig else base_letter
  cl, cr = st.columns([3, 1])
  with cl:
    st.markdown(f'<div class="paper-letter">{html.escape(shown).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
  with cr:
    st.markdown("#### " + t("Actions", "कार्य"))
    st.download_button("📥 " + t("Download (.txt)", "डाउनलोड (.txt)"), data=shown, file_name=f"Solar_Application_{state}.txt", mime="text/plain")
    if st.button("✨ " + t("Polish with AI", "एआई से परिष्कृत करें")):
      if not use_ai:
        st.info(t("Demo mode: connect a Gemini key to polish the wording.", "डेमो मोड: भाषा सुधारने हेतु Gemini key जोड़ें।"))
      else:
        try:
          with st.spinner(t("Polishing…", "परिष्कृत किया जा रहा है…")):
            res = run_llm(
                f"Rewrite this Indian government application letter in a more formal, polished administrative style. Keep the language ({lang_name}), every XXXX placeholder, all facts and the structure unchanged. Output only the letter, no commentary.\n\n{base_letter}",
                max_tokens=900,
            )
          st.session_state.polished_text = res["text"].strip()
          st.session_state.polished_sig = letter_sig
          st.rerun()
        except Exception as e:  # noqa: BLE001
          st.error("❌ " + friendly_error(e))

# ---- TAB 4 -----------------------------------------------------------------
with tab_faq:
  st.markdown("#### 💬 " + t("Ask the MNRE & Discom Copilot", "पीएम सूर्य घर / पीएम-कुसुम सहायक से पूछें"))
  quick = [t("Are DCR panels mandatory?", "क्या DCR पैनल अनिवार्य हैं?"), t("How does net metering work?", "नेट मीटरिंग कैसे काम करती है?"), t("Is load enhancement needed?", "क्या लोड वृद्धि ज़रूरी है?")]
  qcols = st.columns(len(quick))
  for col, qtext in zip(qcols, quick):
    if col.button(qtext, key=f"quick_{qtext}"):
      st.session_state.pending_q = qtext
  with st.form("ask_form", clear_on_submit=True):
    typed = st.text_input(t("Or type your own question:", "या अपना प्रश्न लिखें:"))
    sent = st.form_submit_button("⚡ " + t("Get answer", "उत्तर पाएँ"))
  question = st.session_state.pop("pending_q", None) or (typed.strip() if sent and typed.strip() else None)

  start_idx = 0
  if question:
    st.markdown(f"**🧑 {question}**")
    live = st.empty()
    answer = ""
    if not use_ai:
      answer = t("_Demo mode:_ connect a Gemini key for live answers. In general, central subsidy requires ALMM-listed, DCR-compliant modules; always confirm details with your DISCOM / state agency.", "_डेमो मोड:_ लाइव उत्तर हेतु Gemini key जोड़ें। सामान्यतः केंद्रीय सब्सिडी हेतु ALMM-सूचीबद्ध, DCR-अनुरूप मॉड्यूल ज़रूरी हैं; विवरण अपने डिस्कॉम/राज्य एजेंसी से पुष्टि करें।")
      live.markdown(answer)
    else:
      try:
        res = run_llm(
            f"You are UrjaMitra, a solar policy copilot for {state} ({si['discom']}, regulator {si['regulator']}). Answer in {lang_name}, practical, max 90 words. "
            f"Scheme in context: {scheme_name}. Do not invent subsidy figures or rules; if unsure, say to verify with the DISCOM/state agency.\nQuestion: {question}",
            placeholder=live, max_tokens=400,
        )
        answer = res["text"]
        st.session_state.metrics = {"ttft": res["ttft"], "latency": res["latency"], "in": res["in_tok"], "out": res["out_tok"], "note": "cache hit" if res["cached"] else res["model"]}
        show_metrics(st.empty())
      except Exception as e:  # noqa: BLE001
        st.error("❌ " + friendly_error(e))
    if answer:
      st.session_state.faq_history.insert(0, (question, answer))
      start_idx = 1
    st.write("---")

  for q, a in st.session_state.faq_history[start_idx:]:
    st.markdown(f"**🧑 {q}**")
    st.markdown(a)
    st.write("---")

H(f'<div class="app-footer">⚠️ <b>{t("Disclaimer", "अस्वीकरण")}:</b> {t("Estimates for guidance only. Scheme parameters are configurable assumptions - verify subsidy, specifications and tariffs with MNRE / your DISCOM before buying or installing.", "केवल मार्गदर्शन हेतु अनुमान। योजना पैरामीटर बदले जा सकने वाली मान्यताएँ हैं - खरीद/स्थापना से पहले MNRE / अपने डिस्कॉम से पुष्टि करें।")}</div>')   
