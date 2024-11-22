import serial
import time

ArduinoSerial = serial.Serial('COM3', 9600)
time.sleep(2)

# print(ArduinoSerial.readline())
print("Enter 1 to turn ON LED and 0 to turn OFF LED")

while True:
    ArduinoSerial.write(b'1')
