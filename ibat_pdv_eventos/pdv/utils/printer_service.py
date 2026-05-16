import logging

logger = logging.getLogger(__name__)


class PrinterService:
    def __init__(self, ip, puerto=9100, timeout=5):
        self.ip = ip
        self.puerto = puerto
        self.timeout = timeout

    def _check_connectivity(self):
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.ip, self.puerto))
            sock.close()
            return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    def print_ticket(self, lineas):
        if not self._check_connectivity():
            logger.warning(f"Impresora {self.ip}:{self.puerto} no disponible")
            return False
        try:
            from escpos.printer import Network
            printer = Network(self.ip, self.puerto)
            printer.set(align='left', bold=False)
            for linea in lineas:
                printer.text(linea + '\n')
            printer.cut()
            printer.close()
            logger.info(f"Ticket impreso correctamente en {self.ip}:{self.puerto}")
            return True
        except Exception as e:
            logger.error(f"Error al imprimir en {self.ip}:{self.puerto}: {e}")
            return False
