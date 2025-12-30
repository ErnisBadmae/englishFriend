# Quick Start - Transfer to New Computer

## 1. Clone Repository
```bash
git clone https://github.com/ErnisBadmae/englishFriend.git
cd englishFriend
git checkout main
```

## 2. Backend Setup (Python 3.12)
```bash
# Create venv
py -3.12 -m venv venv
venv/Scripts/activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env: добавьте GROQ_API_KEY, настройте VLLM_API_BASE если нужно
```

## 3. Frontend Setup
```bash
cd frontend
npm install
```

## 4. Database Setup
```bash
# Start PostgreSQL
docker-compose up -d postgres

# Migrations apply automatically via SQLAlchemy on startup
```

## 5. Verify Vosk Model
```bash
ls -la frontend/public/vosk-model-small-en-us-0.15.zip
# Should be ~46MB

# If missing, download:
cd frontend/public
curl -LO https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
```

## 6. Run Application

**Terminal 1 - Backend:**
```bash
venv/Scripts/python.exe main.py
# http://localhost:8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
# http://localhost:5173
```

## 7. Continue Work

**Prompt for Claude:**
> Read PROGRESS_VOSK_INTEGRATION.md for full context. Vosk returns empty recognition results. Check sample rate mismatch and microphone amplitude in browser console.

## Critical Files
- `PROGRESS_VOSK_INTEGRATION.md` - полный контекст
- `frontend/src/hooks/useVosk.ts` - Vosk logic
- `app/api/voice.py` - WebSocket backend

**Status**: 90% complete, debugging speech recognition
