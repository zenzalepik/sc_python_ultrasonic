import random
import sys
import time
import traceback
from collections import deque
from datetime import datetime

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

USE_REAL_HARDWARE = True
USE_GUI = True
LOG_LEVEL = "INFO"

SERIAL_BAUD = 9600
TIMEOUT = 1
JARAK_LOCK = 30.0          # ≤ ini → LOCK
JARAK_MENDEKAT = 50.0      # antara JARAK_LOCK dan ini → MENDEKAT
JARAK_MENJAUH = JARAK_LOCK       # > ini → mulai MENJAUH (sama dgn JARAK_LOCK)
JARAK_RESET = JARAK_MENDEKAT     # > ini → reset ke IDLE (sama dgn JARAK_MENDEKAT)
HEARTBEAT_DETIK = 1
SEND_INTERVAL_DETIK = 1
MENDEKAT_BATAS = 2
MENJAUH_BATAS = 5

_sim_state = "IDLE"
_sim_last_report = 0.0
_sim_count = 0


def log(level, msg):
    if level == "DEBUG" and LOG_LEVEL != "DEBUG":
        return
    ts = datetime.now().strftime("%H:%M:%S.%f")[:12]
    print(f"[{ts}] [{level}] {msg}", flush=True)


def simulate_reading():
    global _sim_state, _sim_last_report, _sim_count
    raw = random.uniform(2, 400)
    jarak = round(raw, 1)
    now = time.time()

    if (now - _sim_last_report) < SEND_INTERVAL_DETIK:
        return None
    _sim_last_report = now

    # ─── LOCK zone (≤ 30 cm) ───
    if jarak >= 2 and jarak <= JARAK_LOCK:
        _sim_count = 0
        just_entered = _sim_state != "LOCK"
        _sim_state = "LOCK"
        if just_entered:
            return f"LOCK | ADA objek terdeteksi | Jarak: {jarak} cm"
        return f"LOCK | Objek masih ada | Jarak: {jarak} cm"

    # ─── MENDEKAT zone (30–50 cm) ───
    if jarak > JARAK_LOCK and jarak <= JARAK_MENDEKAT:
        if _sim_state in ("LOCK", "MENJAUH"):
            pass  # fall through to menjauh handling
        else:
            _sim_count += 1
            if _sim_count >= MENDEKAT_BATAS:
                _sim_state = "MENDEKAT"
                return f"MENDEKAT | Ada objek mendekat | Jarak: {jarak} cm"
            _sim_state = "IDLE"
            return f"IDLE | TIDAK ADA objek | Jarak: {jarak} cm"

    # ─── MENJAUH / IDLE zone (> 50 cm) ───
    if _sim_state in ("LOCK", "MENJAUH"):
        _sim_count += 1
        if _sim_count >= MENJAUH_BATAS:
            _sim_state = "IDLE"
            _sim_count = 0
            return "UNLOCK | TIDAK ADA objek"
        _sim_state = "MENJAUH"
        return f"MENJAUH | Objek terlihat menjauh | Jarak: {jarak} cm | Hitungan: {_sim_count}/{MENJAUH_BATAS}"

    _sim_state = "IDLE"
    _sim_count = 0
    return f"IDLE | TIDAK ADA objek | Jarak: {jarak} cm"



def get_line(ser):
    if USE_REAL_HARDWARE:
        try:
            raw = ser.readline()
            line = raw.decode("utf-8").strip()
            return line if line else None
        except UnicodeDecodeError:
            return None
        except serial.SerialException:
            raise
    else:
        line = simulate_reading()
        time.sleep(0.3)
        return line


