# Pengukur Jarak Digital — HC-SR04 + Arduino + Python

Sistem pengukuran jarak ultrasonic dengan state machine (IDLE → MENDEKAT → LOCK → MENJAUH → UNLOCK), Tkinter GUI, dan library Python yang bisa diimport aplikasi lain.

## Hardware

- Arduino Uno (CH340)
- HC-SR04 Ultrasonic Sensor
- Breadboard + kabel jumper

### Wiring HC-SR04

| HC-SR04 | Arduino |
|---------|---------|
| VCC | 5V |
| GND | GND |
| Trig | Pin 9 |
| Echo | Pin 10 |

## File Structure

```
D:\Github\sc_python_ultrasonic/
├── distance_monitor.py          # Aplikasi utama (GUI + terminal)
├── test_hardware_gui.py         # Test GUI untuk library (real hardware)
├── diagnostic_serial.py         # Diagnostik serial COM6
├── requirements.txt             # Dependencies
├── ultrasonic_distance/
│   └── ultrasonic_distance.ino  # Firmware Arduino (kirim raw jarak)
├── versi_library/
│   └── __init__.py              # Library (class UltrasonicSensor)
└── README.md
```

## Cara Pakai

### 1. Upload Firmware

```powershell
& "C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" compile --fqbn arduino:avr:uno "D:\Github\sc_python_ultrasonic\ultrasonic_distance"
& "C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" upload --fqbn arduino:avr:uno --port COM6 "D:\Github\sc_python_ultrasonic\ultrasonic_distance"
```

### 2a. Jalankan Aplikasi Utama (GUI)

```powershell
python distance_monitor.py
```

### 2b. Jalankan Aplikasi Utama (Terminal)

Edit `USE_GUI = False` di `distance_monitor.py`.

### 3. Test Library dengan GUI

```powershell
python test_hardware_gui.py
```

## Library — `versi_library`

Bisa diimport aplikasi Python lain.

```python
from versi_library import UltrasonicSensor

# Default thresholds: jarak_lock=20, jarak_mendekat=40
sensor = UltrasonicSensor(use_real_hardware=True)

# Custom thresholds
sensor = UltrasonicSensor(jarak_lock=70, jarak_mendekat=100)

# Callback state change
def on_change(old, new, data):
    print(f"{old} -> {new}, jarak={data['jarak']}")

sensor.on_state_change = on_change
sensor.start()

# Properties
print(sensor.state)        # IDLE / MENDEKAT / LOCK / MENJAUH
print(sensor.jarak)        # float (cm)
print(sensor.baseline)     # float (cm)
print(sensor.delta)        # baseline - jarak
print(sensor.durasi_detik) # durasi dalam LOCK
print(sensor.menjauh_hitungan) # countdown MENJAUH
print(sensor.sensor_error) # boolean

sensor.stop()
```

### Parameter Constructor `UltrasonicSensor(**kwargs)`

| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `port` | `None` (auto-detect) | Port serial (contoh: `"COM6"`) |
| `baud` | `9600` | Baud rate |
| `jarak_lock` | `20.0` | Jarak ≤ ini → LOCK (cm) |
| `jarak_mendekat` | `40.0` | Jarak antara LOCK dan ini → MENDEKAT (cm) |
| `heartbeat_detik` | `1` | Interval pembacaan sensor (detik) |
| `mendekat_batas` | `2` | Jumlah pembacaan berturut-turut untuk MENDEKAT |
| `menjauh_batas` | `5` | Jumlah pembacaan berturut-turut untuk UNLOCK |
| `use_real_hardware` | `True` | `True` = hardware, `False` = simulasi |

## State Machine

```
                    ┌──────────────────────────────────┐
                    │           IDLE (>100 cm)          │
                    │    (Baseline captured on first    │
                    │     valid IDLE reading)           │
                    └────────┬─────────────┬────────────┘
                             │             │
                    jarak ≤ 70│             │jarak > 100 (reset)
                             │             │
                    ┌────────▼─────┐  ┌────▼──────────┐
                    │   MENDEKAT   │  │ MENJAUH (1-4) │
                    │  (70-100 cm) │  │  (>70 cm)     │
                    └────────┬─────┘  └────┬──────────┘
                             │             │
                    jarak ≤ 70│             │ hitungan ≥ 5
                             │             │
                    ┌────────▼─────┐  ┌────▼──────────┐
                    │     LOCK     │  │    UNLOCK      │
                    │    (≤70 cm)  │──►   (IDLE)       │
                    │  Delta aktif │  └────────────────┘
                    └──────────────┘
```

### Threshold Default Aplikasi Utama

| Threshold | Nilai | State |
|-----------|-------|-------|
| 0-70 cm | `JARAK_LOCK` | **LOCK** |
| 70-100 cm | `JARAK_MENDEKAT` | **MENDEKAT** |
| >100 cm | — | **IDLE** |

## Firmware — `ultrasonic_distance.ino`

Firmware hanya mengirim **raw jarak** setiap 1 detik. Tidak ada state machine di Arduino — semua logika ada di Python.

| Kondisi | Output Serial |
|---------|--------------|
| Sensor membaca jarak | `JARAK: 114.5 cm` |
| `pulseIn` timeout (>4m) | `JARAK: -1.0 cm` |

## Catatan

- Firmware tidak perlu diubah untuk menyesuaikan threshold — cukup edit di Python.
- Library default `jarak_lock=20, jarak_mendekat=40`. Aplikasi utama pakai `70, 100`.
- `-1.0 cm` = sensor tidak mendeteksi objek (jarak >4m) — tidak dianggap error.
- Chip CH340 (clone Arduino Uno) otomatis terdeteksi di COM6.
