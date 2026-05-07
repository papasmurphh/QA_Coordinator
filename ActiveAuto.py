import time
import ctypes
from ctypes import wintypes

# ----------------------------
# Windows idle-time detection
# ----------------------------

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

GetLastInputInfo = user32.GetLastInputInfo
GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
GetLastInputInfo.restype = wintypes.BOOL

# Prefer GetTickCount64 when available
try:
    GetTickCount64 = kernel32.GetTickCount64
    GetTickCount64.restype = ctypes.c_ulonglong

    def _get_tick_ms():
        return int(GetTickCount64())
except AttributeError:
    GetTickCount = kernel32.GetTickCount
    GetTickCount.restype = wintypes.DWORD

    def _get_tick_ms():
        return int(GetTickCount())

def get_idle_seconds() -> float:
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)

    if not GetLastInputInfo(ctypes.byref(lii)):
        raise ctypes.WinError(ctypes.get_last_error())

    now_ms = _get_tick_ms()
    last_ms = int(lii.dwTime)

    # Handle 32-bit tick wrap if GetTickCount is used
    if now_ms < last_ms:
        now_ms += 2**32

    return (now_ms - last_ms) / 1000.0

# ----------------------------
# Original mouse movement (emulated exactly)
# ----------------------------

mouse_event = user32.mouse_event
SetCursorPos = user32.SetCursorPos

MOUSEEVENTF_MOVE = 0x0001

def original_mouse_move_once():
    # EXACTLY what your original script does
    SetCursorPos(0, 0)
    mouse_event(MOUSEEVENTF_MOVE, 1, 1, 0, 0)

# ----------------------------
# Main loop
# ----------------------------

def keep_computer_active(idle_threshold_seconds=90, check_interval=0.25, move_interval=10.0):
    """
    - Does nothing until idle >= idle_threshold_seconds.
    - When idle threshold is reached, performs the exact same movement as your original script.
    - Stops immediately when user input happens again.
    """
    last_move_time = 0.0

    print(f"Running. Activates after {idle_threshold_seconds} seconds of inactivity.")
    print("Press Ctrl+C to stop.")

    while True:
        idle = get_idle_seconds()

        if idle >= idle_threshold_seconds:
            now = time.time()
            if last_move_time == 0.0 or (now - last_move_time) >= move_interval:
                original_mouse_move_once()
                last_move_time = now
        else:
            # Reset so we wait a full move_interval after going idle again
            last_move_time = 0.0

        time.sleep(check_interval)

if __name__ == "__main__":
    try:
        keep_computer_active(
            idle_threshold_seconds=90,  # 1.5 minutes
            check_interval=0.25,        # how often to check for activity
            move_interval=10.0          # same as your original: every 10 seconds while idle
        )
    except KeyboardInterrupt:
        print("\nStopped.")
