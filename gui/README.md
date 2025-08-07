# Marketplace Bot Desktop App

A React + Python desktop application for automating Facebook Marketplace interactions with AI-powered negotiation.

## Architecture

- **Backend**: FastAPI (Python) with license validation and automation control
- **Frontend**: React (TypeScript) with Material-UI for the user interface
- **Communication**: WebSocket for real-time updates during automation
- **Deployment**: Single executable with PyInstaller

## Features

### License Management
- License key validation and machine binding
- Test license key support for evaluation
- Secure local license caching

### Configuration Management
- Gemini API key configuration
- Customizable search products and keywords
- Flexible pricing strategies
- Browser and automation settings

### Automation Control
- Real-time progress monitoring
- WebSocket-based status updates
- Start/stop automation control
- Results tracking and statistics

### User Interface
- Dark theme Material-UI design
- Three-step setup flow: License → Configuration → Dashboard
- Responsive design for desktop use
- Real-time progress visualization

## Project Structure

```
marketplace-bot-app/
├── backend/
│   ├── main.py                 # FastAPI server
│   ├── models.py               # Pydantic models
│   ├── license_validator.py    # License validation logic
│   ├── config_manager.py       # Configuration management
│   └── automation_runner.py    # Automation script execution
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── LicenseForm.tsx
│   │   │   ├── ConfigurationForm.tsx
│   │   │   └── AutomationDashboard.tsx
│   │   ├── services/
│   │   │   ├── ApiService.ts
│   │   │   └── WebSocketService.ts
│   │   ├── App.tsx
│   │   └── index.tsx
│   ├── public/
│   └── package.json
└── README.md
```

## Setup Instructions

### Prerequisites

- Python 3.9+
- Node.js 16+
- Chrome browser (for automation)

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the FastAPI server:
   ```bash
   python main.py
   ```

The server will start on `http://localhost:8000` and automatically open the browser.

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm start
   ```

The React app will be available at `http://localhost:3000`, but the backend serves it at `http://localhost:8000`.

## Usage

### Step 1: License Validation
- Enter your license key or use the test key: `TEST-1234-5678-9ABC`
- The system validates the license and caches it locally

### Step 2: Configuration
- Enter your Gemini API key
- Configure search products (e.g., "iPhone 13 Pro Max")
- Set pricing strategies for unlocked/locked devices
- Adjust automation settings and limits

### Step 3: Automation Dashboard
- Monitor real-time progress during automation
- View statistics and results
- Control automation start/stop
- Track conversation status and deals

## Configuration Options

### API Configuration
- **Gemini API Key**: Required for AI-powered responses

### Search Configuration
- **Search Products**: Items to search for on marketplace
- **Keywords**: Additional search terms (optional)

### Pricing Strategy
- **Base Offer - Unlocked**: Default offer for unlocked devices
- **Base Offer - Locked**: Default offer for locked devices
- **Price Flexibility**: Negotiation range (±$20 default)

### Advanced Settings
- **Max Conversations**: Limit concurrent conversations
- **Max Offers per Run**: Limit offers sent per automation run
- **Strategy**: Primary/Aggressive/Conservative approaches
- **Browser Settings**: Headless mode and delay configuration

## API Endpoints

### License Management
- `POST /api/validate-license` - Validate license key
- `GET /api/license-status` - Get current license status

### Configuration
- `GET /api/configuration` - Get current configuration
- `POST /api/configuration` - Save configuration
- `POST /api/test-configuration` - Test configuration

### Automation Control
- `POST /api/automation/start` - Start automation
- `POST /api/automation/stop` - Stop automation
- `GET /api/automation/status` - Get automation status
- `GET /api/automation/results` - Get automation results

### WebSocket
- `WS /ws/{client_id}` - Real-time progress updates

## Security Features

- License validation with machine binding
- Secure API key storage
- Local configuration encryption
- Request validation and sanitization

## Development Notes

### Building for Production

1. Build the React frontend:
   ```bash
   cd frontend
   npm run build
   ```

2. Package with PyInstaller:
   ```bash
   cd backend
   pyinstaller --onefile --windowed main.py
   ```

### Testing

- Use the test license key: `TEST-1234-5678-9ABC`
- Backend includes configuration validation
- WebSocket connection health monitoring

## Troubleshooting

### Common Issues

1. **License Validation Failed**: Check internet connection and license key format
2. **WebSocket Connection Failed**: Ensure backend is running on port 8000
3. **Automation Errors**: Verify Gemini API key and Chrome browser availability
4. **Configuration Issues**: Use the test configuration button to validate settings

### Debug Mode

Set environment variable for detailed logging:
```bash
export MARKETPLACE_BOT_DEBUG=true
```

## License

This project requires a valid license key for operation. Contact support for licensing information.