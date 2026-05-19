import logging
import platform
import subprocess

logger = logging.getLogger(__name__)

IP_IMPRESORA = '192.168.0.67'
PUERTO_IMPRESORA = 9100


class EscposBuffer:
    def __init__(self):
        from escpos.escpos import Escpos

        self._buf = bytearray()

        class _BufferPrinter(Escpos):
            def _raw(self_, msg):
                self._buf.extend(msg)

        self._printer = _BufferPrinter(magic_encode_args={'encoding': 'CP1252'})

    def set(self, **kwargs):
        self._printer.set(**kwargs)

    def text(self, txt):
        self._printer.text(txt)

    def qr(self, content, **kwargs):
        kwargs.setdefault('native', True)
        kwargs.setdefault('size', 6)
        kwargs.setdefault('ec', 0)
        self._printer.qr(content, **kwargs)

    def cut(self):
        self._printer.cut()

    def barcode(self, code, **kwargs):
        self._printer.barcode(code, **kwargs)

    def image(self, img_source, **kwargs):
        self._printer.image(img_source, **kwargs)

    def build(self):
        return bytes(self._buf)


def _enviar_tcp(data, ip=None, puerto=None, etiqueta=''):
    import socket
    ip = ip or IP_IMPRESORA
    puerto = puerto or PUERTO_IMPRESORA
    try:
        logger.warning(f'[_enviar_tcp{etiqueta}] conectando a {ip}:{puerto}, {len(data)} bytes...')
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((ip, puerto))
        n = sock.send(data)
        sock.close()
        logger.warning(f'[_enviar_tcp{etiqueta}] enviados {n} bytes OK')
        return True
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        logger.error(f'[_enviar_tcp{etiqueta}] ERROR: {e}')
        raise RuntimeError(f'Impresora no disponible: {e}')


def _is_wsl():
    return 'microsoft' in platform.uname().release.lower()


class LocalPrinterService:
    def __init__(self, ip=None, printer_name=None):
        self.ip = ip or IP_IMPRESORA
        self.printer_name = printer_name

    def check_connectivity(self, timeout=1):
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((self.ip, PUERTO_IMPRESORA))
            sock.close()
            return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    def _get_available_printers_windows(self):
        try:
            import win32print
            printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
            return printers
        except Exception:
            return []

    def _print_escpos(self, lineas, etiqueta=''):
        buf = EscposBuffer()
        buf._buf.extend(b'\x1b\x74\x10')
        buf.set(align='left', bold=False)
        logger.warning(f'[_print_escpos{etiqueta}] {len(lineas)} lineas')
        for linea in lineas:
            buf.text(linea.rstrip('\n') + '\n')
        buf._buf.extend(b'\x1b\x64\x04\x1b\x69')
        data = b'\x1b\x40' + buf.build()
        logger.warning(f'[_print_escpos{etiqueta}] buffer: {len(data)} bytes, primeras 3 lineas: {lineas[:3]}')
        _enviar_tcp(data, ip=self.ip, etiqueta=etiqueta)
        return f'POS-80C ({self.ip}:{PUERTO_IMPRESORA})'

    def _imprimir_html(self, pedido, categoria_nombre=None, etiqueta=None, sufijo=None):
        from .ticket_formatter import TicketFormatter
        formatter = TicketFormatter()
        lineas = formatter.formatear(pedido, categoria_nombre=categoria_nombre, etiqueta=etiqueta, sufijo=sufijo)
        logger.warning(f'[_imprimir_html #{pedido.id}] {len(lineas)} lineas generadas')
        if not lineas:
            logger.warning(f'[_imprimir_html #{pedido.id}] sin lineas, salteando')
            return None
        return self._print_escpos(lineas, '[TICKET]')

    def _categorias_en_pedido(self, pedido):
        return set(l.producto.categoria.nombre for l in pedido.lineas.all())

    def _imprimir_comanda(self, pedido, categoria_nombre, etiqueta, sufijo):
        from .ticket_formatter import TicketFormatter
        formatter = TicketFormatter()
        lineas = formatter.formatear_comanda(pedido, categoria_nombre, etiqueta, sufijo)
        logger.warning(f'[_imprimir_comanda {etiqueta} #{pedido.id}] {len(lineas)} lineas generadas')
        if not lineas:
            logger.warning(f'[_imprimir_comanda {etiqueta} #{pedido.id}] sin lineas, salteando')
            return None
        return self._print_escpos(lineas, f'[{etiqueta}]')

    def _pausa(self, segundos=0.5):
        import time
        time.sleep(segundos)

    def print_ticket(self, pedido):
        if not self.check_connectivity():
            raise RuntimeError(f'Impresora no disponible en {self.ip}')
        categorias = self._categorias_en_pedido(pedido)
        logger.warning(f'[print_ticket #{pedido.id}] categorias={categorias}, total_lineas={pedido.lineas.count()}')
        nombre = None

        n = self._imprimir_html(pedido)
        if n:
            nombre = n
        else:
            logger.warning(f'[print_ticket #{pedido.id}] _imprimir_html retorno None')

        self._pausa(0.5)

        if 'Comidas' in categorias:
            n = self._imprimir_comanda(pedido, 'Comidas', 'COMIDAS', 'C')
            if n:
                nombre = n
            else:
                logger.warning(f'[print_ticket #{pedido.id}] comanda Comidas retorno None')

        self._pausa(0.5)

        if 'Bebidas' in categorias:
            n = self._imprimir_comanda(pedido, 'Bebidas', 'BEBIDAS', 'B')
            if n:
                nombre = n
            else:
                logger.warning(f'[print_ticket #{pedido.id}] comanda Bebidas retorno None')

        if nombre:
            logger.warning(f'[print_ticket #{pedido.id}] todo enviado a: {nombre}')
        else:
            logger.warning(f'[print_ticket #{pedido.id}] NINGUN ticket se imprimio!')
        return nombre or 'desconocida'

    def _get_windows_printers_via_powershell(self):
        try:
            result = subprocess.run(
                ['powershell.exe', '-Command', 'Get-Printer | Select-Object -ExpandProperty Name'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                printers = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
                return printers
        except Exception:
            pass
        return []

    def list_printers(self):
        sistema = platform.system()
        is_wsl = _is_wsl()
        if sistema == 'Windows':
            return self._get_available_printers_windows()
        elif is_wsl:
            return self._get_windows_printers_via_powershell()
        else:
            resultado = subprocess.run(['lpstat', '-p'], capture_output=True, text=True)
            if resultado.returncode == 0:
                lineas = resultado.stdout.strip().split('\n')
                return [l.split()[1] for l in lineas if 'printer' in l]
            return []
