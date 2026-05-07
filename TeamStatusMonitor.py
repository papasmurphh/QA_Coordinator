import tkinter as tk
import ctypes
from ctypes import wintypes
import winsound
import time
import threading

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020

def capture_screen_region(x1, y1, x2, y2):
    """
    Captures the specified region of the screen (x1, y1, x2, y2)
    and returns raw pixel data as a bytes object (BGR...).
    """
    width = x2 - x1
    height = y2 - y1
    if width <= 0 or height <= 0:
        return b""  # Invalid region -> empty bytes

    hdc_screen = user32.GetDC(None)
    hdc_compatible = gdi32.CreateCompatibleDC(hdc_screen)
    hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
    gdi32.SelectObject(hdc_compatible, hbitmap)

    gdi32.BitBlt(hdc_compatible, 0, 0, width, height, hdc_screen, x1, y1, SRCCOPY)

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [
            ("bmiHeader", ctypes.c_uint32 * 10),
            ("bmiColors", ctypes.c_uint32 * 3),
        ]

    bmi = BITMAPINFO()
    bmi.bmiHeader[0] = 40  # biSize = 40
    bmi.bmiHeader[1] = width
    bmi.bmiHeader[2] = height
    bmi.bmiHeader[3] = (1 << 16) | 24  # planes=1, bitcount=24
    bmi.bmiHeader[4] = 0  # BI_RGB
    bmi.bmiHeader[5] = 0
    bmi.bmiHeader[6] = 0
    bmi.bmiHeader[7] = 0
    bmi.bmiHeader[8] = 0
    bmi.bmiHeader[9] = 0

    buf_size = width * height * 3
    buffer = (ctypes.c_char * buf_size)()
    gdi32.GetDIBits(hdc_compatible, hbitmap, 0, height,
                    ctypes.byref(buffer),
                    ctypes.byref(bmi), 0)

    user32.ReleaseDC(None, hdc_screen)
    gdi32.DeleteDC(hdc_compatible)
    gdi32.DeleteObject(hbitmap)

    return buffer.raw


class DraggableRegion(tk.Toplevel):
    """
    A small draggable square that the user can move around the screen.
    Once placed, user clicks 'Lock Region' to confirm the region.
    """
    def __init__(self, parent, size=60):
        super().__init__(parent)
        self.parent = parent
        self.overrideredirect(True)  # Remove window decorations
        self.size = size
        self.drag_x_offset = 0
        self.drag_y_offset = 0

        # Center on screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        start_x = (screen_w // 2) - (self.size // 2)
        start_y = (screen_h // 2) - (self.size // 2)
        self.geometry(f"{self.size}x{self.size}+{start_x}+{start_y}")

        # Make the window partially transparent so you can see behind it
        self.attributes("-alpha", 0.5)

        # Red border
        self.container = tk.Frame(self, bg="red", bd=2, relief="solid")
        self.container.pack(fill="both", expand=True)

        # Lock Region button
        btn_lock = tk.Button(self.container, text="Lock Region", command=self.lock_region)
        btn_lock.pack(side="bottom", fill="x")

        # Bind mouse events for dragging
        self.bind("<Button-1>", self.on_mouse_down)
        self.bind("<B1-Motion>", self.on_mouse_drag)

    def on_mouse_down(self, event):
        # Track the offset from the top-left corner of the window
        self.drag_x_offset = event.x
        self.drag_y_offset = event.y

    def on_mouse_drag(self, event):
        # Calculate new position
        x = self.winfo_x() + (event.x - self.drag_x_offset)
        y = self.winfo_y() + (event.y - self.drag_y_offset)
        self.geometry(f"+{x}+{y}")

    def lock_region(self):
        """
        Once user clicks Lock, we call back to the parent with the final coords.
        """
        x1 = self.winfo_rootx()
        y1 = self.winfo_rooty()
        x2 = x1 + self.size
        y2 = y1 + self.size

        self.parent.set_region(x1, y1, x2, y2)
        self.destroy()


class ScreenWatcherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Teams Status Watcher (Draggable Region)")
        self.geometry("300x230")
        self.resizable(False, False)

        # Region coordinates
        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None

        self.monitoring = False
        self.monitor_thread = None

        self.build_ui()

    def build_ui(self):
        # Three buttons for different sizes
        btn_small = tk.Button(self, text="Show Draggable Region (Small)", 
                              command=lambda: self.show_draggable_region(30))
        btn_small.pack(pady=5)

        btn_medium = tk.Button(self, text="Show Draggable Region (Medium)", 
                               command=lambda: self.show_draggable_region(60))
        btn_medium.pack(pady=5)

        btn_large = tk.Button(self, text="Show Draggable Region (Large)", 
                              command=lambda: self.show_draggable_region(300))
        btn_large.pack(pady=5)

        # Engage monitoring
        self.btn_monitor = tk.Button(self, text="Engage Monitoring", command=self.start_monitoring, state="disabled")
        self.btn_monitor.pack(pady=5)

        # Stop monitoring
        self.btn_stop = tk.Button(self, text="Stop Monitoring", command=self.stop_monitoring, state="disabled")
        self.btn_stop.pack(pady=5)

        self.info_label = tk.Label(self, text="No region locked yet.")
        self.info_label.pack(pady=5)

    def show_draggable_region(self, size):
        """
        Create a draggable region of a given size.
        """
        DraggableRegion(self, size=size)

    def set_region(self, x1, y1, x2, y2):
        """
        Called by the DraggableRegion once the user locks it.
        """
        self.start_x, self.start_y = x1, y1
        self.end_x, self.end_y = x2, y2
        self.info_label.config(
            text=f"Locked region: ({x1}, {y1}) to ({x2}, {y2})"
        )
        # Now we can engage monitoring
        self.btn_monitor.config(state="normal")

    def start_monitoring(self):
        if self.monitoring:
            return
        if None in (self.start_x, self.start_y, self.end_x, self.end_y):
            return

        self.monitoring = True
        self.btn_monitor.config(state="disabled")
        self.btn_stop.config(state="normal")

        # Start background thread
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        self.monitoring = False
        self.btn_monitor.config(state="normal")
        self.btn_stop.config(state="disabled")
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
            self.monitor_thread = None

    def monitor_loop(self):
        last_capture = capture_screen_region(self.start_x, self.start_y, self.end_x, self.end_y)

        while self.monitoring:
            time.sleep(0.5)
            new_capture = capture_screen_region(self.start_x, self.start_y, self.end_x, self.end_y)

            if new_capture != last_capture:
                self.notify_change()
                last_capture = new_capture

    def notify_change(self):
        # Play your custom WAV file (ensure the file is in the same folder, or use a full path)
        winsound.PlaySound("Windows Proximity Notification.wav",
                           winsound.SND_FILENAME | winsound.SND_ASYNC)
        # Show the popup
        self.show_popup("Status change detected!")

    def show_popup(self, message):
        popup = tk.Toplevel(self)
        popup.title("Change Detected")
        tk.Label(popup, text=message).pack(padx=10, pady=10)
        tk.Button(popup, text="OK", command=popup.destroy).pack(pady=5)
        popup.attributes("-topmost", True)


if __name__ == "__main__":
    app = ScreenWatcherApp()
    app.mainloop()