ONCOLENS V2 - DO THIS

WINDOWS:
1. Open oncolens_v2\backend
2. Open CMD there
3. Run:
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python -m uvicorn server:app --host 0.0.0.0 --port 8000
4. Open http://127.0.0.1:8000/health
5. In a second CMD run: ngrok http 8000
6. Send the HTTPS Ngrok URL to the Mac.

MAC:
1. Open oncolens_v2/frontend/index.html in Chrome.
2. Paste the Ngrok URL in the top bar.
3. Click Test.
4. Open New Analysis.
5. Upload H&E image.
6. Click Run AI Analysis.
7. Show Reports, AI Assistant, Find Specialist, Analytics, Hospital Integration.

IMPORTANT:
AI Assistant, Specialists, Analytics, Cloud, Hospital Integration are demo modules.
The real workflow is upload -> FastAPI -> model/fallback -> heatmap -> biomarkers -> report.
