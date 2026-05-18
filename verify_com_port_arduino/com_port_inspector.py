import tkinter as tk
from tkinter import ttk
import serial.tools.list_ports
import serial
import threading
import time


def detect_board(port):
    if port.vid is not None and port.pid is not None:
        known = {
            (0x2341, 0x0043): "Arduino Uno R3",
            (0x2341, 0x0001): "Arduino Uno R3 (CDC)",
            (0x2341, 0x0010): "Arduino Mega",
            (0x1A86, 0x7523): "CH340 (clon Arduino)",
            (0x0403, 0x6001): "FT232 FTDI",
            (0x10C4, 0xEA60): "CP210x",
        }
        if (port.vid, port.pid) in known:
            return known[(port.vid, port.pid)]
    return None


def test_port(device):
    try:
        with serial.Serial(device, 9600, timeout=2) as ser:
            time.sleep(2.5)
            data = ser.read(ser.in_waiting or 100).decode("utf-8", errors="replace")
            ser.write(b"PING_ARDUINO\n")
            time.sleep(1)
            data2 = ser.read(ser.in_waiting or 100).decode("utf-8", errors="replace")
    except Exception as e:
        return "fail", str(e)[:60]

    combined = data + data2

    if "OK_ARDUINO_GATE_SENSOR" in combined:
        return "pass", "VALID ARDUINO (handshake OK)"
    if "ARDUINO READY" in combined or "JARAK:" in combined:
        return "pass", "VALID ARDUINO (data terdeteksi)"
    if combined.strip():
        return "fail", f"Data tidak dikenal: {combined.strip()[:60]}"
    return "fail", "Tidak ada respon"


class App:
    def __init__(self):
        self.win = tk.Tk()
        self.win.title("COM Port Inspector")
        self.win.geometry("800x400")

        top = ttk.Frame(self.win)
        top.pack(fill="x", padx=8, pady=4)
        ttk.Label(top, text="COM Port Inspector", font=("Consolas", 14, "bold")).pack(side="left")
        self.btn = ttk.Button(top, text="Test Semua Port", command=self.test_all)
        self.btn.pack(side="right")
        self.status_lbl = ttk.Label(top, text="Ready", font=("Consolas", 9))
        self.status_lbl.pack(side="right", padx=10)

        cols = ("Port", "Description", "Detected", "Status")
        self.tree = ttk.Treeview(self.win, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.column("Port", width=70)
        self.tree.column("Description", width=250)
        self.tree.column("Detected", width=180)
        self.tree.column("Status", width=250)
        self.tree.tag_configure("pass", background="#c3e6cb")
        self.tree.tag_configure("fail", background="#f5c6cb")
        self.tree.tag_configure("skip", background="#fff3cd")
        vsb = ttk.Scrollbar(self.win, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=4)
        vsb.pack(side="right", fill="y", padx=(0, 8), pady=4)

        self.conclusion = ttk.Label(self.win, text="", font=("Consolas", 10, "bold"), relief="sunken", anchor="w")
        self.conclusion.pack(fill="x", padx=8, pady=(0, 4))

        self.win.after(100, self.test_all)
        self.win.mainloop()

    def test_all(self):
        self.btn.configure(state="disabled")
        self.status_lbl.configure(text="Scanning...")
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.conclusion.configure(text="")
        self.win.update()
        threading.Thread(target=self._run_tests, daemon=True).start()

    def _run_tests(self):
        ports = serial.tools.list_ports.comports()

        for p in ports:
            detected = detect_board(p) or "-"
            self.win.after(0, lambda pp=p: self.status_lbl.configure(text=f"Testing {pp.device}..."))

            if detect_board(p):
                tag, status = test_port(p.device)
            else:
                tag, status = "skip", "Bukan kandidat"

            self.win.after(0, lambda pp=p, det=detected, st=status, tg=tag:
                self.tree.insert("", "end", values=(pp.device, pp.description, det, st), tags=(tg,)))

        self.win.after(0, lambda: self.status_lbl.configure(text="Selesai"))
        self.win.after(0, lambda: self.btn.configure(state="normal"))

        arduino_ports = []
        for row in self.tree.get_children():
            vals = self.tree.item(row)["values"]
            if "VALID" in str(vals[3]):
                arduino_ports.append(vals[0])

        self.win.after(0, lambda: self._show_conclusion(arduino_ports))

    def _show_conclusion(self, ports):
        if ports:
            msg = f"Kesimpulan: Arduino terdeteksi di {ports[0]}"
            if len(ports) > 1:
                msg += f" | Peringatan: {len(ports)} port lolos!"
            bg = "#c3e6cb"
        else:
            msg = "Kesimpulan: Tidak ada Arduino yang terdeteksi"
            bg = "#f5c6cb"
        self.conclusion.configure(text=f"  {msg}", background=bg)


if __name__ == "__main__":
    App()
