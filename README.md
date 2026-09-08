# SIH Institute Inspection Platform

The SIH Institute Inspection Platform is a prototype for inspecting and monitoring educational institutes. It combines:

- A FastAPI service that receives live PC telemetry over WebSockets.
- Python client agents that report CPU, memory, network, disk, and system information.
- A standalone dashboard for live monitoring and PC inventory.
- A React/Vite portal for institute management, inspection workflows, and live telemetry.
- An optional Spring Boot backend for authentication, institute management, assignments, inspections, and ML result storage.

## Project Structure

```text
SIH_Prototype/
|-- server.py                 FastAPI telemetry server
|-- client.py                 PC monitoring agent
|-- dashboard/                Standalone HTML dashboard
|-- frontend/                 React/Vite inspection portal
|-- backend/                  Optional Spring Boot REST API
|-- live_detection.py         Camera and ML inference utility
|-- camera_test.py            Camera stream test utility
|-- models/                   Trained inspection models and documentation
|-- requirements.txt          Python dependencies
`-- .gitignore
```

## Requirements

Install the following before running the project:

- Python 3.10 or newer
- Node.js 18 or newer for the React portal
- Java 21 for the optional Spring Boot backend
- A local network connection when monitoring other PCs

The Python requirements include FastAPI, WebSockets, psutil, OpenCV, PyTorch, and Ultralytics. Some of these packages are large and may take time to install.

## Quick Start: PC Monitoring

The FastAPI service and client agents are the core of the live PC monitoring feature.

### 1. Install Python dependencies

From the `SIH_Prototype` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

On macOS or Linux, activate the environment with:

```bash
source .venv/bin/activate
```

### 2. Start the FastAPI server

Run this on the computer that will host the monitoring dashboard:

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

The server will be available at `http://localhost:8000`.

### 3. Configure and start a client

Open `client.py` and set `SERVER_IP` to the LAN IPv4 address of the computer running the FastAPI server:

```python
SERVER_IP = "192.168.1.10"
SERVER_PORT = 8000
```

Use `127.0.0.1` when the client and server run on the same computer. Run the client on each monitored PC:

```bash
python client.py
```

Each client connects to `ws://SERVER_IP:8000/ws`, sends a system-information handshake, and then sends live metrics every two seconds. Static system information is refreshed periodically while the client is running and is also refreshed whenever the client reconnects.

### 4. Open a dashboard

#### Standalone dashboard

Start a small static file server from the project directory:

```bash
python -m http.server 5500 --directory dashboard
```

Open [http://localhost:5500](http://localhost:5500) in a browser. The dashboard provides:

- Server and online-client status.
- Live CPU, RAM, IP address, and last-seen information.
- PC inventory for clients that have connected.
- Detailed system information for each PC.

The standalone dashboard reads the FastAPI service from `http://127.0.0.1:8000`. To view a server running on another computer, update `API_BASE` in `dashboard/app.js`.

#### React portal

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, normally [http://localhost:5173](http://localhost:5173). The portal includes institute dashboards, lab and asset views, inspection workflow pages, and the live PC telemetry page. It connects to the FastAPI service at `http://127.0.0.1:8000` and to the optional Spring Boot API at `http://localhost:8080`.

## FastAPI Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/` | Server status, online-client count, and inventory count |
| `GET` | `/clients` | Current live clients and telemetry |
| `GET` | `/inventory` | Known clients with system information and online state |
| `WS` | `/ws` | Client handshake and live telemetry stream |

The FastAPI server currently stores client and inventory data in memory. Inventory entries remain available while the server is running, including after a client disconnects, but they are cleared when the server process restarts. The client handshake repopulates and refreshes the record after a restart.

## Optional Spring Boot Backend

The `backend/` directory contains a separate REST API for the broader inspection platform. It provides:

- JWT authentication and role-based access control.
- Institute and inspector management.
- Inspector-to-institute assignments.
- Inspection lifecycle management.
- Storage for combined ML inspection results.
- Audit events and dashboard summary endpoints.

The default configuration uses an in-memory H2 database, so PostgreSQL is not required for a basic local run.

### Start the backend

From the `backend` directory on Windows:

```powershell
.\mvnw.cmd spring-boot:run
```

On macOS or Linux:

```bash
./mvnw spring-boot:run
```

The backend runs at `http://localhost:8080`. Seed the standard development accounts with:

```bash
curl -X POST http://localhost:8080/api/auth/seed
```

For PostgreSQL configuration, copy `backend/src/main/resources/application-local.yml.example` to `application-local.yml` and provide the database credentials. See [`backend/README.md`](backend/README.md) for the complete backend architecture and endpoint reference.

## Inspection and ML Utilities

The repository also contains optional visual inspection utilities:

- `live_detection.py` runs camera-stream inference using the trained models.
- `camera_test.py` checks access to a camera stream.
- `models/` contains the available model files and inference notes.

These utilities are independent of the PC telemetry dashboard. Review the model documentation before using the results for inspection decisions; the models are intended for prototype and human-review workflows.

## Common Commands

```bash
# FastAPI server
python -m uvicorn server:app --host 0.0.0.0 --port 8000

# PC client
python client.py

# Standalone dashboard server
python -m http.server 5500 --directory dashboard

# React portal
cd frontend
npm run dev

# React production build and lint
npm run build
npm run lint

# Spring Boot tests
cd backend
./mvnw test
```

On Windows, use `npm.cmd` and `mvnw.cmd` if PowerShell does not resolve the command directly.

## Troubleshooting

### The dashboard shows no clients

1. Confirm that the FastAPI server is running on port `8000`.
2. Confirm that `SERVER_IP` in `client.py` points to the server computer's reachable LAN address.
3. Make sure both computers are on the same network.
4. Allow Python or TCP port `8000` through the host computer's firewall.
5. Check the client terminal for connection and retry messages.

### Port 8000 is already in use

Stop the existing process using port `8000`, or start the service on another port and update `SERVER_PORT` in `client.py` and `API_BASE` in the dashboard and frontend services.

### The React portal shows the scanner as offline

The React portal expects the FastAPI service at `http://127.0.0.1:8000`. Start the scanner service first, or update `frontend/src/services/scannerService.js` when the scanner is hosted on another computer.

### The backend is offline

The React portal can still open in its standalone or fallback mode, but backend-backed authentication and persisted inspection workflows require the Spring Boot service on port `8080`.

## Notes

- Do not expose the development services directly to the public internet without authentication, access control, and a production deployment configuration.
- Keep `SERVER_IP`, database credentials, and JWT secrets out of public commits when they contain environment-specific or sensitive values.
- The current telemetry inventory is process-local memory. Use a database-backed store before relying on it for long-term asset records.
