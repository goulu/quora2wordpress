#!/usr/bin/env python3
import os
import sys
import time
import datetime

LOG_PATH = "/home/goulu/Documents/develop/quora2wordpress/chrome_lifecycle.log"

def log_message(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [MONITOR] {message}\n")
        print(f"[{timestamp}] [MONITOR] {message}")
    except Exception as e:
        print(f"Error writing to log: {e}", file=sys.stderr)

def get_process_cmdline(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            content = f.read()
            # cmdline is null-byte separated arguments
            args = [arg.decode("utf-8", errors="replace") for arg in content.split(b"\x00") if arg]
            return " ".join(args)
    except Exception:
        return ""

def get_process_ppid(pid):
    try:
        with open(f"/proc/{pid}/stat", "r") as f:
            parts = f.read().split()
            # PPID is the 4th field in /proc/<pid>/stat
            return int(parts[3])
    except Exception:
        return None

def get_chrome_processes():
    processes = {}
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            pid = int(entry)
            cmd = get_process_cmdline(pid)
            if cmd and ("chrome" in cmd.lower() or "chromium" in cmd.lower()):
                ppid = get_process_ppid(pid)
                processes[pid] = {
                    "ppid": ppid,
                    "cmd": cmd
                }
    return processes

def main():
    log_message("Chrome process monitor started.")
    
    # Get initial processes
    active_processes = get_chrome_processes()
    if active_processes:
        log_message(f"Found {len(active_processes)} already running chrome processes:")
        for pid, info in active_processes.items():
            log_message(f"  ALREADY RUNNING: PID={pid}, PPID={info['ppid']}, CMD={info['cmd'][:150]}")
            
    try:
        while True:
            time.sleep(0.5)
            current_processes = get_chrome_processes()
            
            # Check for new processes
            for pid, info in current_processes.items():
                if pid not in active_processes:
                    log_message(f"CREATED: PID={pid}, PPID={info['ppid']}, CMD={info['cmd'][:200]}")
                    active_processes[pid] = info
                    
            # Check for terminated processes
            terminated_pids = []
            for pid in active_processes:
                if pid not in current_processes:
                    info = active_processes[pid]
                    log_message(f"DESTROYED: PID={pid}, PPID={info['ppid']}, CMD={info['cmd'][:200]}")
                    terminated_pids.append(pid)
                    
            for pid in terminated_pids:
                del active_processes[pid]
                
    except KeyboardInterrupt:
        log_message("Chrome process monitor stopped by user.")
    except Exception as e:
        log_message(f"Monitor error: {e}")

if __name__ == "__main__":
    main()
