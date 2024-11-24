import subprocess
import os


def upload_to_board(port):
    sketch_path = os.path.abspath(os.curdir) + "\\temp\\temp.ino" # Use double backslashes in Windows paths
    print(sketch_path)
    fqbn = 'Rudiron:MDR32F9Qx:buterbrodR916'


    print("Compiling the sketch...")
    compile_command = ['arduino-cli', 'compile', '--fqbn', fqbn, sketch_path]
    compile_process = subprocess.run(
        compile_command, capture_output=True, text=True, encoding='utf-8'
    )

    if compile_process.returncode != 0:
        print("Compilation failed:")
        print(compile_process.stderr)
        exit(1)
    else:
        print("Compilation successful.")

    print("Uploading the sketch...")
    upload_command = [
        'arduino-cli', 'upload', '-p', port, '--fqbn', fqbn, '--verbose', sketch_path
    ]
    upload_process = subprocess.run(
        upload_command, capture_output=True, text=True, encoding='utf-8'
    )

    if upload_process.returncode != 0:
        print("Upload failed:")
        print(upload_process.stderr)
        return 0
    else:
        print("Upload successful.")
        return 1


import serial
import time


def reset_arduino(port, baudrate=9600, reset_time=2):
    """
    Перезапуск Arduino через последовательный порт.

    :param port: COM-порт, к которому подключена Arduino (например, "COM3").
    :param baudrate: Скорость порта (по умолчанию 9600).
    :param reset_time: Время задержки для завершения перезапуска (в секундах).
    """
    try:
        # Открываем последовательный порт
        with serial.Serial(port, baudrate, timeout=1) as ser:
            # Программный сброс через DTR
            ser.dtr = False
            time.sleep(10)  # Небольшая задержка
            ser.dtr = True
            time.sleep(reset_time)  # Время на перезапуск Arduino
            print(f"Arduino на порту {port} успешно перезагружена.")
    except serial.SerialException as e:
        print(f"Ошибка работы с последовательным портом: {e}")


if __name__ == "__main__":
    reset_arduino("COM3")
    upload_to_board("COM3")



# arduino-cli compile --fqbn Rudiron:MDR32F9Qx:buterbrodR916 "C:\\Users\\PC\\Documents\\Arduino\\sketch_nov23a\\sketch_nov23a.ino"
# arduino-cli upload -p COM3 --fqbn Rudiron:MDR32F9Qx:buterbrodR916 --verbose "C:\Users\PC\Documents\Arduino\sketch_nov23a"