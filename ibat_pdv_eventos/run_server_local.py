import argparse
import os
import socket
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
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def pick_port(host, requested_port):
    candidates = [requested_port, 8080, 8010, 8888, 9000]
    seen = set()
    ordered = []
    for p in candidates:
        if p not in seen:
            seen.add(p)
            ordered.append(p)

    for port in ordered:
        if can_bind(host, port):
            return port, ordered
    return None, ordered


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

    selected_port, tried_ports = pick_port(args.host, args.port)
    if selected_port is None:
        print("[ERROR] No se encontro un puerto disponible.")
        print(f"        Puertos probados: {', '.join(str(p) for p in tried_ports)}")
        sys.exit(1)

    if selected_port != args.port:
        print(f"[WARN] Puerto {args.port} no disponible. Se usara {selected_port}.")

    print("============================================")
    print(" PDV Eventos - Servidor local")
    print("============================================")
    print(f" Bind: {args.host}:{selected_port}")
    print(f" Frontend/API: http://{fixed_ip}:{selected_port}")
    print("============================================")

    try:
        from django.core.wsgi import get_wsgi_application
        from waitress import serve

        application = get_wsgi_application()
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
