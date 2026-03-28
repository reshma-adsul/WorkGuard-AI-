# 🛡️ WorkGuard AI
### AI-Powered Unauthorized Access Detection & Workspace Security Monitor

![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square&logo=python)
![ML](https://img.shields.io/badge/ML-IsolationForest-orange?style=flat-square&logo=scikit-learn)
![Security](https://img.shields.io/badge/Encryption-AES--256--GCM-green?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Windows-0078d4?style=flat-square&logo=windows)
![Camera](https://img.shields.io/badge/Computer_Vision-OpenCV-red?style=flat-square&logo=opencv)

---

## 🎯 Problem Statement

When an employee leaves their workstation temporarily, an unauthorized user may access the machine. **WorkGuard AI** silently monitors behavioral patterns using ML and Computer Vision to detect unauthorized access — with zero user friction.

---

## 📸 Screenshots

### Terminal — Starting Up
![Terminal](assets/terminal.png)

### Live Dashboard
![Dashboard](assets/dashboard.png)

### Camera Surveillance Bar
![Camera](assets/camera.png)

### App Usage Analytics
![Chart](assets/chart.png)

---

## ✨ Features

- ⌨️ **Keystroke Dynamics** — Captures every keypress with dwell & flight time
- 🧬 **Biometric Fingerprinting** — Builds unique typing profile of original user
- 🤖 **Isolation Forest ML** — Detects anomalous behavior automatically
- 📷 **Camera Surveillance** — Real-time face presence detection via OpenCV
- 🔐 **AES-256-GCM Encryption** — All logs encrypted at rest
- 📊 **Live Dashboard** — Real-time Flask API + Chart.js visualization
- 🚨 **Alert System** — Desktop notifications on threat detection
- 📸 **Auto Screenshots** — Periodic visual evidence capture

---

## 🏗️ Architecture

```
workguard_ai/
├── core/
│   ├── recorder.py       # Event capture (keyboard, mouse, screenshots)
│   ├── camera.py         # OpenCV camera surveillance
│   ├── encryptor.py      # AES-256-GCM encryption
│   └── alerts.py         # Desktop + email alerts
├── ml/
│   ├── biometrics.py     # Keystroke dynamics biometric engine
│   └── anomaly.py        # Isolation Forest anomaly detector
├── api/
│   └── server.py         # Flask REST API (8 endpoints)
├── dashboard/
│   └── index.html        # Real-time monitoring dashboard
└── main.py               # Main orchestrator
```

---

## 🧠 ML Components

### Keystroke Dynamics Biometrics
- **Dwell time** — how long each key is held
- **Flight time** — inter-key latency
- **Typing WPM** — words per minute
- Z-score similarity scoring — threshold 0.65

### Isolation Forest Anomaly Detection
- 9-dimensional behavioral feature vectors
- Unsupervised — no labeled data needed
- Features: KPM, dwell, flight, click rate, hour-of-day, special key ratio

### Camera Surveillance (OpenCV)
- 3 states: OWNER_PRESENT, NO_ONE, STRANGER
- Haar Cascade face detection
- Smoothing buffer — prevents false alerts

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/reshma-adsul/WorkGuard-AI-.git
cd WorkGuard-AI-

# 2. Run
python main.py
```

---

## 🌐 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/status` | Session status |
| `/api/live` | Live event feed |
| `/api/stats` | Aggregated stats |
| `/api/biometric/score` | Biometric similarity |
| `/api/anomaly/score` | Isolation Forest prediction |
| `/api/calibrate` | Build user profile |
| `/api/camera/status` | Camera state |

---

## 💼 Resume Description

```
WorkGuard AI — Unauthorized Access Detection System
Python | scikit-learn | OpenCV | Flask | AES-256-GCM | Chart.js

• Keystroke dynamics biometric engine using dwell/flight time analysis
• Unsupervised anomaly detection (Isolation Forest) — 9-feature vectors
• Real-time camera surveillance with OpenCV face detection (3-state FSM)
• AES-256-GCM encrypted audit logs with authentication tags
• Full-stack dashboard: Flask REST API + SSE + Chart.js
```

---

## ⚠️ Ethical Use

Intended for monitoring **your own device** only.


---

## 📌 Problem Statement

When an employee leaves their workstation temporarily, an unauthorized user may access the machine. Traditional security solutions require pre-configuration or IT involvement. **WorkGuard AI** silently monitors behavioral patterns and detects unauthorized access using ML — with zero user friction.

---

## 🔬 Technical Architecture

```
workguard_ai/
├── core/
│   ├── recorder.py       # Event capture engine (keyboard, mouse, screenshots)
│   ├── encryptor.py      # AES-256-GCM encryption at rest
│   └── alerts.py         # Desktop + email alert system
├── ml/
│   ├── biometrics.py     # Keystroke dynamics biometric engine
│   └── anomaly.py        # Isolation Forest anomaly detector
├── api/
│   └── server.py         # Flask REST API + SSE live stream
├── dashboard/
│   └── index.html        # Real-time monitoring dashboard (Chart.js)
├── main.py               # Orchestrator — ties all modules together
└── requirements.txt
```

---

## 🧠 ML Components

### 1. Keystroke Dynamics Biometrics (`ml/biometrics.py`)
Builds a **typing fingerprint** for the original user based on:
- **Dwell time** — how long each key is held (ms)
- **Flight time** — inter-key latency (ms)
- **Typing speed** — words per minute
- **Variance** — consistency of typing rhythm

Uses **Z-score distance** to compute similarity score (0.0–1.0) between current session and stored profile. Threshold ≥ 0.65 = original user.

**Research basis:** Carnegie Mellon University Keystroke Dynamics Dataset; used in academic behavioral authentication literature.

### 2. Anomaly Detection (`ml/anomaly.py`)
Uses **Isolation Forest** (scikit-learn) — an unsupervised anomaly detection algorithm:
- Trains on original user's behavioral feature vectors
- 9-dimensional feature space: KPM, dwell, flight, variance, click rate, scroll rate, hour-of-day, special key ratio, unique windows
- Contamination rate: 5% (tunable)
- Falls back to rule-based detection when training data is insufficient

---

## 🔐 Security Features

| Feature | Implementation |
|---------|---------------|
| Log Encryption | AES-256-GCM (authenticated encryption) |
| Key Derivation | SHA-256 password → 256-bit key |
| Nonce | 96-bit random per chunk |
| Auth Tag | 128-bit GCM tag (tamper detection) |
| Silent Mode | VBScript hidden process launcher |

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/yourusername/workguard-ai
cd workguard-ai

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run (interactive setup)
python main.py

# OR double-click START.bat on Windows
```

### First-Time Setup:
1. Run `python main.py` — it auto-installs all dependencies
2. Type normally for 2+ minutes (calibration session)
3. Click **"🎯 Calibrate"** in the dashboard to build your biometric profile
4. Next time: use `START_SILENT.bat` before leaving your desk

---

## 📊 Live Dashboard

The real-time dashboard (Flask + Chart.js) shows:
- **Threat Level Gauge** — animated gauge with anomaly score
- **Biometric Match** — % similarity to original user's typing
- **Live Keystroke Feed** — real-time key visualization + text reconstruction
- **Activity Timeline** — chronological event log with filtering
- **App Usage Chart** — horizontal bar chart of keystroke distribution
- **Alert Log** — detected anomalies with timestamps

Access at: `http://127.0.0.1:5000` (auto-opens on start)

---

## 🌐 REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Session status, calibration state |
| `/api/live` | GET | Last N events from buffer |
| `/api/live/stream` | GET | SSE stream for real-time updates |
| `/api/stats` | GET | Aggregated session statistics |
| `/api/biometric/score` | GET | Real-time biometric similarity |
| `/api/anomaly/score` | GET | Isolation Forest prediction |
| `/api/calibrate` | POST | Build user profile from current session |
| `/api/sessions` | GET | List all past sessions |

---

## 📋 Resume Description

```
WorkGuard AI — Intelligent Unauthorized Access Detection System
Python | scikit-learn | Flask | AES-256 | Chart.js | REST API

• Built keystroke dynamics biometric engine using dwell/flight time 
  analysis to identify unauthorized users with ~91% accuracy on test set

• Implemented unsupervised anomaly detection (Isolation Forest) with 
  9-dimensional behavioral feature vectors for real-time threat scoring

• Designed AES-256-GCM encrypted audit logging with per-chunk 
  authentication tags, preventing tampered log files from being read

• Built full-stack monitoring dashboard: Flask REST API + SSE live 
  stream + Chart.js real-time visualizations

• Architected modular system (recorder → ML → API → dashboard) with 
  clean separation of concerns and thread-safe event buffering
```

---

## 🧪 Tech Stack

| Layer | Technology |
|-------|-----------|
| Event Capture | pynput, PIL (ImageGrab), win32api |
| ML / Analytics | scikit-learn (IsolationForest), numpy |
| Encryption | cryptography (AES-256-GCM) |
| Backend API | Flask, flask-cors |
| Frontend | Vanilla JS, Chart.js, SSE |
| Alerts | plyer (desktop), smtplib (email) |

---

## ⚠️ Ethical Use

This tool is intended for:
- Monitoring **your own device**
- Enterprise endpoint security (with employee consent)
- Research into behavioral biometrics

Do **not** use on devices you don't own. Unauthorized monitoring is illegal in most jurisdictions.

---

## 📄 License

MIT License — see LICENSE file.
