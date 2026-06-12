# Configuration & Environment Setup Guide

Complete guide to configuring all components.

---

## Backend Configuration

### Environment Variables (.env)

Create `poc/backend/.env`:

```env
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# REQUIRED: API Keys
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Your Anthropic/Claude API key from https://console.anthropic.com
OPENAI_API_KEY=sk-ant-...

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Claude model to use
# Options: gpt-4o (recommended), gpt-4-turbo, gpt-4, gpt-3.5-turbo
OPENAI_MODEL=gpt-4o

# Maximum steps to include in AI analysis
# Lower = faster, less comprehensive
# Higher = slower, more thorough
AI_MAX_STEPS=10

# Character limit per field value sent to AI
# Prevents sending huge values that waste tokens
AI_FIELD_CHAR_LIMIT=200

# Maximum network calls included per step
# Prevents overwhelming AI with network noise
AI_MAX_NETWORK_CALLS_PER_STEP=3

# Timeout for failure reasoning AI call (seconds)
AI_REASONING_TIMEOUT_SECONDS=20

# Number of retries for failed AI API calls
AI_REASONING_MAX_RETRIES=0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Playwright Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Timeout for each Playwright action (milliseconds)
# If element not found after this time, action fails
PLAYWRIGHT_ACTION_TIMEOUT_MS=5000

# Time to wait after click before checking result (ms)
# Allows page to process the click
PLAYWRIGHT_POST_CLICK_SETTLE_MS=300

# Timeout for navigation after click (milliseconds)
# Waits for page to load after click that triggers navigation
PLAYWRIGHT_POST_CLICK_NAVIGATION_TIMEOUT_MS=5000

# CSS selectors for overlay detection (comma-separated)
# Used to auto-dismiss cookie/consent popups
PLAYWRIGHT_OVERLAY_HINT_SELECTORS=[id*='cookie'], [class*='cookie'], [id*='consent'], [class*='consent']

# CSS selectors for overlay dismiss buttons (comma-separated)
# Clicks these to close detected overlays
PLAYWRIGHT_DISMISS_SELECTORS=button:has-text('Accept'), button:has-text('Accept all'), button:has-text('Dismiss')

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Database Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Database URL (SQLite by default)
# For SQLite: sqlite:///./test.db
# For PostgreSQL: postgresql://user:pass@localhost/dbname
# For MySQL: mysql+pymysql://user:pass@localhost/dbname
DATABASE_URL=sqlite:///./test.db

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Server Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Server host to bind to
# 0.0.0.0 = accept from any network interface
# 127.0.0.1 = local only
SERVER_HOST=0.0.0.0

# Server port
SERVER_PORT=8000

# Log level: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Feature Flags (Optional)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Enable/disable features for testing
FEATURE_OVERLAY_DISMISSAL=true
FEATURE_SCREENSHOT_CAPTURE=true
FEATURE_NETWORK_LOGGING=true
FEATURE_AI_ANALYSIS=true

# Maximum concurrent test executions
MAX_CONCURRENT_TESTS=3

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Development Mode
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Enable debug mode: verbose logging, don't clear temp files
DEBUG=false

# Enable auto-reload on file changes (development only)
RELOAD=true
```

### Database Setup

#### SQLite (Default - Development)

**No setup required.** Database created automatically on first run.

```bash
# Verify database exists
ls -la poc/backend/test.db

# Backup database
cp poc/backend/test.db poc/backend/test.db.backup

# Inspect database
sqlite3 poc/backend/test.db ".schema"
sqlite3 poc/backend/test.db "SELECT COUNT(*) FROM sessions;"
```

#### PostgreSQL (Production)

Install PostgreSQL and create database:

```bash
# macOS (with Homebrew)
brew install postgresql@15
brew services start postgresql@15
createdb agentic_testing

# Linux
sudo apt-get install postgresql postgresql-contrib
sudo -u postgres createdb agentic_testing

# Windows: Download from https://www.postgresql.org/download/windows/
```

Update `.env`:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/agentic_testing
```

Install Python PostgreSQL driver:
```bash
pip install psycopg2-binary
```

#### MySQL (Alternative)

```bash
# Create database
mysql -u root -p -e "CREATE DATABASE agentic_testing;"

