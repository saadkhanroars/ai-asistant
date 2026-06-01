# Desktop AI Assistant - Modern UI Edition

## Project Structure

```
desktop-ai-assistant/
├── backend_api.py              # FastAPI server (REST endpoints)
├── main.py                     # Original CLI entry (kept for compatibility)
├── requirements.txt            # Python dependencies
├── .env.example               # Environment template
└── [existing modules]         # All original Python modules unchanged

frontend/
├── public/
│   ├── electron.js            # Electron main process
│   ├── preload.js             # Electron preload (IPC bridge)
│   ├── index.html             # HTML entry
│   └── icon.png               # App icon
├── src/
│   ├── App.jsx                # Main React app
│   ├── index.jsx              # React entry point
│   ├── index.css              # Global styles
│   ├── components/
│   │   ├── ChatInterface.jsx  # Chat UI
│   │   ├── SearchInterface.jsx# Search UI
│   │   ├── MessageBubble.jsx  # Message component
│   │   ├── Sidebar.jsx        # Navigation sidebar
│   │   └── TopBar.jsx         # Window controls
│   ├── store/
│   │   └── appStore.js        # Zustand state management
│   └── hooks/
│       └── useApi.js          # API communication
├── tailwind.config.js         # Tailwind CSS config
├── postcss.config.js          # PostCSS config
└── package.json               # Dependencies & scripts
```

## Architecture

### Backend (Python)
```
CLI (main.py) ←→ REST API (backend_api.py:5000) ←→ Electron/React Frontend (3000)
                        ↓
                  Existing modules:
                  - ai.py, router.py, search_engine.py
                  - indexer.py, database.py, watcher.py
                  - memory.py (chat history)
```

**No changes to existing Python logic** — only wrapped in REST endpoints.

### Frontend (React + Electron)
```
Electron Main Process (electron.js)
         ↓
React App (App.jsx)
         ↓
Tabs: Chat | Search | Settings
         ↓
UseApi Hook → HTTP Calls → Backend (FastAPI)
```

## Installation & Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- npm or yarn

### Step 1: Set up Python Backend

```bash
cd desktop-ai-assistant

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY (optional for AI features)
```

### Step 2: Start Backend API

```bash
python backend_api.py
```

Expected output:
```
🚀 Starting Desktop AI Assistant Backend API...
📍 Server: http://localhost:5000
📚 Docs: http://localhost:5000/docs
```

✅ **Backend running on port 5000**

### Step 3: Set up React/Electron Frontend

In a **new terminal**, from the project root:

```bash
cd frontend

# Install dependencies
npm install

# Start development (React + Electron)
npm run dev
```

This will:
1. Start React dev server (port 3000)
2. Launch Electron app pointing to React
3. Enable hot reload for development

✅ **App should open automatically**

## Development Workflow

### Terminal 1: Python Backend
```bash
cd desktop-ai-assistant
python backend_api.py
```

### Terminal 2: React + Electron Frontend
```bash
cd frontend
npm run dev
```

### Making Changes

**Backend changes** (Python):
- Modify any `.py` file
- Server auto-reloads (FastAPI with uvicorn)
- No need to restart React

**Frontend changes** (React/Electron):
- Edit `.jsx` or `.js` files
- Hot reload automatically (React dev server)
- No need to restart backend

## API Endpoints

All endpoints are at `http://localhost:5000/api`

### Chat
- `POST /api/chat` — Send message, get response
- `GET /api/chat/history` — Get conversation history
- `POST /api/chat/clear` — Clear chat history

### Search
- `POST /api/search` — Search indexed files/apps

### Actions
- `POST /api/action` — Execute command (open app, etc.)

### Index Management
- `GET /api/index/stats` — Get index statistics
- `POST /api/index/rebuild` — Rebuild index
- `GET /api/index/folders` — List indexed folders

### Settings
- `GET /api/settings` — Get app settings
- `POST /api/settings` — Update settings

### Health
- `GET /health` — Check backend status
- `GET /api/version` — Get API version

**Interactive API docs**: Open http://localhost:5000/docs in browser

## Building for Distribution

