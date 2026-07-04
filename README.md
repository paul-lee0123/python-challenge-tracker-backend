# Python Challenge Tracker - Backend

Backend API for executing Python code safely and providing feedback.

## Setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
python app.py
```

Server runs on `http://localhost:5000`

## Endpoints

- `POST /execute` - Execute Python code
- `POST /check-syntax` - Check code for errors
- `POST /test-challenge` - Run test cases

## Security

- Uses RestrictedPython for sandboxed execution
- No file system access
- No network access
- 10 second timeout maximum
