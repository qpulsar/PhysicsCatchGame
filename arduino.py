# arduino.py
import serial
import serial.tools.list_ports
import time

arduino_connected = False
ser = None

def get_available_ports():
    """Returns a list of available serial ports."""
    return [port.device for port in serial.tools.list_ports.comports()]

def connect_arduino(port='COM3', baudrate=9600, timeout=0.1):
    global ser, arduino_connected
    try:
        if ser:
            ser.close()
        ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2) # Give Arduino time to reset
        arduino_connected = True
    except Exception:
        arduino_connected = False
    return arduino_connected

def read_arduino():
    global ser
    if ser and ser.is_open:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                return line
        except Exception:
            pass
    return None

def send_command(command):
    """Sends a command string to the Arduino."""
    global ser, arduino_connected
    if ser and ser.is_open:
        try:
            ser.write(f"{command}\n".encode('utf-8'))
            return True
        except Exception:
            arduino_connected = False
    return False

def close_arduino():
    global ser, arduino_connected
    if ser:
        try:
            ser.close()
        except:
            pass
        ser = None
        arduino_connected = False
        return True
    return False
