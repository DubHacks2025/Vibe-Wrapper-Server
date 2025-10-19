# actions/process_manager.py
import psutil
import json
import subprocess
import sys
from typing import Dict, List, Optional, Any

# Essential system processes that should never be killed
ESSENTIAL_PROCESSES = {
    # Core system processes
    "kernel_task", "launchd", "system_profiler", "SystemUIServer",
    "WindowServer", "loginwindow", "Dock", "Finder", "coreservicesd",
    "kernelmanagerd", "hidd", "syspolicyd", "trustd", "securityd",
    "kextd", "mds", "mdworker", "mds_stores", "fseventsd",

    # Network and security
    "networksetup", "networkd", "configd", "discoveryd", "mDNSResponder",
    "WiFiAgent", "AirPort", "bluetoothd", "bluetoothaudiod",

    # Hardware management
    "powerd", "thermald", "hidd", "distnoted", "notifyd",
    "UserEventAgent", "sharingd", "locationd", "coreaudiod",

    # Shell and terminal
    "bash", "zsh", "sh", "csh", "tcsh", "ksh",

    # Development tools (be conservative)
    "Python", "python3", "node", "npm", "git", "vim", "nano",

    # System utilities
    "Activity Monitor", "Terminal", "Console", "Disk Utility",

    # Browser processes (user might lose work)
    "Safari", "Google Chrome", "Firefox", "Edge", "Opera",

    # Office applications (user might lose work)
    "Microsoft Word", "Microsoft Excel", "Microsoft PowerPoint",
    "Pages", "Numbers", "Keynote", "TextEdit", "Preview",

    # Communication apps
    "Messages", "Mail", "FaceTime", "Slack", "Discord", "Zoom",
    "Microsoft Teams", "Skype", "WhatsApp", "Telegram",

    # Media applications
    "iTunes", "Music", "TV", "Photos", "QuickTime Player",
    "VLC", "Spotify", "Audacity", "Final Cut Pro", "Logic Pro"
}

def get_process_info(proc: psutil.Process) -> Dict[str, Any]:
    """Get detailed information about a process"""
    try:
        # Get basic process info
        info = {
            "pid": proc.pid,
            "name": proc.name(),
            "status": proc.status(),
            "create_time": proc.create_time(),
            "cpu_percent": proc.cpu_percent(),
            "memory_info": proc.memory_info()._asdict(),
            "memory_percent": proc.memory_percent(),
            "num_threads": proc.num_threads(),
            "cmdline": " ".join(proc.cmdline()) if proc.cmdline() else "",
        }

        # Get I/O counters if available
        try:
            io_counters = proc.io_counters()
            info["io_counters"] = io_counters._asdict() if io_counters else None
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            info["io_counters"] = None

        # Get connections if available
        try:
            connections = proc.connections()
            info["connections"] = len(connections) if connections else 0
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            info["connections"] = 0

        return info
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None

def determine_load_level(cpu_percent: float, memory_percent: float, num_threads: int) -> str:
    """Determine if a process has Light, Medium, or Heavy load"""
    # Light: Low resource usage
    # Medium: Moderate resource usage
    # Heavy: High resource usage

    if cpu_percent > 50 or memory_percent > 10 or num_threads > 50:
        return "Heavy"
    elif cpu_percent > 10 or memory_percent > 2 or num_threads > 10:
        return "Medium"
    else:
        return "Light"

def is_essential_process(process_name: str, cmdline: str) -> bool:
    """Check if a process is essential and should not be killed"""
    process_name_lower = process_name.lower()
    cmdline_lower = cmdline.lower()

    # Check against essential processes list
    for essential in ESSENTIAL_PROCESSES:
        if essential.lower() in process_name_lower or essential.lower() in cmdline_lower:
            return True

    # Additional heuristics for essential processes
    essential_patterns = [
        "system", "kernel", "launchd", "windowserver", "dock", "finder",
        "loginwindow", "coreservices", "security", "trust", "network",
        "bluetooth", "power", "thermal", "audio", "video", "camera",
        "location", "notification", "disk", "file", "backup", "sync"
    ]

    for pattern in essential_patterns:
        if pattern in process_name_lower or pattern in cmdline_lower:
            return True

    return False