# Update .env
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/agentic_testing

# Install driver
pip install pymysql
```

### API Key Configuration

#### Anthropic/Claude API Key

1. Visit https://console.anthropic.com/account/keys
2. Click "Create Key"
3. Copy key to `.env`:
   ```env
   OPENAI_API_KEY=sk-ant-...
   ```
4. Test connection:
   ```bash
   python -c "from openai import OpenAI; OpenAI().models.list()"
   ```

#### Rate Limiting (Future)

When you add rate limiting:

```env
API_RATE_LIMIT=100              # Requests per minute
API_RATE_LIMIT_WINDOW=60        # Window in seconds
ANALYSIS_RATE_LIMIT=10          # AI analysis per hour
```

---

## Frontend Configuration

### Environment Variables

Create `poc/frontend/.env` (optional):

```env
# Backend API URL
VITE_API_URL=http://localhost:8000

# Feature flags
VITE_ENABLE_ANALYTICS=false
VITE_ENABLE_CRASH_REPORTING=false

# UI Configuration
VITE_RESULTS_PER_PAGE=20
VITE_AUTO_REFRESH_INTERVAL=5000  # ms
```

### Vite Configuration

`poc/frontend/vite.config.js`:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false,  // Set true for debugging production builds
  }
})
```

### Tailwind CSS Configuration

`poc/frontend/tailwind.config.js`:

```javascript
export default {
  theme: {
    extend: {
      colors: {
        primary: '#3B82F6',
        success: '#10B981',
        danger: '#EF4444',
        warning: '#F59E0B',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      }
    }
  }
}
```

---

## Chrome Extension Configuration

### Manifest Configuration

`poc/extension/manifest.json`:

```json
{
  "manifest_version": 3,
  "name": "AI Testing Agent - Recorder",
  "version": "1.0.0",
  "description": "Records web sessions for AI-powered test generation",
  
  "permissions": [
    "activeTab",
    "tabs",
    "storage",
    "scripting"
  ],
  
  "host_permissions": [
    "<all_urls>"
  ],
  
  "background": {
    "service_worker": "background.js"
  },
  
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": ["content.js"],
      "run_at": "document_idle",
      "all_frames": false
    }
  ],
  
  "action": {
    "default_popup": "popup.html",
    "default_title": "AI Testing Agent"
  },
  
  "web_accessible_resources": [
    {
      "resources": ["content.js"],
      "matches": ["<all_urls>"]
    }
  ]
}
```

### Backend URL Configuration

In `poc/extension/background.js`:

```javascript
// Configure backend URL
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 
                    'http://localhost:8000';

const API_ENDPOINT = `${BACKEND_URL}/api/session/events`;
```

For production, pass via environment:
```bash
REACT_APP_BACKEND_URL=https://api.production.com npm run build
```

---

## Deployment Configurations

### Local Development

```bash
# Terminal 1 — Backend
cd poc/backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd poc/frontend
npm run dev

# Terminal 3 — Extension
# Just load in chrome://extensions
```

### Docker Development

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./poc/backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      DATABASE_URL: postgresql://postgres:password@db:5432/agentic_testing
    depends_on:
      - db
    volumes:
      - ./poc/backend:/app

  frontend:
    build:
      context: ./poc/frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    depends_on:
      - backend
    environment:
      VITE_API_URL: http://backend:8000
    volumes:
      - ./poc/frontend:/app

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: agentic_testing
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Run:
```bash
docker-compose up
```

### Docker Backend Only

Create `poc/backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    playwright-api \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install

# Copy application
COPY . .

# Run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t ai-testing-backend poc/backend
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  ai-testing-backend
```

### Kubernetes Deployment (Advanced)

Create `k8s/backend-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-testing-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ai-testing-backend
  template:
    metadata:
      labels:
        app: ai-testing-backend
    spec:
      containers:
      - name: backend
        image: ai-testing-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: openai-key
        - name: DATABASE_URL
          value: postgresql://db-service:5432/agentic_testing
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

Deploy:
```bash
kubectl apply -f k8s/backend-deployment.yaml
kubectl expose deployment ai-testing-backend --type=LoadBalancer --port=8000
```

---

## Performance Tuning

### Backend Optimization

```python
# In main.py, for production:

