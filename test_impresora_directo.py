import socket
import sys

IP = '192.168.0.58'
PORT = 9100

print(f'Conectando a {IP}:{PORT}...')
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect((IP, PORT))
    print('Conectado!')

    data = (
        b'\x1b\x40'  # ESC @ - reset
        b'\x1b\x74\x10'  # ESC t 0x10 - codepage CP1252
        b'TEST DESDE WINDOWS\n'
        b'Si ves esto funciona!\n'
        b'\n'
        b'\x1b\x64\x04'  # ESC d 4 - feed 4 lines
        b'\x1b\x69'  # ESC i - cut (partial)
    )
    n = s.send(data)
    print(f'Enviados {n} bytes OK')

    s.close()
    print('Conexion cerrada.')
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
