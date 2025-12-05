# G-Maps Pro Scraper (Resilient Edition)

A robust, full-stack Google Maps scraping application designed to handle dynamic DOM elements, avoid bot detection, and support multi-user sessions via WebSocket.

## 🚀 Features

* **Frontend**: React (Vite) + Tailwind CSS + Lucide Icons.
* **Backend**: FastAPI + Selenium (Headless Chrome) + WebSockets.
* **Resilience**: Smart DOM polling, dynamic visual extraction (ratings/names), and "Resume" capability.
* **Export**: Client-side export to CSV and Excel (.xlsx).
* **Live View**: Real-time visual feedback of the scraping process.

## 📋 Prerequisites

To run this project, you need the following installed on your system:

1.  **Anaconda or Miniconda**: Used to manage the Python environment. [Download Miniconda](https://docs.conda.io/en/latest/miniconda.html)
2.  **Node.js & npm**: Required to build the frontend. [Download from Node.js Official Site](https://nodejs.org/) (Select the "LTS" version).
3.  **Google Chrome**: Required for the Selenium web driver.

## 🛠️ Installation & Setup Guide

Since the provided `setup.sh` only handles building and running the project, you must set up your environment (dependencies and tools) first.

### Step 1: Create & Configure Environment

Open your terminal (Anaconda Prompt on Windows) and follow these steps to prepare your system.

1.  **Create a new Conda environment (for Python):**
    ```bash
    conda create -n gmaps_scraper python=3.10 -y
    ```

2.  **Activate the environment:**
    ```bash
    conda activate gmaps_scraper
    ```

3.  **Verify Installations:**
    Ensure both Python (from Conda) and Node.js (standard install) are accessible.
    ```bash
    python --version
    node --version
    npm --version
    ```

### Step 2: Run the Project

Now that your environment is ready, you can use the project's setup script.

1.  **Make the script executable (Linux/Mac only):**
    ```bash
    chmod +x setup.sh
    ```

2.  **Run the setup script (Localhost Mode):**
    By default, this runs locally at `http://localhost:8000`.
    ```bash
    ./setup.sh
    ```

    *Note for Windows users:* If you cannot run `.sh` files, you can run the commands manually inside your `gmaps_scraper` environment:
    ```bash
    # 1. Build Frontend
    cd frontend
    npm install
    npm run build
    cd ..

    # 2. Start Backend
    cd backend
    pip install -r requirements.txt
    python main.py --host 0.0.0.0 --port 8000
    ```

### Step 3: Install & Configure Ngrok (Optional)

If you plan to use the --ngrok flag to expose the scraper publicly, you must install the Ngrok agent and authenticate it with your account. Create account [here](https://ngrok.com).

1. Install Ngrok (Linux/Debian/Ubuntu):
Run the following command to add the repository and install:

    ```
    curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
        | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null \
        && echo "deb https://ngrok-agent.s3.amazonaws.com bookworm main" \
        | sudo tee /etc/apt/sources.list.d/ngrok.list \
        && sudo apt update \
        && sudo apt install ngrok
    ```

(For Windows/Mac, follow instructions at [ngrok.com/download](https://ngrok.com/download))

2. Authenticate:
Copy your Authtoken from the Ngrok Dashboard and run:

    ```
    ngrok config add-authtoken <YOUR_AUTH_TOKEN>
    ```

### Optional: Enable Public Access (Ngrok)

If you want to share the tool publicly or access it from another device, enable Ngrok mode manually.

1.  **Stop the current server** (Ctrl+C).
2.  **Run with the flag:**
    ```bash
    cd backend
    python main.py --ngrok
    ```
    This will generate a temporary public URL (e.g., `https://xxxx-xx.ngrok-free.app`).

## 🖥️ Usage

1.  Open your browser and navigate to `http://127.0.0.1:8000`.
2.  Enter a search keyword (e.g., "Coffee shops in NYC").
3.  Toggle **Headless** if you want to see the browser popup (debugging) or keep it off for background processing.
4.  Click **START**.
5.  Use **STOP** to pause. Clicking **START** again with the *same keyword* will resume scraping. Changing the keyword starts a new session.
6.  Click **EXPORT** to download data as CSV or Excel.

## 📁 Project Structure
```text
maps-scraper-pro
├── frontend/ # React Vite App
│ ├── src/ # UI Components 
│ └── dist/ # Built static assets (after build) 
├── backend/ # FastAPI Server 
│ ├── main.py # Server entry point & WebSocket manager 
│ ├── worker.py # Selenium Scraper Logic 
│ └── requirements.txt 
└── setup.sh # Build & Run script
```