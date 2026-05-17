import random
import threading
import time
from datetime import datetime

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


def parse_event(line):
    jarak = None
    sensor_error = "ERROR" in line and "HC-SR04" in line
    menjauh_hitungan = None

    # Format baru: "JARAK: 114.5 cm" or "JARAK: -1.0 cm" (out of range)
    if "JARAK:" in line and "cm" in line:
        jarak = float(line.replace("JARAK:", "").replace("cm", "").strip())
        if jarak == 0.0:
            jarak = -1.0
        return "JARAK", jarak, sensor_error, menjauh_hitungan

    # Format lama (backward compat)
    if "ERROR" in line:
        sensor_error = True
    if "Jarak:" in line:
        jarak = float(line.split("Jarak:")[-1].replace("cm", "").strip())
        if "Hitungan:" in line:
            try:
                menjauh_hitungan = int(line.split("Hitungan:")[-1].split("/")[0].strip())
            except ValueError:
                pass

    if "UNLOCK" in line:
        return "IDLE", jarak, sensor_error, menjauh_hitungan
    if "LOCK" in line:
        return "LOCK", jarak, sensor_error, menjauh_hitungan
    if "MENDEKAT" in line:
        return "MENDEKAT", jarak, sensor_error, menjauh_hitungan
    if "MENJAUH" in line:
        return "MENJAUH", jarak, sensor_error, menjauh_hitungan
    if "IDLE" in line:
        return "IDLE", jarak, sensor_error, menjauh_hitungan

    if jarak == 0.0:
        jarak = -1.0
    return "IDLE", jarak, sensor_error, menjauh_hitungan


