# arduino.py
import serial

arduino_connected = False
ser = None

def connect_arduino(port='COM3', baudrate=9600, timeout=1):
    global ser, arduino_connected
    try:
        ser = serial.Serial(port, baudrate, timeout=timeout)
        arduino_connected = True
    except serial.SerialException:
        arduino_connected = False
    return arduino_connected

def read_arduino():
    global ser
    if ser and ser.in_waiting > 0:
        return ser.readline().decode().strip()
    return None

def close_arduino():
    global ser
    if ser:
        ser.close()
        ser = None
        return True
    return False
