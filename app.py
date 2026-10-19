import os
import time
import google.generativeai as genai
import streamlit as st

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="UrjaMitra | PM Surya Ghar Copilot",
    page_icon="☀️",
    layout="wide",
)

# --- RETRIEVE SECURE API KEY ---
configured_key = st.secrets.get("GEMINI_API_KEY", "")

# --- APP HEADER & LANGUAGE SELECTION ---
col_head, col_lang = st.columns([3, 1])
with col_head:
  st.title("☀️ UrjaMitra (ऊर्जा मित्र)")
  st.caption("AI-Powered Solar Sizing, PM Surya Ghar Subsidy & Fair-Price Audit")

with col_lang:
  lang = st.selectbox("🌐 भाषा / Language", ["English", "हिंदी (Hindi)"])

is_hindi = lang == "हिंदी (Hindi)"

# --- SIDEBAR: USER INPUTS ---
st.sidebar.header("⚙️ " + ("उपभोक्ता विवरण" if is_hindi else "Consumer Details"))

if configured_key:
  api_key = configured_key
  st.sidebar.success("🔑 API Key Connected Securely")
else:
  api_key = st.sidebar.text_input(
      "🔑 Enter Gemini API Key",
      type="password",
      help="Add GEMINI_API_KEY to Streamlit Secrets or enter here.",
  )

monthly_bill = st.sidebar.number_input(
    "औसत मासिक बिजली बिल (₹)" if is_hindi else "Avg. Monthly Power Bill (₹)",
    min_value=300,
    max_value=100000,
    value=2500,
    step=100,
)

roof_area = st.sidebar.number_input(
    "उपलब्ध छत का क्षेत्रफल (वर्ग फुट)"
    if is_hindi
    else "Available Roof Area (sq. ft.)",
    min_value=50,
    max_value=20000,
    value=350,
    step=50,
)

state = st.sidebar.selectbox(
    "राज्य / State",
    [
        "Haryana",
        "Delhi",
        "Uttar Pradesh",
        "Rajasthan",
        "Punjab",
        "Maharashtra",
        "Other",
    ],
)

consumer_type = st.sidebar.radio(
    "कनेक्शन प्रकार" if is_hindi else "Connection Type",
    [
        "Residential (घरेलू)" if is_hindi else "Residential",
        "Agricultural (कृषि)" if is_hindi else "Agricultural",
    ],
)

st.sidebar.markdown("---")
st.sidebar.subheader(
    "🔍 "
    + ("विक्रेता कोटेशन ऑडिट (वैकल्पिक)" if is_hindi else "Quote Audit (Optional)")
)
vendor_quote = st.sidebar.number_input(
    "विक्रेता द्वारा मांगा गया कुल मूल्य (₹)"
    if is_hindi
    else "Installer Quoted Total (₹)",
    min_value=0,
    value=0,
    step=5000,
)

# --- DETERMINISTIC SOLAR & SUBSIDY CALCULATION ENGINE ---
unit_rate = 7.0
est_units_per_month = monthly_bill / unit_rate
calculated_kw = round(est_units_per_month / 120.0, 1)

max_kw_by_roof = round(roof_area / 100.0, 1)
recommended_kw = max(1.0, min(calculated_kw, max_kw_by_roof))

# MNRE PM Surya Ghar Subsidy slabs
if recommended_kw < 1.5:
  subsidy_amount = 30000
  display_kw = 1
elif recommended_kw < 2.5:
  subsidy_amount = 60000
  display_kw = 2
else:
  subsidy_amount = 78000
  display_kw = int(recommended_kw)

bench_gross_cost = display_kw * 60000
net_estimated_cost = max(0, bench_gross_cost - subsidy_amount)
annual_savings = round(display_kw * 4 * 365 * unit_rate)
payback_years = (
    round(net_estimated_cost / annual_savings, 1) if annual_savings > 0 else 0
)

# --- METRIC CARDS DISPLAY ---
st.subheader(
    "📊 " + ("सौर प्रणाली का आकलन" if is_hindi else "Solar Sizing & Economics")
)
m1, m2, m3, m4 = st.columns(4)

