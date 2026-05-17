import sys
import time
import serial
import serial.tools.list_ports

print("=" * 60)
print("DIAGNOSTIC SERIAL - Test Komunikasi Arduino + HC-SR04")
print("=" * 60)

ports = list(serial.tools.list_ports.comports())
print(f"\nPort terdeteksi ({len(ports)}):")
for p in ports:
    print(f"  {p.device}: {p.description}")

target_port = None
for p in ports:
    if "CH340" in p.description or "Arduino" in p.description or "USB" in p.description:
        target_port = p.device
        print(f"\n-> Port target: {p.device} ({p.description})")
        break

if not target_port:
    print("\nTidak ada port Arduino/CH340 ditemukan!")
    sys.exit(1)

print(f"\nMembuka {target_port} @ 9600 baud...")
try:
    ser = serial.Serial(target_port, 9600, timeout=0.5)
    ser.dtr = False
    time.sleep(0.3)
    ser.dtr = True
    time.sleep(0.5)
    ser.reset_input_buffer()
    print(f"  Status: open={ser.is_open}")
except Exception as e:
    print(f"  GAGAL: {e}")
    sys.exit(1)

print("\n=== Test 1: Baca startup message ===")
for _ in range(10):
    raw = ser.readline()
    if raw:
        decoded = raw.decode("utf-8", errors="replace").strip()
        print(f"  {decoded}")
    else:
        break

print("\n=== Test 2: Baca data 10 detik ===")
print("  (gerakkan tangan di depan sensor untuk test)")
start = time.time()
count = 0
while time.time() - start < 10:
    try:
        raw = ser.readline()
        if raw:
            count += 1
            decoded = raw.decode("utf-8", errors="replace").strip()
            print(f"  [{count}] {decoded}")
    except Exception as e:
        print(f"  Error: {e}")

if count == 0:
    print("  TIDAK ADA DATA - Arduino tidak mengirim")

print(f"\n  Total baris: {count}")

print("\n=== Test 3: Cek jarak 0.00 ===")
if count > 0:
    print("  Jika semua baris menunjukkan Jarak: 0.00 cm,")
    print("  maka HC-SR04 TIDAK TERBACA oleh Arduino.")
    print("  Penyebab:")
    print("  1. Kabel jumper longgar atau salah pin")
    print("  2. Sensor tidak mendapat daya (VCC harus 5V)")
    print("  3. Sensor rusak")
else:
    print("  Tidak ada data untuk dianalisa")

ser.close()
print("\n" + "=" * 60)
print("DIAGNOSTIC SELESAI")
print("=" * 60)