class UltrasonicSensor:
    def __init__(self, **kwargs):
        self.config = {
            "port": kwargs.get("port", None),
            "baud": kwargs.get("baud", 9600),
            "jarak_lock": kwargs.get("jarak_lock", 20.0),
            "jarak_mendekat": kwargs.get("jarak_mendekat", 40.0),
            "heartbeat_detik": kwargs.get("heartbeat_detik", 1),
            "mendekat_batas": kwargs.get("mendekat_batas", 2),
            "menjauh_batas": kwargs.get("menjauh_batas", 5),
            "use_real_hardware": kwargs.get("use_real_hardware", True),
        }
        J = self.config["jarak_lock"]
        M = self.config["jarak_mendekat"]
        self.config["jarak_menjauh"] = kwargs.get("jarak_menjauh", J)
        self.config["jarak_reset"] = kwargs.get("jarak_reset", M)

        self._state = "IDLE"
        self._jarak = None
        self._baseline = None
        self._durasi_detik = 0
        self._menjauh_hitungan = 0
        self._mendekat_count = 0
        self._sensor_error = False
        self._lock_start = None
        self._running = False
        self._thread = None
        self._ser = None

        self._sim_state = "IDLE"
        self._sim_last_report = 0.0
        self._sim_count = 0

        self._state_lock = threading.Lock()
        self._on_state_change = None

    @property
    def state(self):
        with self._state_lock:
            return self._state

    @property
    def jarak(self):
        with self._state_lock:
            return self._jarak

    @property
    def baseline(self):
        with self._state_lock:
            return self._baseline

    @property
    def delta(self):
        with self._state_lock:
            if self._baseline is not None and self._jarak is not None:
                return round(self._baseline - self._jarak, 1)
            return None

    @property
    def durasi_detik(self):
        with self._state_lock:
            return self._durasi_detik

    @property
    def menjauh_hitungan(self):
        with self._state_lock:
            return self._menjauh_hitungan

    @property
    def sensor_error(self):
        with self._state_lock:
            return self._sensor_error

    @property
    def on_state_change(self):
        return self._on_state_change

    @on_state_change.setter
    def on_state_change(self, func):
        self._on_state_change = func

    def _set_state(self, **updates):
        old = None
        with self._state_lock:
            old = self._state
            for k, v in updates.items():
                setattr(self, f"_{k}", v)
            new = self._state
        if old != new and self._on_state_change:
            data = {
                "state": new,
                "jarak": self.jarak,
                "baseline": self.baseline,
                "delta": self.delta,
                "durasi_detik": self.durasi_detik,
                "menjauh_hitungan": self.menjauh_hitungan,
                "sensor_error": self.sensor_error,
            }
            self._on_state_change(old, new, data)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass

    def _setup_hardware(self):
        if not HAS_SERIAL:
            raise RuntimeError("pyserial not installed. Run: pip install pyserial")

        cfg = self.config
        port = cfg["port"]
        if not port:
            ports = list(serial.tools.list_ports.comports())
            for p in ports:
                if "CH340" in p.description or "Arduino" in p.description or "USB" in p.description:
                    port = p.device
                    break
        if not port:
            raise RuntimeError("Arduino tidak ditemukan. Periksa koneksi USB.")

        ser = serial.Serial(port, cfg["baud"], timeout=0.5)
        ser.dtr = False
        time.sleep(0.3)
        ser.dtr = True
        time.sleep(2.0)
        ser.reset_input_buffer()
        ser.timeout = 0.1
        for _ in range(8):
            try:
                raw = ser.readline()
                if raw:
                    raw.decode("utf-8").strip()
            except UnicodeDecodeError:
                continue
        return ser

    def _simulate_reading(self):
        S = self.config["heartbeat_detik"]
        JL = self.config["jarak_lock"]
        JM = self.config["jarak_mendekat"]
        DB = self.config["mendekat_batas"]
        JB = self.config["menjauh_batas"]

        raw = random.uniform(2, 400)
        jarak = round(raw, 1)
        now = time.time()

        if (now - self._sim_last_report) < S:
            return None
        self._sim_last_report = now

        if jarak >= 2 and jarak <= JL:
            self._sim_count = 0
            just_entered = self._sim_state != "LOCK"
            self._sim_state = "LOCK"
            if just_entered:
                return f"JARAK: {jarak} cm"
            return f"JARAK: {jarak} cm"

        if jarak > JL and jarak <= JM:
            if self._sim_state in ("LOCK", "MENJAUH"):
                pass
            else:
                self._sim_count += 1
                if self._sim_count >= DB:
                    self._sim_state = "MENDEKAT"
                else:
                    self._sim_state = "IDLE"
                return f"JARAK: {jarak} cm"

        if self._sim_state in ("LOCK", "MENJAUH"):
            self._sim_count += 1
            if self._sim_count >= JB:
                self._sim_state = "IDLE"
                self._sim_count = 0
            else:
                self._sim_state = "MENJAUH"
            return f"JARAK: {jarak} cm"

        self._sim_state = "IDLE"
        self._sim_count = 0
        return f"JARAK: {jarak} cm"

    def _get_line(self):
        if not self.config["use_real_hardware"]:
            line = self._simulate_reading()
            time.sleep(0.3)
            return line

        if not self._ser:
            return None
        try:
            raw = self._ser.readline()
            line = raw.decode("utf-8").strip()
            return line if line else None
        except UnicodeDecodeError:
            return None
        except serial.SerialException:
            self._running = False
            return None

    def _process_line(self, line):
        ts = datetime.now().strftime("%H:%M:%S")
        msg_state, jarak, sensor_error, menjauh_hitungan = parse_event(line)

        if sensor_error:
            self._set_state(state="ERROR", jarak=None, sensor_error=True)
            return

        if jarak is None or jarak <= 0:
            return

        self._sensor_error = False
        JL = self.config["jarak_lock"]
        JM = self.config["jarak_mendekat"]
        DB = self.config["mendekat_batas"]
        JB = self.config["menjauh_batas"]

        if jarak >= 2 and jarak <= JL:
            self._mendekat_count = 0
            if self._state != "LOCK":
                if self._baseline is None:
                    self._baseline = jarak
                self._menjauh_hitungan = 0
                self._lock_start = time.time()
                self._set_state(state="LOCK", jarak=jarak, durasi_detik=0, menjauh_hitungan=0)
            else:
                self._set_state(jarak=jarak)
                if self._lock_start:
                    self._set_state(durasi_detik=int(time.time() - self._lock_start))

        elif self._state in ("LOCK", "MENJAUH"):
            self._mendekat_count = 0
            menjauh = self._menjauh_hitungan + 1
            if menjauh >= JB:
                self._menjauh_hitungan = 0
                self._set_state(state="IDLE", jarak=jarak, durasi_detik=0, menjauh_hitungan=0)
            else:
                self._menjauh_hitungan = menjauh
                self._set_state(state="MENJAUH", jarak=jarak, menjauh_hitungan=menjauh)

        elif jarak > JL and jarak <= JM:
            self._mendekat_count += 1
            if self._mendekat_count >= DB:
                self._mendekat_count = 0
                self._menjauh_hitungan = 0
                self._set_state(state="MENDEKAT", jarak=jarak, menjauh_hitungan=0)
            else:
                self._set_state(state="IDLE", jarak=jarak)

        else:
            self._mendekat_count = 0
            if self._baseline is None:
                self._baseline = jarak
            self._set_state(state="IDLE", jarak=jarak)

    def _run(self):
        try:
            if self.config["use_real_hardware"]:
                self._ser = self._setup_hardware()
        except RuntimeError as e:
            print(f"[SENSOR ERROR] {e}", flush=True)
            self._running = False
            return

        while self._running:
            line = self._get_line()
            if line:
                self._process_line(line)
            time.sleep(0.1)


def scan_port():
    if not HAS_SERIAL:
        return []
    import serial.tools.list_ports
    result = []
    for p in serial.tools.list_ports.comports():
        result.append((p.device, p.description))
    return result
