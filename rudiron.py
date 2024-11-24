import subprocess
import os

sketch_path = os.path.abspath(os.curdir) + "\\temp\\temp.ino" # Use double backslashes in Windows paths
print(sketch_path)
fqbn = 'Rudiron:MDR32F9Qx:buterbrodR916'


port = 'COM3'

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
    exit(1)
else:
    print("Upload successful.")



# arduino-cli compile --fqbn Rudiron:MDR32F9Qx:buterbrodR916 "C:\\Users\\PC\\Documents\\Arduino\\sketch_nov23a\\sketch_nov23a.ino"
# arduino-cli upload -p COM3 --fqbn Rudiron:MDR32F9Qx:buterbrodR916 --verbose "C:\Users\PC\Documents\Arduino\sketch_nov23a"