def setup_hardware():
    log("INFO", "setup_hardware() started")
    if not HAS_SERIAL:
        print("Module 'pyserial' tidak terinstall. Jalankan: pip install pyserial")
        sys.exit(1)

    import serial.tools.list_ports
    ports = list(serial.tools.list_ports.comports())
    port = None
    for p in ports:
        if "CH340" in p.description or "Arduino" in p.description or "USB" in p.description:
            port = p.device
            log("INFO", f"Matched port: {p.device} -> {p.description}")
            break
    if not port:
        print("Arduino tidak ditemukan. Periksa koneksi USB.")
        sys.exit(1)

    try:
        ser = serial.Serial(port, SERIAL_BAUD, timeout=0.5)
        ser.dtr = False
        time.sleep(0.3)
        ser.dtr = True
        time.sleep(0.5)
        ser.reset_input_buffer()
        log("INFO", f"Serial opened: {ser}")
        for _ in range(8):
            try:
                raw = ser.readline()
                if raw:
                    msg = raw.decode("utf-8").strip()
                    log("INFO", f"Arduino: {msg}")
            except UnicodeDecodeError:
                continue
        ser.timeout = 0.1
        log("INFO", "Serial siap, timeout=100ms")
        return ser
    except serial.SerialException as e:
        print(f"Gagal buka port {port}: {e}")
        sys.exit(1)


def parse_event(line):
    state = "IDLE"
    jarak = None
    sensor_error = "ERROR" in line or "DEBUG |" in line
    menjauh_hitungan = None

    if "LOCK" in line and "Jarak:" in line:
        state = "LOCK"
        jarak = float(line.split("Jarak:")[-1].replace("cm", "").strip())
    elif "MENDEKAT" in line and "Jarak:" in line:
        state = "MENDEKAT"
        jarak = float(line.split("Jarak:")[-1].replace("cm", "").strip())
    elif "MENJAUH" in line and "Jarak:" in line:
        state = "MENJAUH"
        jarak = float(line.split("Jarak:")[-1].split("|")[0].replace("cm", "").strip())
        if "Hitungan:" in line:
            try:
                menjauh_hitungan = int(line.split("Hitungan:")[-1].split("/")[0].strip())
            except ValueError:
                pass
    elif "UNLOCK" in line:
        state = "IDLE"
    elif "IDLE" in line and "Jarak:" in line:
        state = "IDLE"
        jarak = float(line.split("Jarak:")[-1].replace("cm", "").strip())
    if jarak == 0.0:
        sensor_error = True
    return state, jarak, sensor_error, menjauh_hitungan


def run_terminal():
    log("INFO", "run_terminal() started")
    ser = setup_hardware() if USE_REAL_HARDWARE else None
    mode = "REAL" if USE_REAL_HARDWARE else "SIMULASI"
    print(f"\nMode {mode} | Terminal")
    print("=== PENGUKUR JARAK DIGITAL ===")
    print("Tekan Ctrl+C untuk keluar\n")

    try:
        while True:
            line = get_line(ser)
            if line is None:
                continue
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] {line}", flush=True)
    except KeyboardInterrupt:
        print("\nKeluar oleh user.")
    except serial.SerialException as e:
        print(f"Koneksi terputus: {e}")
    except Exception as e:
        traceback.print_exc()
    finally:
        if ser:
            ser.close()
        print("Koneksi ditutup.")


