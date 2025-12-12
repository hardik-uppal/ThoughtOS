# Docker SOP: Managing the ThoughtOS Environment

Because this system uses the **Snap** version of Docker on Linux, we occasionally encounter "Permission Denied" errors where containers refuse to stop even with `sudo`. This document outlines the standard procedures and the "Nuclear Option" for recovery.

## 1. The Golden Rule (Graceful Stop)
**ALWAYS** use this command to stop the application. Do not use `Ctrl+C` if possible, and avoided just closing the terminal.

```bash
docker compose -p context_os_final down
```

This command:
1.  Stops the containers.
2.  Removes the containers (preventing ID conflicts).
3.  Removes the network.
4.  Releases file locks.

---

## 2. Troubleshooting: "Permission Denied" / Stuck Containers
If you see errors like `Error response from daemon: cannot stop container... permission denied`, the AppArmor security layer has locked the process. PROCEED WITH CAUTION.

### Step 1: Identify the Stuck Processes
We need to find the `containerd-shim` processes belonging to Docker (namespace `moby`).
**DO NOT kill processes with namespace `k8s.io` (MicroK8s).**

Run this command to list them:
```bash
ps aux | grep containerd-shim | grep moby
```

### Step 2: The Nuclear Option (Force Kill)
Identify the PIDs (Process IDs) from the second column of the output above.
Run:
```bash
sudo kill -9 <PID1> <PID2> ...
```
*Example: `sudo kill -9 607686 611360`*

### Step 3: Cleanup & Restart Daemon
Killing processes manually leaves "ghost" files that block restart. You **MUST** cycle the daemon immediately after killing.

1.  **Restart Docker Daemon:**
    ```bash
    sudo systemctl restart docker
    ```

2.  **Clear "Ghost" Shims (Only if Restart fails):**
    If you still get `mkdir ... file exists` errors, you must manually delete the referencing directory found in the error log:
    ```bash
    sudo rm -rf /run/snap.docker/containerd/daemon/io.containerd.runtime.v2.task/moby/<CONTAINER_ID_FROM_ERROR>
    ```

### Step 4: Restart Application
Once the daemon is clean, start the app again using the correct project name:

```bash
docker compose -p context_os_final up --build
```