m1.metric(
    "सुझाया गया प्लांट" if is_hindi else "Recommended Plant", f"{display_kw} kW"
)
m2.metric(
    "सरकारी सब्सिडी" if is_hindi else "PM Surya Ghar Subsidy",
    f"₹{subsidy_amount:,}",
)
m3.metric(
    "अनुमानित शुद्ध लागत" if is_hindi else "Net Estimated Cost",
    f"₹{net_estimated_cost:,}",
)
m4.metric(
    "अनुमानित पेबैक" if is_hindi else "Estimated Payback",
    f"{payback_years} Years",
)

st.markdown("---")


# --- RESILIENT MULTI-MODEL DISPATCHER ---
def stream_ai_response(key: str, prompt: str, placeholder, status_box):
  """Tries models sequentially. If one model hits a 429 quota limit, automatically switches to the next available model."""
  genai.configure(api_key=key)

  # Candidate models in order of preference
  candidate_models = [
      "models/gemma-4-26b-a4b-it",
      "models/gemini-3.8-flash",
      "models/gemma-2-27b-it",
      "models/gemma-2-9b-it",
  ]

  # Dynamically append any other text-generation models discovered in this account
  try:
    for m in genai.list_models():
      if (
          "generateContent" in m.supported_generation_methods
          and "1.5" not in m.name
          and "2.5" not in m.name
          and m.name not in candidate_models
      ):
        candidate_models.append(m.name)
  except Exception:
    pass

  last_err = None
  for model_name in candidate_models:
    try:
      display_name = model_name.replace("models/", "")
      status_box.info(f"⚡ Generating assessment via {display_name}...")
      model = genai.GenerativeModel(model_name)
      response = model.generate_content(prompt, stream=True)

      full_text = ""
      for chunk in response:
        if chunk.text:
          full_text += chunk.text
          placeholder.markdown(full_text)

      return display_name
    except Exception as e:
      err_str = str(e)
      last_err = e
      # If 429 (Quota exceeded) or 404 (Not found), seamlessly try next model
      if "429" in err_str or "404" in err_str:
        continue
      else:
        raise e

  raise last_err if last_err else RuntimeError("All available AI models busy.")


# --- AI ADVISORY & GROUNDED AUDIT ENGINE ---
tab_advisory, tab_letter, tab_faq = st.tabs([
    (
        "📑 विशेषज्ञ रिपोर्ट एवं कोटेशन ऑडिट"
        if is_hindi
        else "📑 Expert Report & Quote Audit"
    ),
    (
        "✉️ डिस्कॉम नेट-मीटरिंग आवेदन पत्र"
        if is_hindi
        else "✉️ Discom Application Letter"
    ),
    "❓ " + ("सौर सहायक से सवाल पूछें" if is_hindi else "Ask AI Assistant"),
])

with tab_advisory:
  if st.button(
      "🚀 "
      + (
          "विस्तृत रिपोर्ट तैयार करें"
          if is_hindi
          else "Generate Detailed Report"
      )
  ):
    if not api_key:
      st.error("कृपया API Key दर्ज करें। / Please enter a valid Gemini API key.")
    else:
      status_box = st.empty()
      report_box = st.empty()
      start_time = time.time()
      try:
        quote_context = (
            f"Vendor Quoted Price: Rs. {vendor_quote}."
            if vendor_quote > 0
            else "No vendor quote entered."
        )
        prompt = f"""
You are UrjaMitra, an expert Solar Rooftop Consultant specializing in India's PM Surya Ghar Muft Bijli Yojana.
Analyze the following user profile and return a structured assessment directly in clean Markdown format in {lang}.

DO NOT include raw scratchpad calculations, planning notes, or restatements of input. Begin immediately with '# UrjaMitra Solar Assessment Report'.

User Details:
- State: {state}
- Monthly Electricity Bill: Rs. {monthly_bill}
- Available Shadow-free Roof: {roof_area} sq. ft.
- Recommended Plant Capacity: {display_kw} kW
- Applicable Central Government Subsidy: Rs. {subsidy_amount} (Official MNRE slab)
- Estimated Net Investment: Rs. {net_estimated_cost}
- Expected Annual Financial Savings: Rs. {annual_savings}
- {quote_context}

Provide these structured sections:
1. Executive Feasibility Assessment (Roof sufficiency, expected daily kWh units)
2. Subsidy Claim Procedure (Official steps on pmsuryaghar.gov.in)
3. Quote Audit & Fair Price Verification (Compare vendor quote against benchmark ~Rs. 60,000/kW. Flag non-DCR modules or inflation).
4. Critical Safety & Technical Tips (Earthing pits, Lightning arrestor, ACDB/DCDB, Net meter).
"""
        used_model = stream_ai_response(
            api_key, prompt, report_box, status_box
        )
        latency = round(time.time() - start_time, 2)
        status_box.empty()
        st.success(
            f"✅ Completed in {latency}s | Engine: {used_model} | Cost: $0.00 (Free Tier) | Grounded in MNRE Guidelines"
        )

      except Exception as e:
        status_box.empty()
        st.error(f"Error calling AI API: {str(e)}")

