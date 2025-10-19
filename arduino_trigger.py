import serial
import subprocess
import time
import serial.tools.list_ports

SERIAL_PORT = "COM7"         # 👈 Make sure this matches your Arduino port
BAUD_RATE = 9600

def get_serial_port():
    ports = list(serial.tools.list_ports.comports())

    while True:
        for i, p in enumerate(ports):
            print(f'  [{i}] {p.device} - {p.description}')

        idx = int(input('\nPlease select the trigger device: '))
        if 0 <= idx < len(ports):
            return ports[idx].device

def start_trigger():
    SERIAL_PORT = get_serial_port()
    print(f"Connecting to {SERIAL_PORT}...")

    while True:
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)  # Wait for Arduino to reset
            print("Ready. Waiting for START signal...")

            while True:
                if ser.in_waiting:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    print(f"[Arduino → Python]: {line}")

                    if line == "START":
                        print("START received. Running executer.py...")
                        # result = subprocess.run(["python", "executer.py"])
                        import executer
                        executer.main()
                        # print("executer.py finished with return code:", result.returncode)

                        ser.write(b"DONE\n")
                        print("DONE sent back to Arduino.\nWaiting for next START...")

        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")

        except KeyboardInterrupt:
            print("Exiting.")

# import serial
# import serial.tools.list_ports

# import time
# import executer
# BAUD_RATE = 9600


# def get_serial_port():
#     ports = list(serial.tools.list_ports.comports())

#     while True:
#         for i, p in enumerate(ports):
#             print(f'  [{i}] {p.device} - {p.description}')

#         idx = int(input('\nPlease select the trigger device: '))
#         if 0 <= idx < len(ports):
#             return ports[idx].device

# def main():
#     print('Starting serial')
#     SERIAL_PORT = get_serial_port()
#     print('Connected to device')
#     while True:
#         try:
#             ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
#             time.sleep(2)  # Wait for Arduino to reset
#             print("Connected. Waiting for START signal...")

#             while True:
#                 if ser.in_waiting:
#                     line = ser.readline().decode('utf-8', errors='ignore').strip()
#                     print(f"[Arduino → Python]: {line}")

#                     if line == "START":
#                         print("START received. Running executer.py...")
#                         executer.main()
#                         # result = subprocess.run(["python", "executer.py"])
#                         # print("executer.py finished with return code:", result.returncode)

#                         ser.write(b"DONE\n")
#                         print("DONE sent back to Arduino.\nWaiting for next START...")

#         except serial.SerialException as e:
#             print(f"Error opening serial port: {e}")

#         except KeyboardInterrupt:
#             print("Exiting.")

# if __name__ == '__main__':
#     main()
