# Quick Start Guide - Desktop AI Assistant Modern UI

## One-Time Setup (5 minutes)

### Option A: Automated Setup (Recommended)

```bash
# Clone/navigate to repo
cd ai-asistant

# Run setup script (coming soon)
# bash setup.sh
```

### Option B: Manual Setup

#### 1. Backend Setup

```bash
cd desktop-ai-assistant

# Install Python dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Open .env and add OPENAI_API_KEY (optional)
```

#### 2. Frontend Setup

```bash
cd ../frontend

# Install Node dependencies
npm install
```

## Daily Development

### Start Backend (Terminal 1)
```bash
cd desktop-ai-assistant
python backend_api.py
```

✅ Backend ready at: http://localhost:5000

### Start Frontend (Terminal 2)
```bash
cd frontend
npm run dev
```

✅ App launches automatically

## What's Working

✅ **Chat with AI** - Type messages or commands
✅ **Search files** - Indexed file/app search
✅ **Open apps** - "open chrome" or "open downloads"
✅ **Web search** - "search cats on google"
✅ **Settings routing** - "bluetooth settings"
✅ **Index management** - Rebuild/refresh commands
✅ **Modern UI** - Dark theme, smooth animations
✅ **Connection indicator** - Shows backend status
✅ **Markdown in AI responses** - Code syntax highlighting

## Common Commands

```
Chat:
  "open chrome"           → Launches Chrome
  "search cats on google" → Opens web search
  "what's the weather?"   → AI responds
  "help"                  → Shows command list

Search:
  Click search tab → Enter query → Click result to open

Index:
  "rebuild index"  → Full rebuild
  "refresh index"  → Incremental sync
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Blank screen | Check backend running on :5000 |
| "Cannot connect" | Restart both backend and frontend |
| Port 5000 in use | Change port in `backend_api.py` |
| No search results | Rebuild index: "rebuild index" |

## Architecture

```
Backend (Python) ←→ REST API ←→ Frontend (React/Electron)
  • Original code        (FastAPI)      • Modern UI
  • No changes made      (port 5000)    • Chat & Search
  • All features work    (port 3000)    • Animations
```

**Key Point**: All your original Python code works unchanged! We just added a REST API layer.

## Next Steps

1. ✅ Start backend & frontend (see above)
2. ✅ Test chat & search
3. ✅ Try commands like "open chrome"
4. ✅ Adjust settings as needed

## Building for Distribution

When ready to share:

```bash
cd frontend
npm run build-electron

# Creates Windows installer in dist/
```

---

**Questions?** Check MODERN_UI_IMPLEMENTATION.md for detailed docs.