### Windows Installer

```bash
cd frontend
npm run build-electron
```

This creates:
- `dist/Desktop AI Assistant Setup 1.0.0.exe` — Installer
- `dist/Desktop AI Assistant 1.0.0.exe` — Portable version

### macOS

```bash
npm run build-electron
```

Creates `.dmg` file.

## Troubleshooting

### "Cannot connect to backend"
- Ensure `python backend_api.py` is running on port 5000
- Check firewall settings
- Verify no other app is using port 5000

### React shows blank screen
- Check browser console (F12) for errors
- Verify backend is running and healthy: `http://localhost:5000/health`
- Check network tab for failed API calls

### Chat/Search not working
- Backend connection issue (see above)
- Check backend logs for errors
- Verify API format matches (POST body, headers)

### Electron app won't start
- Kill any existing Electron processes
- Delete `node_modules`, run `npm install` again
- Check Node.js version: `node --version` (should be 18+)

## Feature Overview

### ✅ Implemented
- **Chat Interface**: Talk to AI or execute commands
- **Search**: Find files, apps, folders with beautiful results
- **Modern UI**: Dark theme with gradients, animations, smooth transitions
- **Window Controls**: Minimize, maximize, close buttons
- **Responsive Design**: Works on different window sizes
- **Error Handling**: Graceful error messages with retry options
- **Connection Status**: Shows if backend is connected
- **Markdown Support**: AI responses with code syntax highlighting

### 🔄 Backend Features (Unchanged)
- Indexed file search (SQLite)
- Background file watcher
- AI integration (OpenAI)
- Action routing (open apps, settings, web search)
- Session memory (conversation history)

### 🚀 Future Enhancements
- System tray integration
- Keyboard shortcuts (Cmd+K for search)
- Voice input/output
- Custom themes
- Plugin system
- Multi-session support
- Cloud sync

## Manual Steps You May Need

### 1. Environment Setup
```bash
# In desktop-ai-assistant/
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Initial Index Build
First run will automatically build the search index. This may take 10-30 seconds depending on your disk size.

### 3. Windows Defender SmartScreen
When installing the `.exe`, Windows may warn you. Click "More info" → "Run anyway" (this is normal for new apps).

### 4. Port Conflicts
If port 5000 or 3000 is in use:

```bash
# Find process using port 5000 (Windows)
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Or change ports in code:
# backend_api.py: uvicorn.run(..., port=5001)
# frontend/.env.local: REACT_APP_BACKEND_URL=http://localhost:5001
```

## Production Deployment

### For Desktop Installation
1. Build frontend: `cd frontend && npm run build-electron`
2. Distribute `.exe` installer
3. Users run installer, app starts automatically
4. Backend runs in background (packaged with Electron app)

### For Server/Web Version (Future)
1. Deploy backend to cloud (AWS, Azure, etc.)
2. Host React build on static hosting
3. Update API URLs in frontend

## Performance Optimization

- **Index Caching**: Search results cached in memory
- **Incremental Updates**: Only changed files re-indexed
- **Code Splitting**: React components lazy-loaded
- **Asset Compression**: Production builds minified
- **API Debouncing**: Search debounced (500ms)

## Testing

### Manual Testing
1. Start backend and frontend
2. Try chat: "open chrome"
3. Try search: "downloads"
4. Try command: "rebuild index"

### Backend API Testing
```bash
# Test health
curl http://localhost:5000/health

# Test chat
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'

# Test search
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "downloads"}'
```

## Known Limitations

1. **Windows Only (for now)**: Primary development for Windows. macOS/Linux support coming.
2. **Single Instance**: Only one instance runs at a time.
3. **Settings**: Limited settings panel (can be expanded).
4. **Voice**: No voice input yet (future feature).

## Contributing

- Backend changes: Edit `.py` files in `desktop-ai-assistant/`
- Frontend changes: Edit `.jsx` files in `frontend/src/`
- Follow existing code style
- Test both CLI and UI before committing

## License

MIT License (see LICENSE file)

## Support

For issues or feature requests, open a GitHub issue.

---

**Happy coding! 🚀**
