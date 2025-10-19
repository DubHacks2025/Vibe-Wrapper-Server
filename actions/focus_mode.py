# actions/focus_mode.py
import subprocess
import json
from typing import Dict, Any

def toggle_do_not_disturb(enable: bool = True) -> Dict[str, Any]:
    """Toggle Do Not Disturb mode on macOS using multiple approaches"""
    try:
        # Method 1: Try using osascript with simpler approach
        if enable:
            script = '''
            tell application "System Events"
                set dndEnabled to do shell script "defaults -currentHost read com.apple.notificationcenterui dndStart 2>/dev/null || echo 'disabled'"
                if dndEnabled is "disabled" then
                    do shell script "defaults -currentHost write com.apple.notificationcenterui dndStart -1 && killall NotificationCenter"
                    return "enabled"
                else
                    return "already enabled"
                end if
            end tell
            '''
        else:
            script = '''
            tell application "System Events"
                set dndEnabled to do shell script "defaults -currentHost read com.apple.notificationcenterui dndStart 2>/dev/null || echo 'disabled'"
                if dndEnabled is not "disabled" then
                    do shell script "defaults -currentHost delete com.apple.notificationcenterui dndStart && killall NotificationCenter"
                    return "disabled"
                else
                    return "already disabled"
                end if
            end tell
            '''

        # Try the osascript approach first
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            response = result.stdout.strip()
            if "enabled" in response:
                return {
                    "ok": True,
                    "message": f"Do Not Disturb mode enabled",
                    "status": "enabled",
                    "enabled": True
                }
            elif "disabled" in response:
                return {
                    "ok": True,
                    "message": f"Do Not Disturb mode disabled",
                    "status": "disabled",
                    "enabled": False
                }

        # Method 2: Try direct defaults command approach
        return toggle_do_not_disturb_direct(enable)

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "Do Not Disturb toggle timed out",
            "enabled": enable
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to toggle Do Not Disturb: {str(e)}",
            "enabled": enable
        }

def toggle_do_not_disturb_direct(enable: bool = True) -> Dict[str, Any]:
    """Direct approach using defaults command"""
    try:
        if enable:
            # Turn on Do Not Disturb using defaults
            cmd = [
                "defaults", "-currentHost", "write", "com.apple.notificationcenterui",
                "dndStart", "-1"
            ]
        else:
            # Turn off Do Not Disturb
            cmd = [
                "defaults", "-currentHost", "delete", "com.apple.notificationcenterui",
                "dndStart"
            ]

        # Execute the command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            # Kill the NotificationCenter process to apply changes
            subprocess.run(
                ["killall", "NotificationCenter"],
                capture_output=True,
                timeout=5
            )

            status = "enabled" if enable else "disabled"
            return {
                "ok": True,
                "message": f"Do Not Disturb mode {status}",
                "status": status,
                "enabled": enable
            }
        else:
            # Method 3: Try the user-friendly approach
            return toggle_do_not_disturb_fallback(enable)

    except Exception as e:
        return {
            "ok": False,
            "error": f"Direct method failed: {str(e)}",
            "enabled": enable
        }

