# Facebook Marketplace Automation

A powerful automation tool for Facebook Marketplace that helps find listings, send offers, and manage negotiations using AI.

## ⚠️ Important OS Compatibility Note

**This application has been primarily tested on Linux.**

### 🍎 macOS Users
If you are running this on macOS, you **MUST** update the Chrome executable path in the Python scripts. By default, the scripts look for Chromium at `/usr/bin/chromium`.

You need to edit the `executable_path` in the following files:
- `get_listing_urls.py`
- `offer_agent.py`
- `conversation_agent.py`
- `get_marketplace_urls.py`

**Typical macOS Chrome Path:**
```python
executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

### 🐧 Linux Users
The default configuration assumes `chromium` is installed at `/usr/bin/chromium`. If you use Google Chrome or a different path, please update the files listed above.

## 🔑 License and Configuration

To run the program, you will need a license key. For testing purposes, you can use the default test key:

**Default License Key:** `TEST-1234-5678-9ABC`

### Configuration Storage
All configuration files, including your Gemini API key and License key, are stored locally in your home directory:

- **Directory:** `~/.marketplace-bot/`
- **Config File:** `~/.marketplace-bot/config.json` (Stores Gemini API Key and settings)
- **License File:** `~/.marketplace-bot/license.json` (Stores License Key)

## 🚀 Quick Start Guide

### Prerequisites
1. **Python 3.11+** installed on your system.
2. **Node.js** (v16 or higher) and `npm` for the frontend.
3. **Chrome** or **Chromium** browser installed.
4. **uv** package manager (recommended for fast Python package management).

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Facebook_Automation
   ```

2. **Set up a Python Virtual Environment:**
   It is highly recommended to use a virtual environment to avoid conflicts.
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   # or
   # .\venv\Scripts\activate  # On Windows

3. **Install Dependencies:**
   First, install `uv` if you haven't already:
   ```bash
   pip install uv
   ```
   
   Then install the project requirements:
   ```bash
   uv pip install -r requirements.txt
   # OR using standard pip
   pip install -r requirements.txt
   ```

4. **Install GUI/Backend Dependencies:**
   The `run_gui.py` script will attempt to install these, but you can pre-install them:
   ```bash
   pip install fastapi uvicorn python-multipart google-generativeai
   ```

### Running the Application

The easiest way to start the application is using the provided launcher script. This will automatically build the React frontend and start the FastAPI backend.

```bash
python run_gui.py
```

Once started:
1. The backend will run at `http://localhost:8000`.
2. The browser should open automatically to the dashboard.
3. Go to the **Configuration** tab to set your **Gemini API Key** and search preferences.

## 🔧 Troubleshooting

- **Browser not opening/crashing:** Double-check the `executable_path` in the python scripts matches your actual Chrome installation path.
- **Dependencies:** If `uv` fails, the script attempts to fall back to standard `pip`. Ensure your virtual environment is active.
- **Frontend Build Fails:** Ensure you have `node` and `npm` installed and available in your system PATH.

## 📁 Project Structure

- `gui/`: Contains the React frontend and FastAPI backend.
- `utils/`: Helper scripts for data management and processing.
- `*.py`: Core automation agents (Listing search, Offer sending, Conversations).
