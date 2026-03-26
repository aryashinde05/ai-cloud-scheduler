# ☁️ Cloud Intelligence & Migration Advisor

**A professional FinOps platform for cloud cost optimization, anomaly detection, and intelligent migration planning.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![React](https://img.shields.io/badge/Frontend-React%2018-61DAFB?logo=react)](frontend/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi)](backend/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](backend/requirements.txt)

---

## 📌 Features

### 1. Cost Intelligence & FinOps
- **Multi-Cloud Dashboards**: Live visibility into AWS and Azure spending and inventory.
- **AI Anomaly Detection**: ML-powered detection of cost spikes and unexpected usage patterns.
- **Budget Management**: Set, track, and receive alerts on cloud budgets with real-time utilization metrics.
- **Cost Forecasting**: Predict future spending based on historical usage patterns.

### 2. Intelligent Migration Advisor
- **Wizard-Driven Assessment**: Comprehensive profiling of organization, workload, and technical requirements.
- **ML Scoring Engine**: Data-driven provider recommendations (AWS, Azure, GCP, IBM, Oracle) weighted by performance, compliance, and cost.
- **TCO Comparison**: Real-time Total Cost of Ownership estimates across major cloud providers.
- **Evidence-Based Insights**: Transparent logic for every recommendation, including migration risks and bottlenecks.

### 3. Governance & Compliance
- **Tagging Compliance**: Automated scanning of AWS resources for mandatory tags.
- **Policy Enforcement**: Identification of idle instances, unattached volumes, and security violations.
- **Resource Inventory**: Unified view of all cloud resources across regions and providers.

---

## 🏗️ Project Structure

```text
.
├── backend/                # FastAPI Application
│   ├── app/                # Core Application Logic
│   │   ├── api/            # REST API Endpoints (Auth, Cloud, AI, etc.)
│   │   ├── services/       # Business Logic (Cost Engine, ML, Migration)
│   │   ├── models/         # Database Models (SQLAlchemy)
│   │   └── database/       # Session & Connection Management
│   ├── alembic/            # Database Migrations
│   ├── scripts/            # Operational & Utility Scripts
│   └── main.py             # Entry Point
├── frontend/               # React Application (TypeScript)
│   ├── src/
│   │   ├── pages/          # Feature Pages (Dashboards, Wizards)
│   │   ├── services/       # Frontend API Clients
│   │   └── components/     # Reusable UI Library
│   └── package.json
├── docs/                   # Product Documentation & PRDs
├── docker/                 # Containerization Configs
└── start-project.ps1       # One-click startup script (Windows)
```

---

## 🚀 Getting Started

### Prerequisites
- **Node.js** 16+ & **npm**
- **Python** 3.10+
- **AWS/Azure Account** with appropriate API access

### 1. Setup Environment
Create a `.env` file in the root directory (refer to `.env.example` if available) with your cloud credentials:
```bash
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=...
```

### 2. Install & Run
Use the provided PowerShell script (Windows) or manual commands:

**Windows (Automated):**
```powershell
./start-project.ps1
```

**Manual (Cross-Platform):**
```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend
cd frontend
npm install
npm start
```

---

## 🔐 Security & Compliance
The platform implements enterprise-grade security practices:
- **AES-256 Encryption** for stored cloud credentials.
- **JWT Authentication** for secure API access.
- **Role-Based Access Control** (RBAC) ready.

---

## 📜 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.