def toggle_do_not_disturb_fallback(enable: bool = True) -> Dict[str, Any]:
    """Fallback method using multiple approaches"""
    try:
        # Method 1: Try using shortcuts command (macOS Monterey+)
        try:
            if enable:
                result = subprocess.run([
                    "shortcuts", "run", "Set Focus", "--input", "Do Not Disturb"
                ], capture_output=True, text=True, timeout=10)
            else:
                result = subprocess.run([
                    "shortcuts", "run", "Turn Off Focus"
                ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                status = "enabled" if enable else "disabled"
                return {
                    "ok": True,
                    "message": f"Focus mode {status} using Shortcuts",
                    "status": status,
                    "enabled": enable,
                    "method": "shortcuts"
                }
        except Exception:
            pass  # Continue to next method

        # Method 2: Try using the newer m-cli approach
        try:
            if enable:
                subprocess.run([
                    "m", "focus", "on"
                ], capture_output=True, timeout=10)
            else:
                subprocess.run([
                    "m", "focus", "off"
                ], capture_output=True, timeout=10)

            status = "enabled" if enable else "disabled"
            return {
                "ok": True,
                "message": f"Focus mode {status} using m-cli",
                "status": status,
                "enabled": enable,
                "method": "m-cli"
            }
        except Exception:
            pass  # Continue to next method

        # Method 3: User-friendly approach - open Focus settings
        if enable:
            subprocess.run([
                "open", "x-apple.systempreferences:com.apple.preference.notifications"
            ], timeout=5)

            return {
                "ok": True,
                "message": "Opening Focus settings - please enable Do Not Disturb manually",
                "status": "manual_setup_required",
                "enabled": enable,
                "note": "Please enable Do Not Disturb in the Focus settings that just opened",
                "method": "manual"
            }
        else:
            # For disabling, try the basic approach
            subprocess.run([
                "defaults", "-currentHost", "delete", "com.apple.notificationcenterui", "dndStart"
            ], timeout=5)

            subprocess.run(["killall", "NotificationCenter"], timeout=5)

            return {
                "ok": True,
                "message": "Do Not Disturb disabled",
                "status": "disabled",
                "enabled": False,
                "method": "defaults"
            }

    except Exception as e:
        return {
            "ok": False,
            "error": f"All focus mode methods failed: {str(e)}",
            "enabled": enable,
            "note": "Please manually enable/disable Do Not Disturb in System Preferences > Focus"
        }

def enable_focus_mode() -> Dict[str, Any]:
    """Enable focus mode (turn on Do Not Disturb)"""
    return toggle_do_not_disturb(True)

def disable_focus_mode() -> Dict[str, Any]:
    """Disable focus mode (turn off Do Not Disturb)"""
    return toggle_do_not_disturb(False)

def get_focus_status() -> Dict[str, Any]:
    """Get current Do Not Disturb status using defaults command"""
    try:
        # Check Do Not Disturb status using defaults command
        result = subprocess.run([
            "defaults", "-currentHost", "read", "com.apple.notificationcenterui", "dndStart"
        ], capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            # If we get a value, Do Not Disturb is enabled
            dnd_value = result.stdout.strip()
            if dnd_value and dnd_value != "(null)":
                return {
                    "ok": True,
                    "status": "enabled",
                    "enabled": True,
                    "value": dnd_value
                }
            else:
                return {
                    "ok": True,
                    "status": "disabled",
                    "enabled": False
                }
        else:
            # If the key doesn't exist, Do Not Disturb is disabled
            return {
                "ok": True,
                "status": "disabled",
                "enabled": False
            }

    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to get Do Not Disturb status: {str(e)}"
        }

def set_focus_duration(minutes: int) -> Dict[str, Any]:
    """Set focus mode for a specific duration"""
    try:
        if minutes <= 0:
            return {
                "ok": False,
                "error": "Duration must be greater than 0 minutes"
            }

        # Enable Do Not Disturb first
        enable_result = enable_focus_mode()
        if not enable_result["ok"]:
            return enable_result

        # Schedule turning off Do Not Disturb after specified duration
        script = f'''
        do shell script "sleep {minutes * 60} && osascript -e 'tell application \\"System Events\\" to tell process \\"NotificationCenter\\" to click (first button whose description contains \\"Do Not Disturb\\")'"
        '''

        # Run the scheduled task in background
        subprocess.Popen(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return {
            "ok": True,
            "message": f"Focus mode enabled for {minutes} minutes",
            "duration_minutes": minutes,
            "enabled": True
        }

    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to set focus duration: {str(e)}"
        }

def diagnose_focus_mode() -> Dict[str, Any]:
    """Diagnose focus mode capabilities on the current system"""
    try:
        diagnosis = {
            "ok": True,
            "system_info": {},
            "available_methods": [],
            "recommendations": []
        }

        # Check macOS version
        try:
            result = subprocess.run([
                "sw_vers", "-productVersion"
            ], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                diagnosis["system_info"]["macos_version"] = result.stdout.strip()
        except Exception:
            diagnosis["system_info"]["macos_version"] = "unknown"

        # Check if defaults command works
        try:
            result = subprocess.run([
                "defaults", "-currentHost", "read", "com.apple.notificationcenterui", "dndStart"
            ], capture_output=True, text=True, timeout=5)
            diagnosis["available_methods"].append("defaults_command")
        except Exception:
            diagnosis["recommendations"].append("defaults command not available")

        # Check if shortcuts command is available
        try:
            result = subprocess.run([
                "shortcuts", "--help"
            ], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                diagnosis["available_methods"].append("shortcuts_command")
        except Exception:
            diagnosis["recommendations"].append("shortcuts command not available (requires macOS Monterey+)")

        # Check if m-cli is available
        try:
            result = subprocess.run([
                "m", "--version"
            ], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                diagnosis["available_methods"].append("m_cli")
        except Exception:
            diagnosis["recommendations"].append("m-cli not installed (optional: brew install m-cli)")

        # Check current focus status
        status_result = get_focus_status()
        diagnosis["current_status"] = status_result

        # Add recommendations based on available methods
        if not diagnosis["available_methods"]:
            diagnosis["recommendations"].append("Manual control recommended: System Preferences > Focus")

        return diagnosis

    except Exception as e:
        return {
            "ok": False,
            "error": f"Diagnosis failed: {str(e)}"
        }

if __name__ == "__main__":
    # Test the functions
    print("Testing Focus Mode Functions:")
    print("=" * 40)

    # Run diagnosis first
    diagnosis = diagnose_focus_mode()
    print("System Diagnosis:")
    print(json.dumps(diagnosis, indent=2))
    print()

    # Test getting status
    status_result = get_focus_status()
    print("Current Status:")
    print(json.dumps(status_result, indent=2))

    # Test enabling focus mode
    enable_result = enable_focus_mode()
    print("\nEnable Focus Mode:")
    print(json.dumps(enable_result, indent=2))

    # Test setting duration
    duration_result = set_focus_duration(5)
    print("\nSet Focus Duration (5 minutes):")
    print(json.dumps(duration_result, indent=2))
