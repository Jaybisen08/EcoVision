🌿 EcoVision – AI Smart Waste Analyzer
![image alt](https://github.com/Jaybisen08/EcoVision/blob/main/ecovision.png?raw=true)

🌎 Overview

EcoVision is an AI-powered waste analysis system that helps identify waste from images, assess its environmental impact, and guide users on proper disposal.
It features a beautiful, animated UI, PDF reporting, and a full analytics dashboard.

🚀 Features
🤖 AI Waste Classification

Powered by Google Gemini 2.5 Flash

Detects: organic, plastic, paper, textile, e-waste, hazardous, mixed, etc.

Returns confidence score + expert notes

🌍 Environmental Impact Breakdown

Visualized using Matplotlib pie chart:

Greenhouse Emissions

Soil Contamination

Water Pollution

Energy Use

♻️ Smart Disposal Steps

Clear, actionable instructions (3–6 steps) for safe waste management.

📝 Auto-Generated PDF Report

Includes:

Uploaded waste image

Impact chart

Category + confidence

Notes & disposal guidelines

Eco Tip of the Day

Sanitized fonts for compatibility

📊 Analytics Dashboard

View all past analyses

Filter by waste category

Bar chart of category frequency

Local JSON storage: ecovision_stats.json

✨ Modern UI & Animations

Gradient animated background

Glass-morphism cards

Lottie animations for each section

📁 Project Structure
EcoVision/
│── app.py
│── ecovision_stats.json
│── requirements.txt
│── README.md
│── fonts/
│   └── (optional fonts for PDF)

🛠️ Installation
1. Clone the Repository
git clone https://github.com/jaybisen08/EcoVision.git
cd EcoVision

2. Install Dependencies
pip install -r requirements.txt

🔑 Gemini API Setup

Create .streamlit/secrets.toml:

GEMINI_API_KEY = "your_api_key_here"


Or add via Streamlit Cloud → Settings → Secrets.

▶️ Run the App
streamlit run app.py


App will start at:

http://localhost:8501

📦 Recommended requirements.txt
streamlit
pillow
matplotlib
pandas
fpdf2
google-generativeai
requests
streamlit-lottie

🌿 How EcoVision Works

User uploads a waste image

Image + prompt sent to Gemini Vision

Strict JSON returned

App generates:

Pie chart

Sanitized PDF report

Dashboard entry

Data stored locally in JSON

User views results instantly

🌱 Eco Tip of the Day

EcoVision rotates tips daily using date-based index mapping.

🤝 Contributing

All contributions are welcome!
Whether you want to:

Improve UI

Add new waste categories

Expand reporting

Optimize performance

Submit a PR anytime 🚀

📜 License

This project is released under the MIT License.

⭐ Support the Project

If you like EcoVision, give this repo a star ⭐ on GitHub — it helps more people discover it!
