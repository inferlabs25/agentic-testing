# Quick Start Guide — AI Agentic Testing Tool

Get up and running in 15 minutes.

---

## 1️⃣ Prerequisites (2 min)

✅ Check you have:
- Python 3.11+ (`python --version`)
- Node.js 18+ (`node --version`)
- Chrome browser
- OpenAI/Claude API key
- VS Code or IDE

---

## 2️⃣ Backend Setup (4 min)

### Create Virtual Environment

**Windows:**
```bash
cd poc\backend
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
cd poc/backend
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
playwright install
```

### Create .env File

Create `poc/backend/.env`:
```env
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o
AI_MAX_STEPS=10
PLAYWRIGHT_ACTION_TIMEOUT_MS=5000
```

### Start Backend

```bash
uvicorn main:app --reload --port 8000
```

✅ **Success:** Browser shows `http://localhost:8000/docs` with API docs

---

## 3️⃣ Frontend Setup (3 min)

**New terminal:**

```bash
cd poc/frontend
npm install
npm run dev
```

✅ **Success:** Shows `➜ Local: http://localhost:5173/`

---

## 4️⃣ Chrome Extension (3 min)

1. Open Chrome → `chrome://extensions/`
2. Enable "Developer mode" (top right)
3. Click "Load unpacked"
4. Select `poc/extension/` folder
5. Extension appears in toolbar ✅

---

## 5️⃣ Record Your First Session (5 min)

1. Navigate to any website (e.g., https://example.com)
2. Click extension icon → "Start Recording"
3. Perform actions:
   - Click on elements
   - Fill out forms
   - Navigate pages
4. Click "Stop Recording"
5. Open http://localhost:5173

✅ **Success:** New session appears in dashboard

---

## 6️⃣ Generate & Run Tests (5 min)

1. Select session from list
2. Click "Analyze with AI"
3. Wait 30-60 seconds for test generation
4. Click "Approve All" tests
5. Click "Run All Tests"

✅ **Success:** See test results with pass/fail status

---

## Verify Everything Works

| Component | URL | Status |
|-----------|-----|--------|
| Backend API | http://localhost:8000/docs | ✅ Loads |
| Frontend Dashboard | http://localhost:5173 | ✅ Loads |
| Chrome Extension | Chrome toolbar | ✅ Icon visible |
| Database | `poc/backend/test.db` | ✅ File exists |

---

## Troubleshooting Quick Fixes

**Backend won't start:**
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9  # macOS/Linux
netstat -ano | findstr :8000   # Windows (find PID, then taskkill)
```

**Extension not capturing events:**
- Reload extension: chrome://extensions → Refresh button
- Check console: DevTools (F12) → Console tab

**Frontend can't reach backend:**
- Verify both running: Backend on 8000, Frontend on 5173
- Check .env has correct API key

**Tests timing out:**
- Increase in .env: `PLAYWRIGHT_ACTION_TIMEOUT_MS=10000`
- Restart backend

---

## Next Steps

- [Full Documentation](./DOCUMENTATION.md) — Complete reference
- [Development Guide](#) — For contributing code
- [API Reference](./DOCUMENTATION.md#api-reference) — Endpoint details

---

**Ready to go!** 🚀

Questions? Check the main documentation or check the console logs for error details.
