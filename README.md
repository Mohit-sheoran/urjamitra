# urjamitra
# ☀️ UrjaMitra (ऊर्जा मित्र)
### AI-Powered Solar Sizing, PM Surya Ghar Subsidy & Fair-Price Audit

UrjaMitra is an LLM application designed to eliminate friction in residential and agricultural rooftop solar adoption under India's **PM Surya Ghar: Muft Bijli Yojana**.

---

## 🚀 Live Demo
- **Web App:** [UrjaMitra on Streamlit Cloud](https://urjamitra-ubz8fuwuscyloy2gbn78mj.streamlit.app)

---

## 🎯 Problem Statement
Navigating rooftop solar economics in India is confusing for average citizens:
- Unclear calculation of central subsidies and net out-of-pocket costs.
- Risk of overcharging or non-DCR (Domestic Content Requirement) module fraud by unverified local vendors.
- Tedious bureaucratic procedures for Discom net-metering NOC applications.

---

## 💡 Key Features
- **Deterministic Solar Engine:** Calculates plant capacity (kWp), required roof area, and exact MNRE subsidy slabs using standard benchmarks without AI hallucinations.
- **Grounded AI Advisory:** Uses Gemini 1.5 Flash grounded in official MNRE PM Surya Ghar operational guidelines to audit vendor quotes and detail scheme steps.
- **Automated Discom Net-Metering Drafter:** Generates print-ready formal letters for local Sub-Divisional Officers (SDO).
- **Multilingual Support:** Fully bilingual interface and reports supporting English and Hindi (हिंदी).
- **Cost & Latency Tracking:** Real-time metrics tracking inference latency (<1s) and token cost ($0.00 on free tier).

---

## 🛠️ Tech Stack
- **Frontend / UI:** Streamlit
- **LLM / Reasoning Engine:** Google Gemini 1.5 Flash (via `google-generativeai`)
- **Knowledge Base:** MNRE PM Surya Ghar Operational Guidelines (Updated 2024 Slabs)

---

## ⚙️ Local Setup
```bash
git clone [https://github.com/Mohit-sheoran/urjamitra.git](https://github.com/Mohit-sheoran/urjamitra.git)
cd urjamitra
pip install -r requirements.txt
streamlit run app.py
