# Installation & Setup Guide for Desktop AI Assistant Modern UI

## System Requirements

- **Windows 10+** (or macOS 10.13+, Linux)
- **Python 3.10+**
- **Node.js 18+** (for frontend)
- **npm 9+** (comes with Node.js)
- **4GB RAM** minimum
- **500MB free disk space**

## Installation Steps

### Step 1: Clone Repository

```bash
git clone https://github.com/saadkhanroars/ai-asistant.git
cd ai-asistant
```

### Step 2: Setup Backend (Python)

#### Windows
```powershell
cd desktop-ai-assistant

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment file
copy .env.example .env
```

#### macOS/Linux
```bash
cd desktop-ai-assistant

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup environment file
cp .env.example .env
```

#### Configure OpenAI API (Optional but Recommended)

1. Get API key: https://platform.openai.com/api-keys
2. Open `.env` file in text editor
3. Replace `your_api_key_here` with your actual key
4. Save file

```bash
# Example .env
OPENAI_API_KEY=sk-...
ASSISTANT_DEBUG=0
```

### Step 3: Setup Frontend (React/Electron)

```bash
# From project root, go to frontend
cd frontend

# Install dependencies
npm install

# This may take 2-3 minutes (wait for completion)
```

## Running the Application

### Development Mode (Recommended for Testing)

**Terminal 1 - Start Backend:**
```bash
cd desktop-ai-assistant
python backend_api.py
```

You should see:
```
✅ Backend initialized. Watcher mode: watchdog
🚀 Starting Desktop AI Assistant Backend API...
📍 Server: http://localhost:5000
📚 Docs: http://localhost:5000/docs
```

**Terminal 2 - Start Frontend:**
```bash
cd frontend
npm run dev
```

The app should launch automatically. If not, open browser to `http://localhost:3000`

### Production Mode (Built App)

```bash
cd frontend
npm run build-electron
```

This creates an installer in `dist/` folder. Run the `.exe` (Windows) or `.dmg` (macOS).

## First Run

1. **Index Building**: First launch will build the search index (~10-30 seconds)
2. **Chat**: Try saying "hello" or "open chrome"
3. **Search**: Click Search tab and search for files
4. **Settings**: Check index statistics and configure options

## Troubleshooting

### Backend Won't Start

**Error: "Port 5000 already in use"**
```bash
# Find what's using port 5000
netstat -ano | findstr :5000

# Kill the process (Windows)
taskkill /PID <PID> /F

# Or use different port
# Edit backend_api.py line: uvicorn.run(..., port=5001)
```

**Error: "ModuleNotFoundError"**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Frontend Won't Start

**Error: "npm: command not found"**
- Install Node.js from https://nodejs.org/
- Restart terminal after installation

**Error: "Port 3000 already in use"**
```bash
# Use different port
PORT=3001 npm start
```

### App Shows Blank Screen

1. Check browser console (F12)
2. Check backend health: `http://localhost:5000/health`
3. Restart both backend and frontend
4. Check firewall settings

### Chat/Search Not Working

1. **Verify backend running**: Open http://localhost:5000/docs
2. **Check API key**: If using AI, ensure OPENAI_API_KEY is set
3. **Rebuild index**: In Settings, click "Rebuild Index (Full)"
4. **Check logs**: Look for error messages in terminal

### Index Building Taking Too Long

- First run scans entire disk (normal)
- Subsequent runs are incremental (fast)
- Can take 5-10 minutes for large disks
- Don't close the window during indexing

## Uninstallation

### Development Version
```bash
# Just delete the folder
rm -rf ai-asistant
```

### Built Application (Windows)
1. Go to Control Panel → Programs → Programs and Features
2. Find "Desktop AI Assistant"
3. Click Uninstall

## Performance Optimization

### For Slow Machines

```bash
# Reduce search index
# Edit desktop-ai-assistant/search_config.py:
# MAX_INDEX_FILES = 10000  # Default: 50000

# Disable file watching
# Edit .env:
# ASSISTANT_DEBUG=0
```

### For Fast Machines

```bash
# Enable full disk indexing
# Edit search_config.py:
# MAX_INDEX_FILES = 100000
```

## Manual Configuration

### Add Custom Search Folders

1. Edit `desktop-ai-assistant/search_config.py`
2. Find `CUSTOM_SEARCH_ROOTS`
3. Add your folders:
```python
CUSTOM_SEARCH_ROOTS = [
    "C:\\MyFiles",
    "C:\\Projects",
]
```
4. Restart backend and rebuild index

### Change AI Model

```bash
# Edit .env
OPENAI_MODEL=gpt-4-turbo
# or
OPENAI_MODEL=gpt-3.5-turbo
```

### Enable Debug Mode

```bash
# Edit .env
ASSISTANT_DEBUG=1

# Now backend will print detailed logs
```

## Testing Installation

### Backend Test
```bash
# Test backend health
curl http://localhost:5000/health

# Should return:
# {"status":"healthy","ai_enabled":"yes","watcher":"watchdog"}
```

### Frontend Test
1. Open app
2. Type: "hello"
3. Should see response

### Search Test
1. Click Search tab
2. Type: "downloads"
3. Should see indexed files

## Getting Help

- **GitHub Issues**: https://github.com/saadkhanroars/ai-asistant/issues
- **Documentation**: See MODERN_UI_IMPLEMENTATION.md
- **Quick Start**: See QUICK_START.md

## Next Steps

1. ✅ Installation complete
2. Read QUICK_START.md for daily usage
3. Read MODERN_UI_IMPLEMENTATION.md for detailed features
4. Customize .env for your setup
5. Enjoy! 🚀

---

**Installation Support**: If you encounter issues, check the troubleshooting section above or open a GitHub issue.
