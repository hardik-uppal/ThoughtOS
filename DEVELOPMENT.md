# Developer Environment Setup

This guide explains how to run ThoughtOS locally for rapid development, avoiding the need to rebuild Docker containers for every code change.

## Overview
We will use a **Hybrid Setup**:
1.  **Neo4j (Database)**: Runs in Docker (stable, easy to manage).
2.  **Backend (FastAPI)**: Runs locally with Python (Hot Reload enabled).
3.  **Frontend (React)**: Runs locally with Vite (Hot Reload enabled).

---

## 1. Prerequisites
-   Python 3.10+
-   Node.js 18+
-   Docker (for the database only)

## 2. Start the Database (Neo4j)
Instead of running the whole stack, we just run Neo4j.

**Run this command:**
```bash
docker run -d \
    --name context_os_neo4j_dev \
    -p 7474:7474 -p 7687:7687 \
    -v $PWD/data/neo4j:/data \
    -e NEO4J_AUTH=neo4j/password \
    -e NEO4J_PLUGINS='["apoc", "graph-data-science"]' \
    neo4j:5.15-community
```

*To stop it later:* `docker stop context_os_neo4j_dev && docker rm context_os_neo4j_dev`

## 3. Backend Setup
1.  **Navigate to root**:
    ```bash
    cd /home/hardik/Projects/ThoughtOS
    ```
2.  **Create venv** (first time only):
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Configure Environment**:
    Ensure your `.env` file exists in the root with your API keys.
    *   `NEO4J_URI` should be `bolt://localhost:7687` (since it's now local).
    *   Add this line to `.env` if missing:
        ```bash
        NEO4J_URI=bolt://localhost:7687
        ```
4.  **Run with Hot Reload**:
    ```bash
    source venv/bin/activate
    uvicorn backend.main:app --reload --port 8000
    ```
    *Server will be at http://localhost:8000*

## 4. Frontend Setup
1.  **Navigate to frontend**:
    ```bash
    cd frontend
    ```
2.  **Install dependencies** (first time only):
    ```bash
    npm install
    ```
3.  **Run Dev Server**:
    ```bash
    npm run dev
    ```
    *App will be at http://localhost:5173*

## 5. Summary of Workflow
1.  **Terminal 1**: `docker run ...` (Neo4j)
2.  **Terminal 2**: `uvicorn ...` (Backend)
3.  **Terminal 3**: `npm run dev` (Frontend)

Now, any change you make to `.py` or `.tsx` files will reflect immediately!

## 6. Remote Access (The "Invalid Origin" Fix)
Google blocks private IP addresses (like `192.168.x.x` or `100.x.x.x`) for security.
To access the app from your Mac/Windows machine while it runs on the Linux server, you must use **SSH Port Forwarding**.

1.  **On your local machine (Mac/Windows)**, run this terminal command:
    ```bash
    # Replace 'hardik@your-server-ip' with your actual SSH login
    ssh -L 5173:localhost:5173 hardik@100.76.207.86
    ```
    *(Leave this terminal window open)*.

2.  **Open your Browser**:
    Go to `http://localhost:5173`

3.  **Why this works**:
    - Your browser thinks it is on `localhost` (which Google allows).
    - The traffic is securely tunneled to the server.
    - No changes needed in Google Cloud Console!


## 7. Troubleshooting
### Neo4j Fails to Start ("Lock file" error)
If the database container exits immediately, it usually means the data directory is locked from a previous crash.
**Fix:** Wipes the database to start fresh.
```bash
# 1. Stop container
docker stop context_os_neo4j_dev && docker rm context_os_neo4j_dev

# 2. Wipe data
sudo rm -rf data/neo4j

# 3. Start again
docker run -d ... (command from Section 2)
```

## 8. Mobile Testing (Ngrok)
To test on a mobile device (where SSH tunneling is difficult), use **ngrok** to create a public HTTPS tunnel. This is required because Google Verification **blocks private IP addresses** (like 192.168.x.x) and requires HTTPS.

1.  **Install ngrok**: [https://ngrok.com/download](https://ngrok.com/download)
2.  **Start the tunnel**:
    ```bash
    ngrok http 5173
    ```
    Copy the `https://...ngrok-free.app` URL.

3.  **Update Google Cloud Console**:
    *   Go to: [Google Cloud Console > Credentials](https://console.cloud.google.com/apis/credentials)
    *   Edit your OAuth 2.0 Client ID.
    *   Add the ngrok URL (e.g., `https://example.ngrok-free.app`) to **Authorized JavaScript origins**.
    *   (Optional) Add it to **Authorized redirect URIs** as well.

4.  **Test on Mobile**:
    Open the ngrok URL on your phone. Google Sign-In will now work because:
    *   The origin is HTTPS.
    *   The origin is whitelisted in your Google Console.