app.add_middleware(
    GZIPMiddleware,
    minimum_size=1000
)

# Connection pooling
app.config["SQLALCHEMY_POOL_SIZE"] = 20
app.config["SQLALCHEMY_POOL_RECYCLE"] = 3600

# Caching
from cachetools import TTLCache
session_cache = TTLCache(maxsize=100, ttl=3600)
```

### Playwright Optimization

```env
# Run tests in parallel
MAX_CONCURRENT_TESTS=5

# Use lightweight browser (instead of full Chrome)
PLAYWRIGHT_BROWSER=chromium

# Shorter action timeouts
PLAYWRIGHT_ACTION_TIMEOUT_MS=3000

# Disable video recording
PLAYWRIGHT_VIDEO=false

# Limit screenshot resolution
PLAYWRIGHT_SCREENSHOT_MAX_WIDTH=1280
```

### Database Optimization

```bash
# Add indexes for frequent queries
sqlite3 test.db "CREATE INDEX idx_session_created ON sessions(created_at DESC);"
sqlite3 test.db "CREATE INDEX idx_event_session ON events(session_id, timestamp);"

# Vacuum database to reclaim space
sqlite3 test.db "VACUUM;"
```

---

## Monitoring & Logging

### Backend Logging

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Use in code
logger.info(f"Processing session {session_id}")
logger.error(f"Failed with error: {error}")
logger.debug("Detailed debug info")
```

### Frontend Logging

```javascript
// Environment-based logging
const isDev = process.env.NODE_ENV === 'development';

const log = (level, message, data) => {
  if (isDev) {
    console.log(`[${level}] ${message}`, data);
  }
  // Send to logging service in production
};

log('info', 'Session loaded', { sessionId: '123' });
log('error', 'API error', { status: 500 });
```

### Error Tracking (Optional)

Add Sentry for error monitoring:

```python
# Backend
import sentry_sdk

sentry_sdk.init(dsn="https://...@sentry.io/...", traces_sample_rate=1.0)

# Frontend
import * as Sentry from "@sentry/react";

Sentry.init({ dsn: "https://...@sentry.io/..." });
```

---

## Security Configuration

### API Security

```python
# In main.py - add rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/session/events")
@limiter.limit("100/minute")
def receive_events(...):
    ...
```

### CORS Security

```python
# Production CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific domain only
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    max_age=3600
)
```

### API Authentication (Future)

```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

@app.post("/api/session/events")
def receive_events(
    batch: EventBatch,
    api_key: str = Security(verify_api_key),
    db: DBSession = Depends(get_db)
):
    ...
```

---

## Troubleshooting Configuration Issues

### "Cannot connect to backend"

```bash
# Check backend is running
ps aux | grep uvicorn

# Check port is open
lsof -i :8000

# Check CORS is configured
curl -H "Origin: http://localhost:5173" http://localhost:8000/api/health
```

### "API Key invalid"

```bash
# Test API key directly
python -c "
from openai import OpenAI
import os
os.environ['OPENAI_API_KEY'] = 'sk-...'
client = OpenAI()
print('OK')
"
```

### "Database connection failed"

```bash
# Check database URL
echo $DATABASE_URL

# Test connection
python -c "
from sqlalchemy import create_engine
engine = create_engine('sqlite:///./test.db')
print(engine.execute('SELECT 1'))
"
```

---

## Configuration Checklists

### Before First Run

- [ ] `.env` file created with valid API key
- [ ] Python virtual environment activated
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Playwright browsers installed: `playwright install`
- [ ] Chrome extension loaded in chrome://extensions
- [ ] Frontend dependencies installed: `npm install`
- [ ] All 3 services running (backend, frontend, extension)

### Before Production

- [ ] Database backed up
- [ ] Environment variables secured (not in git)
- [ ] CORS configured for specific domain
- [ ] API keys rotated
- [ ] Logging configured
- [ ] Error tracking enabled
- [ ] Rate limiting enabled
- [ ] Database indexes created
- [ ] Load testing completed
- [ ] Security audit passed

---

**Need help?** Check [Troubleshooting Guide](./DOCUMENTATION.md#troubleshooting) or run with `DEBUG=true` for verbose logs.