def list_processes(limit: int = 50, sort_by: str = "cpu") -> Dict[str, Any]:
    """List all running processes with their resource usage"""
    try:
        processes = []

        # Get all processes
        for proc in psutil.process_iter(['pid', 'name', 'status', 'create_time']):
            try:
                proc_info = get_process_info(proc)
                if proc_info:
                    # Add load level
                    proc_info["load_level"] = determine_load_level(
                        proc_info["cpu_percent"],
                        proc_info["memory_percent"],
                        proc_info["num_threads"]
                    )

                    # Add essential status
                    proc_info["is_essential"] = is_essential_process(
                        proc_info["name"],
                        proc_info["cmdline"]
                    )

                    processes.append(proc_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Sort processes
        if sort_by == "cpu":
            processes.sort(key=lambda x: x["cpu_percent"], reverse=True)
        elif sort_by == "memory":
            processes.sort(key=lambda x: x["memory_percent"], reverse=True)
        elif sort_by == "name":
            processes.sort(key=lambda x: x["name"].lower())
        elif sort_by == "load":
            load_order = {"Heavy": 3, "Medium": 2, "Light": 1}
            processes.sort(key=lambda x: load_order.get(x["load_level"], 0), reverse=True)

        # Limit results
        processes = processes[:limit]

        # Calculate summary statistics
        total_cpu = sum(p["cpu_percent"] for p in processes)
        total_memory = sum(p["memory_percent"] for p in processes)
        load_counts = {"Light": 0, "Medium": 0, "Heavy": 0}
        for p in processes:
            load_counts[p["load_level"]] += 1

        return {
            "ok": True,
            "processes": processes,
            "summary": {
                "total_processes": len(processes),
                "total_cpu_percent": round(total_cpu, 2),
                "total_memory_percent": round(total_memory, 2),
                "load_distribution": load_counts
            }
        }

    except Exception as e:
        return {"ok": False, "error": f"Failed to list processes: {str(e)}"}

def kill_process(pid: int, force: bool = False) -> Dict[str, Any]:
    """Safely kill a process by PID"""
    try:
        proc = psutil.Process(pid)
        proc_info = get_process_info(proc)

        if not proc_info:
            return {"ok": False, "error": f"Process {pid} not found"}

        # Check if process is essential
        if is_essential_process(proc_info["name"], proc_info["cmdline"]):
            return {
                "ok": False,
                "error": f"Cannot kill essential process: {proc_info['name']} (PID: {pid})",
                "process_name": proc_info["name"],
                "is_essential": True
            }

        # Kill the process
        if force:
            proc.kill()
            action = "force killed"
        else:
            proc.terminate()
            action = "terminated"

        return {
            "ok": True,
            "message": f"Process {proc_info['name']} (PID: {pid}) {action}",
            "process_name": proc_info["name"],
            "pid": pid,
            "action": action
        }

    except psutil.NoSuchProcess:
        return {"ok": False, "error": f"Process {pid} not found"}
    except psutil.AccessDenied:
        return {"ok": False, "error": f"Access denied to kill process {pid}"}
    except Exception as e:
        return {"ok": False, "error": f"Failed to kill process {pid}: {str(e)}"}

def kill_processes_by_name(name: str, force: bool = False) -> Dict[str, Any]:
    """Kill all processes with a specific name"""
    try:
        killed_processes = []
        failed_processes = []

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] == name:
                    result = kill_process(proc.info['pid'], force)
                    if result['ok']:
                        killed_processes.append(result)
                    else:
                        failed_processes.append(result)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return {
            "ok": True,
            "killed_processes": killed_processes,
            "failed_processes": failed_processes,
            "summary": {
                "total_killed": len(killed_processes),
                "total_failed": len(failed_processes)
            }
        }

    except Exception as e:
        return {"ok": False, "error": f"Failed to kill processes by name '{name}': {str(e)}"}

def get_system_resources() -> Dict[str, Any]:
    """Get overall system resource usage"""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()

        # Memory usage
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Disk usage
        disk = psutil.disk_usage('/')

        # Network I/O
        net_io = psutil.net_io_counters()

        # Boot time
        boot_time = psutil.boot_time()

        return {
            "ok": True,
            "cpu": {
                "usage_percent": cpu_percent,
                "count": cpu_count,
                "usage_per_core": psutil.cpu_percent(interval=1, percpu=True)
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "free": memory.free,
                "usage_percent": memory.percent,
                "swap_total": swap.total,
                "swap_used": swap.used,
                "swap_free": swap.free,
                "swap_usage_percent": swap.percent
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "usage_percent": (disk.used / disk.total) * 100
            },
            "network": {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            },
            "system": {
                "boot_time": boot_time,
                "uptime_seconds": psutil.time.time() - boot_time
            }
        }

    except Exception as e:
        return {"ok": False, "error": f"Failed to get system resources: {str(e)}"}

if __name__ == "__main__":
    # Test the functions
    print("System Resources:")
    print(json.dumps(get_system_resources(), indent=2))

    print("\nTop 10 Processes by CPU:")
    print(json.dumps(list_processes(limit=10, sort_by="cpu"), indent=2))
