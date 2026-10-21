import argparse
import os
import socket
import subprocess
import sys


def discover_local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def is_valid_ipv4(value):
    parts = value.split('.')
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def can_bind(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # En Windows SO_REUSEADDR deja bindear un puerto que otro proceso ya escucha
    # (asi corrieron dos servidores en el 8080); SO_EXCLUSIVEADDRUSE lo impide.
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    else:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def find_listening_pid(port):
    """PID que escucha en el puerto (via netstat), o None si no se pudo determinar."""
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        cols = line.split()
        if len(cols) >= 5 and cols[3].upper() == "LISTENING" and cols[1].endswith(f":{port}"):
            return cols[4]
    return None


def main():
    parser = argparse.ArgumentParser(description="Servidor local PDV para red ethernet")
    parser.add_argument("--host", default=os.getenv("PDV_SERVER_BIND", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PDV_SERVER_PORT", "8000")))
    parser.add_argument("--threads", type=int, default=int(os.getenv("PDV_SERVER_THREADS", "8")))
    args = parser.parse_args()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ibat_pdv_eventos.settings")

    fixed_ip = os.getenv("PDV_SERVER_IP", "").strip()
    if not fixed_ip or not is_valid_ipv4(fixed_ip):
        fixed_ip = discover_local_ip()
        os.environ["PDV_SERVER_IP"] = fixed_ip

    # El puerto no cambia solo: las cajas apuntan a uno fijo y un cambio silencioso las deja sin servidor.
    selected_port = args.port
    if not can_bind(args.host, selected_port):
        pid = find_listening_pid(selected_port)
        quien = f"por el PID {pid}" if pid else "por otro proceso (PID no determinado)"
        print(f"[ERROR] El puerto {selected_port} esta ocupado {quien} - cerra ese proceso y volve a iniciar.")
        sys.exit(1)

    print("============================================")
    print(" PDV Eventos - Servidor local")
    print("============================================")
    print(f" Bind: {args.host}:{selected_port}")
    print(f" Frontend/API: http://{fixed_ip}:{selected_port}")
    print("============================================")

    try:
        import logging
        from django.conf import settings
        from django.core.wsgi import get_wsgi_application
        from waitress import serve

        application = get_wsgi_application()
        logging.getLogger("pdv_servidor").info(
            "Arranque: bind=%s puerto=%s threads=%s DEBUG=%s PID=%s",
            args.host, selected_port, args.threads, settings.DEBUG, os.getpid(),
        )
        serve(application, host=args.host, port=selected_port, threads=args.threads)
    except ModuleNotFoundError as exc:
        if exc.name == "waitress":
            print("[WARN] waitress no esta instalado. Se usara runserver.")
            from django.core.management import execute_from_command_line

            execute_from_command_line(["manage.py", "runserver", f"{args.host}:{selected_port}"])
        else:
            raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nServidor detenido por usuario")
        sys.exit(0)
