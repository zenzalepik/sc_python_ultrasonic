import tkinter as tk
import time
from versi_library import UltrasonicSensor

sensor = UltrasonicSensor(use_real_hardware=True)
sensor.start()

win = tk.Tk()
win.title("TEST HARDWARE - Library UltrasonicSensor")
win.geometry("420x320")
win.configure(bg="#1e1e2e")
win.resizable(False, False)

font_label = ("Consolas", 11)
font_value = ("Consolas", 14, "bold")
font_title = ("Consolas", 10)

# Top bar
bar = tk.Frame(win, bg="#1e1e2e")
bar.pack(fill="x", padx=15, pady=(10, 2))
tk.Label(bar, text="LIBRARY TEST | Real Hardware", font=font_title,
         bg="#1e1e2e", fg="#585b70").pack(side="left")

# Main info
main_frame = tk.Frame(win, bg="#181825", padx=15, pady=15)
main_frame.pack(fill="both", expand=True, padx=15, pady=5)

rows = [
    ("State", "state_val", "#89b4fa"),
    ("Jarak", "jarak_val", "#cdd6f4"),
    ("Baseline", "baseline_val", "#a6e3a1"),
    ("Delta", "delta_val", "#f9e2af"),
    ("Durasi Lock", "durasi_val", "#cdd6f4"),
    ("Menjauh", "menjauh_val", "#f38ba8"),
]

labels = {}
for i, (title, key, color) in enumerate(rows):
    f = tk.Frame(main_frame, bg="#181825")
    f.pack(fill="x", pady=2)
    tk.Label(f, text=title, font=font_label, bg="#181825", fg="#585b70",
             width=14, anchor="w").pack(side="left")
    v = tk.Label(f, text="...", font=font_value, bg="#181825", fg=color, anchor="w")
    v.pack(side="left", fill="x", expand=True)
    labels[key] = v

# Bottom status
status_label = tk.Label(win, text="Starting...", font=font_label,
                        bg="#1e1e2e", fg="#585b70", anchor="w")
status_label.pack(fill="x", padx=15, pady=(0, 10))

def poll():
    s = sensor.state or "..."
    lb = sensor.baseline
    j = sensor.jarak
    d = sensor.delta
    dur = sensor.durasi_detik
    hit = sensor.menjauh_hitungan
    err = sensor.sensor_error

    labels["state_val"].config(text=s)
    labels["jarak_val"].config(text=f"{j} cm" if j is not None else "...")
    labels["baseline_val"].config(text=f"{lb} cm" if lb is not None else "...")
    labels["delta_val"].config(text=f"{d} cm" if d is not None else "...")
    labels["durasi_val"].config(text=f"{dur // 60:02d}:{dur % 60:02d}" if dur else "00:00")
    labels["menjauh_val"].config(text=f"{hit}/5" if hit else "-")

    if err:
        status_label.config(text="[ERROR] Sensor bermasalah!", fg="#f38ba8")
    elif s == "LOCK":
        status_label.config(text=f"[LOCKED] Objek terdeteksi pada {j} cm", fg="#a6e3a1")
    elif s == "MENDEKAT":
        status_label.config(text=f"[MENDEKAT] Objek mendekat pada {j} cm", fg="#f9e2af")
    elif s == "MENJAUH":
        status_label.config(text=f"[MENJAUH] Hitungan {hit}/5", fg="#f9e2af")
    elif s == "IDLE":
        status_label.config(text=f"[IDLE] Memantau... jarak ambient {j} cm", fg="#89b4fa")

    win.after(200, poll)

start_time = time.time()

def on_close():
    sensor.stop()
    win.destroy()

win.after(200, poll)
win.protocol("WM_DELETE_WINDOW", on_close)
win.mainloop()