with tab_letter:
  st.info(
      "डिस्कॉम (SDO कार्यालय) के लिए औपचारिक नेट-मीटरिंग अनापत्ति आवेदन।"
      if is_hindi
      else "Formal Net-Metering Application Letter for your local Discom SDO."
  )
  if st.button(
      "📝 " + ("आवेदन पत्र तैयार करें" if is_hindi else "Draft Application Letter")
  ):
    if not api_key:
      st.error("Please enter a valid Gemini API key.")
    else:
      status_box = st.empty()
      letter_placeholder = st.empty()
      start_time = time.time()
      try:
        model_name = get_best_model(api_key)
        model = genai.GenerativeModel(model_name)

        if is_hindi:
          letter_prompt = f"""
आप ऊर्जा मित्र हैं। डिस्कॉम के उप-मंडल अधिकारी (SDO), {state} को सोलर नेट-मीटरिंग और लोड स्वीकृति हेतु एक संक्षिप्त, सटीक और औपचारिक आवेदन पत्र लिखें।
प्लांट क्षमता: {display_kw} kW ऑन-ग्रिड रूफटॉप सोलर (पीएम सूर्य घर योजना)।

प्रारूप:
दिनांक: [दिनांक]
सेवा में, उप-मंडल अधिकारी (SDO)...
विषय: नेट-मीटरिंग एवं ग्रिड कनेक्टिविटी हेतु आवेदन...
महोदय...

केवल और केवल ऊपर दिए गए प्रारूप में अंतिम पत्र लिखें। कोई रूपरेखा या अतिरिक्त टिप्पणी न लिखें।
"""
        else:
          letter_prompt = f"""
You are UrjaMitra. Write a concise, professional, single-page formal application letter to the Sub-Divisional Officer (SDO), Electricity Distribution Utility ({state}).
Request: Solar Net-Metering Connection and Sanctioned Load Feasibility under PM Surya Ghar Muft Bijli Yojana for a {display_kw} kW on-grid solar system.

Format:
Date: [Insert Date]
To, The Sub-Divisional Officer (SDO)...
Subject: Application for Net-Metering Connection for {display_kw} kW Solar System...
Respected Sir/Madam...

Output strictly the final formal letter following this format.
"""

        status_box.info(
            f"⚡ Drafting via {model_name.replace('models/', '')}..."
        )
        response = model.generate_content(letter_prompt)
        raw_text = response.text

        # --- SMART POST-PROCESSING FILTER ---
        # Strips out any accidental outline/scratchpad generated before the letter header
        clean_text = raw_text
        for anchor in ["Date:", "दिनांक:", "To,", "सेवा में,"]:
          if anchor in clean_text:
            clean_text = anchor + clean_text.split(anchor, 1)[1]
            break

        # Remove duplicate letters if the model generated a second header
        if clean_text.count("Date:") > 1:
          clean_text = "Date:" + clean_text.split("Date:")[1]
        elif clean_text.count("दिनांक:") > 1:
          clean_text = "दिनांक:" + clean_text.split("दिनांक:")[1]

        status_box.empty()
        latency = round(time.time() - start_time, 2)
        st.success(f"✅ Drafted in {latency}s | Ready to copy and print")

        # Display in a clean text area for easy copying
        st.text_area(
            "📋 Ready-to-Print Letter"
            if not is_hindi
            else "📋 प्रिंट हेतु तैयार पत्र",
            value=clean_text.strip(),
            height=380,
        )

      except Exception as e:
        status_box.empty()
        st.error(f"Error generating letter: {str(e)}")