class DistanceApp:
    BG = "#1e1e2e"
    FG = "#cdd6f4"
    FG_DIM = "#585b70"
    FG_BLUE = "#89b4fa"
    FG_GREEN = "#a6e3a1"
    FG_RED = "#f38ba8"
    FG_YELLOW = "#f9e2af"
    FG_LOG = "#45475a"
    CARD_BG = "#181825"

    def __init__(self, win, ser):
        import tkinter as tk
        self.tk = tk
        self.win = win
        self.ser = ser
        self.state = "IDLE"
        self.baseline = None
        self.obj_jarak = None
        self.lock_start = None
        self.reset_timer = None
        self.events = deque(maxlen=3)
        self.durasi_detik = 0
        self.dot_count = 0
        self._reset_scheduled = False

        win.title("Pengukur Jarak Digital")
        win.geometry("700x450")
        win.configure(bg=self.BG)
        win.resizable(False, False)

        self._build_top_bar()
        self._build_panels()
        self._build_bottom_bar()
        self._build_log()

        win.after(100, self.update)
        win.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_top_bar(self):
        mode = "REAL" if USE_REAL_HARDWARE else "SIMULASI"
        bar = self.tk.Frame(self.win, bg=self.BG)
        bar.pack(fill="x", padx=15, pady=(10, 2))
        self.tk.Label(
            bar, text=f"Mode {mode}", font=("Consolas", 10),
            bg=self.BG, fg=self.FG_DIM
        ).pack(side="left")
        self.info_label = self.tk.Label(
            bar, text=f"Send: tiap {SEND_INTERVAL_DETIK}s | Ambang: {JARAK_LOCK} cm",
            font=("Consolas", 10), bg=self.BG, fg=self.FG_DIM
        )
        self.info_label.pack(side="right")

        sep = self.tk.Frame(self.win, height=1, bg=self.FG_DIM)
        sep.pack(fill="x", padx=15, pady=2)

    def _build_panels(self):
        main = self.tk.Frame(self.win, bg=self.BG)
        main.pack(fill="both", expand=True, padx=15, pady=5)

        main.grid_columnconfigure(0, weight=1, uniform="panel")
        main.grid_columnconfigure(1, weight=1, uniform="panel")
        main.grid_rowconfigure(0, weight=1)

        self._build_left_panel(main)
        self._build_right_panel(main)

    def _build_left_panel(self, parent):
        frame = self.tk.Frame(parent, bg=self.CARD_BG, highlightbackground=self.FG_DIM, highlightthickness=1)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.tk.Label(
            frame, text="BASE (IDLE)", font=("Consolas", 11, "bold"),
            bg=self.CARD_BG, fg=self.FG_BLUE
        ).pack(pady=(10, 5))

        sep_in = self.tk.Frame(frame, height=1, bg=self.FG_DIM)
        sep_in.pack(fill="x", padx=20, pady=2)

        self.lbl_ambient_title = self.tk.Label(
            frame, text="Jarak Ambient", font=("Consolas", 10),
            bg=self.CARD_BG, fg=self.FG_DIM
        )
        self.lbl_ambient_title.pack(pady=(15, 0))

        self.lbl_ambient_val = self.tk.Label(
            frame, text="-- -- -- cm", font=("Consolas", 28, "bold"),
            bg=self.CARD_BG, fg=self.FG
        )
        self.lbl_ambient_val.pack(pady=(2, 5))

        self.lbl_threshold = self.tk.Label(
            frame, text=f"Send: tiap {SEND_INTERVAL_DETIK}s | Threshold: {JARAK_LOCK} cm", font=("Consolas", 10),
            bg=self.CARD_BG, fg=self.FG_DIM
        )
        self.lbl_threshold.pack(pady=(2, 0))

        self.lbl_delta = self.tk.Label(
            frame, text="Delta: -- -- -- cm", font=("Consolas", 10),
            bg=self.CARD_BG, fg=self.FG_DIM
        )
        self.lbl_delta.pack(pady=(2, 0))

        self.lbl_status_icon = self.tk.Label(
            frame, text="(O) IDLE", font=("Consolas", 13),
            bg=self.CARD_BG, fg=self.FG_BLUE
        )
        self.lbl_status_icon.pack(pady=(10, 5))

    def _build_right_panel(self, parent):
        frame = self.tk.Frame(parent, bg=self.CARD_BG, highlightbackground=self.FG_DIM, highlightthickness=1)
        frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self.right_title = self.tk.Label(
            frame, text="DETEKSI (LOCK)", font=("Consolas", 11, "bold"),
            bg=self.CARD_BG, fg=self.FG_GREEN
        )
        self.right_title.pack(pady=(10, 5))

        sep_in = self.tk.Frame(frame, height=1, bg=self.FG_DIM)
        sep_in.pack(fill="x", padx=20, pady=2)

        self.lbl_lock_badge = self.tk.Label(
            frame, text="", font=("Consolas", 32, "bold"),
            bg=self.CARD_BG, fg=self.FG_GREEN
        )
        self.lbl_lock_badge.pack(pady=(10, 0))

        self.lbl_obj_jarak = self.tk.Label(
            frame, text="-- -- -- cm", font=("Consolas", 28, "bold"),
            bg=self.CARD_BG, fg=self.FG
        )
        self.lbl_obj_jarak.pack(pady=(5, 0))

        self.lbl_obj_name = self.tk.Label(
            frame, text="", font=("Consolas", 11),
            bg=self.CARD_BG, fg=self.FG_DIM
        )
        self.lbl_obj_name.pack(pady=(2, 0))

        self.lbl_durasi = self.tk.Label(
            frame, text="", font=("Consolas", 11),
            bg=self.CARD_BG, fg=self.FG_DIM
        )
        self.lbl_durasi.pack(pady=(2, 0))

        self.lbl_waktu_deteksi = self.tk.Label(
            frame, text="--:--:--", font=("Consolas", 14),
            bg=self.CARD_BG, fg=self.FG_BLUE
        )
        self.lbl_waktu_deteksi.pack(pady=(8, 5))

    def _build_bottom_bar(self):
        bar = self.tk.Frame(self.win, bg=self.BG)
        bar.pack(fill="x", padx=15, pady=(2, 2))

        sep = self.tk.Frame(self.win, height=1, bg=self.FG_DIM)
        sep.pack(fill="x", padx=15, pady=2)

        self.lbl_status_bar = self.tk.Label(
            bar, text="Status: (O) Stable", font=("Consolas", 10),
            bg=self.BG, fg=self.FG_GREEN, anchor="w"
        )
        self.lbl_status_bar.pack(side="left", fill="x", expand=True)

        self.lbl_event = self.tk.Label(
            bar, text="Event: --", font=("Consolas", 10),
            bg=self.BG, fg=self.FG_DIM, anchor="e"
        )
        self.lbl_event.pack(side="right")

    def _build_log(self):
        self.log_frame = self.tk.Frame(self.win, bg=self.BG)
        self.log_frame.pack(fill="x", padx=15, pady=(0, 10))

        self.log_labels = []
        for _ in range(3):
            lbl = self.tk.Label(
                self.log_frame, text="", font=("Consolas", 9),
                bg=self.BG, fg=self.FG_LOG, anchor="w"
            )
            lbl.pack(fill="x")
            self.log_labels.append(lbl)

    def set_right_reset(self):
        self.right_title.config(text="RESET / LOADING", fg=self.FG_YELLOW)
        self.lbl_lock_badge.config(text="[R] RESET...", fg=self.FG_YELLOW)
        self.lbl_obj_jarak.config(text="-- -- --", fg=self.FG_DIM)
        self.lbl_obj_name.config(text="Menunggu objek...")
        self.lbl_durasi.config(text="")
        self.lbl_waktu_deteksi.config(text="--:--:--")

    def set_right_idle(self):
        self.right_title.config(text="DETEKSI (LOCK)", fg=self.FG_DIM)
        self.lbl_lock_badge.config(text="", fg=self.FG_DIM)
        self.lbl_obj_jarak.config(text="-- -- -- cm", fg=self.FG_DIM)
        self.lbl_obj_name.config(text="Tidak ada objek")
        self.lbl_durasi.config(text="")
        self.lbl_waktu_deteksi.config(text="--:--:--")

    def set_right_lock(self, jarak, ts):
        self.right_title.config(text="DETEKSI (LOCK)", fg=self.FG_GREEN)
        self.lbl_lock_badge.config(text="# LOCK #", fg=self.FG_GREEN)
        self.lbl_obj_jarak.config(text=f"{jarak} cm", fg=self.FG_GREEN)
        self.lbl_obj_name.config(text="Objek terdeteksi")
        delta = round(self.baseline - jarak, 1) if self.baseline else 0
        self.lbl_durasi.config(text=f"Delta: {delta} cm")
        self.lbl_waktu_deteksi.config(text=ts)

    def set_right_menjauh(self, jarak, hitungan, ts):
        self.right_title.config(text="DETEKSI (MENJAUH)", fg=self.FG_YELLOW)
        self.lbl_lock_badge.config(text="[^] MENJAUH", fg=self.FG_YELLOW)
        self.lbl_obj_jarak.config(text=f"{jarak} cm", fg=self.FG_YELLOW)
        self.lbl_obj_name.config(text=f"Objek menjauh... ({hitungan or '?'}/{MENJAUH_BATAS})")
        self.lbl_durasi.config(text="")
        self.lbl_waktu_deteksi.config(text=ts)

    def set_right_mendekat(self, jarak, ts):
        self.right_title.config(text="DETEKSI (MENDEKAT)", fg=self.FG_YELLOW)
        self.lbl_lock_badge.config(text="[V] MENDEKAT", fg=self.FG_YELLOW)
        self.lbl_obj_jarak.config(text=f"{jarak} cm", fg=self.FG_YELLOW)
        self.lbl_obj_name.config(text="Objek mendekat...")
        self.lbl_durasi.config(text="")
        self.lbl_waktu_deteksi.config(text=ts)

    def update_log(self, line, ts):
        self.events.append(f"[{ts}] {line}")
        for i, lbl in enumerate(self.log_labels):
            idx = len(self.events) - 3 + i
            if idx >= 0 and idx < len(self.events):
                lbl.config(text=list(self.events)[idx])
            else:
                lbl.config(text="")

    def set_left_panel_idle(self):
        self.lbl_ambient_title.config(text="Jarak Ambient")

    def update(self):
        try:
            line = get_line(self.ser)
            ts = datetime.now().strftime("%H:%M:%S")

            if line:
                state, jarak, sensor_error, menjauh_hitungan = parse_event(line)

                if sensor_error:
                    print(f"[TERMINAL] [{ts}] [SENSOR ERROR] {line}", flush=True)
                    self.lbl_status_bar.config(
                        text="Status: [X] SENSOR ERROR - periksa wiring HC-SR04", fg=self.FG_RED
                    )
                    self.lbl_ambient_val.config(text="ERR", fg=self.FG_RED)
                    self.lbl_status_icon.config(text="[X] ERROR", fg=self.FG_RED)
                    print(f"[STATUS] [{ts}] [X] SENSOR ERROR", flush=True)
                    self.update_log(line, ts)
                    self.win.after(100, self.update)
                    return

                # ─────────── LOCK (<= 30 cm) ───────────
                if state == "LOCK" and jarak is not None:
                    if self.state != "LOCK":
                        self.lock_start = time.time()
                        self.state = "LOCK"
                        self.lbl_ambient_title.config(text="Baseline")
                        self.lbl_status_icon.config(text="[O] LOCKED", fg=self.FG_GREEN)
                        self.lbl_status_bar.config(
                            text="Status: [O] Locked", fg=self.FG_GREEN
                        )
                        print(f"[STATUS] [{ts}] [O] LOCKED", flush=True)
                        print(f"[TERMINAL] [{ts}] [DETEKSI] LOCK | ADA objek terdeteksi | Jarak: {jarak} cm", flush=True)

                    self.obj_jarak = jarak
                    self.durasi_detik = int(time.time() - self.lock_start)
                    durasi_str = f"{self.durasi_detik // 60:02d}:{self.durasi_detik % 60:02d}"
                    self.set_right_lock(jarak, ts)
                    self.lbl_durasi.config(text=f"Durasi: {durasi_str}")

                    if self.baseline is not None:
                        delta = self.baseline - jarak
                        self.lbl_delta.config(
                            text=f"Delta: {delta:+.1f} cm", fg=self.FG_GREEN
                        )
                        print(f"[TERMINAL] [{ts}] [DETEKSI] LOCK | Durasi: {durasi_str} | Jarak: {jarak} cm | Delta: {delta:+.1f} cm", flush=True)

                # ─────────── MENDEKAT (30-50 cm) ───────────
                elif state == "MENDEKAT" and jarak is not None:
                    self.state = "MENDEKAT"
                    self.lbl_status_bar.config(
                        text="Status: [V] Object mendekat", fg=self.FG_YELLOW
                    )
                    self.lbl_status_icon.config(text="[V] MENDEKAT", fg=self.FG_YELLOW)
                    self.set_right_mendekat(jarak, ts)
                    print(f"[STATUS] [{ts}] [V] MENDEKAT", flush=True)
                    print(f"[TERMINAL] [{ts}] [DETEKSI] MENDEKAT | Ada objek mendekat | Jarak: {jarak} cm", flush=True)

                # ─────────── MENJAUH (> 30 cm, counting to UNLOCK) ───────────
                elif state == "MENJAUH" and jarak is not None:
                    if self.state in ("LOCK", "MENJAUH", "MENDEKAT"):
                        self.state = "MENJAUH"
                        self.lbl_status_bar.config(
                            text=f"Status: [^] Object menjauh ({menjauh_hitungan or '?'}/{MENJAUH_BATAS})", fg=self.FG_YELLOW
                        )
                        self.lbl_status_icon.config(text="[^] MENJAUH", fg=self.FG_YELLOW)
                        self.set_right_menjauh(jarak, menjauh_hitungan, ts)
                        print(f"[STATUS] [{ts}] [^] MENJAUH ({menjauh_hitungan or '?'}/{MENJAUH_BATAS})", flush=True)
                        print(f"[TERMINAL] [{ts}] [DETEKSI] MENJAUH | Jarak: {jarak} cm | Hitungan: {menjauh_hitungan or '?'}/{MENJAUH_BATAS}", flush=True)

                # ─────────── IDLE (> 50 cm, no object) ───────────
                elif state == "IDLE":
                    if self.state in ("LOCK", "MENJAUH", "MENDEKAT"):
                        self.state = "IDLE"
                        self.lbl_status_bar.config(
                            text="Status: [!] Unstable", fg=self.FG_YELLOW
                        )
                        self.lbl_status_icon.config(text="[!] UNSTABLE", fg=self.FG_YELLOW)
                        self.set_left_panel_idle()
                        self.set_right_reset()
                        self._reset_scheduled = True
                        print(f"[STATUS] [{ts}] [!] UNSTABLE", flush=True)
                        print(f"[TERMINAL] [{ts}] [DETEKSI] RESET | Objek hilang, loading 3 detik...", flush=True)
                        self.win.after(3000, self.reset_to_idle)

                    if jarak is not None:
                        if self.baseline is None:
                            self.baseline = jarak
                            print(f"[TERMINAL] [{ts}] [BASE] Baseline awal: {jarak} cm", flush=True)
                        self.lbl_ambient_val.config(text=f"{jarak} cm", fg=self.FG)
                        print(f"[TERMINAL] [{ts}] [BASE] Jarak ambient: {jarak} cm", flush=True)

                self.update_log(line, ts)

            self.dot_count += 1
            if self.state == "IDLE" and not self._reset_scheduled:
                dots = "." * (self.dot_count % 4)
                self.lbl_status_icon.config(text=f"(O) MEMANTAU{dots}")

        except serial.SerialException:
            ets = datetime.now().strftime('%H:%M:%S')
            print(f"[STATUS] [{ets}] [X] SERIAL ERROR - Koneksi putus", flush=True)
            print(f"[TERMINAL] [{ets}] [ERROR] Serial connection lost", flush=True)
            self.lbl_status_bar.config(text="Status: [X] Error - Koneksi putus", fg=self.FG_RED)
            self.lbl_lock_badge.config(text="[X] ERROR", fg=self.FG_RED)

        self.win.after(100, self.update)

    def reset_to_idle(self):
        self._reset_scheduled = False
        if self.state == "IDLE":
            self.baseline = None
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[STATUS] [{ts}] (O) STABLE", flush=True)
            print(f"[TERMINAL] [{ts}] [DETEKSI] IDLE | Reset selesai, kembali memantau", flush=True)
            self.set_right_idle()
            self.set_left_panel_idle()
            self.lbl_status_bar.config(
                text="Status: (O) Stable", fg=self.FG_GREEN
            )
            self.lbl_status_icon.config(text="(O) IDLE", fg=self.FG_BLUE)

    def on_close(self):
        if self.ser:
            self.ser.close()
        self.win.destroy()


def run_gui():
    import tkinter as tk

    ser = setup_hardware() if USE_REAL_HARDWARE else None
    win = tk.Tk()
    app = DistanceApp(win, ser)
    win.mainloop()


def main():
    log("INFO", "=== APP START ===")
    try:
        if USE_GUI:
            run_gui()
        else:
            run_terminal()
    except Exception as e:
        log("ERROR", f"Fatal: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
