import logging
import platform
import subprocess
import tempfile
import os

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
        self.printer_name = (printer_name or '').strip() or None

    def _is_local_printer_mode(self):
        return bool(self.printer_name)

    def _send_raw_to_windows_printer(self, data):
        try:
            import win32print
        except Exception as e:
            raise RuntimeError(f'No se pudo cargar win32print: {e}')

        printer = self.printer_name or win32print.GetDefaultPrinter()
        if not printer:
            raise RuntimeError('No hay impresora predeterminada en Windows.')

        try:
            handle = win32print.OpenPrinter(printer)
            try:
                win32print.StartDocPrinter(handle, 1, ('PDV Ticket', None, 'RAW'))
                win32print.StartPagePrinter(handle)
                win32print.WritePrinter(handle, data)
                win32print.EndPagePrinter(handle)
                win32print.EndDocPrinter(handle)
            finally:
                win32print.ClosePrinter(handle)
        except Exception as e:
            raise RuntimeError(f'Error enviando a impresora Windows "{printer}": {e}')

        return printer

    def _send_text_to_windows_printer(self, text_data):
        try:
            import win32print
        except Exception as e:
            raise RuntimeError(f'No se pudo cargar win32print: {e}')

        printer = self.printer_name or win32print.GetDefaultPrinter()
        if not printer:
            raise RuntimeError('No hay impresora predeterminada en Windows.')

        last_error = None
        for datatype in ('TEXT', 'RAW', None):
            try:
                handle = win32print.OpenPrinter(printer)
                try:
                    win32print.StartDocPrinter(handle, 1, ('PDV Ticket', None, datatype))
                    win32print.StartPagePrinter(handle)
                    win32print.WritePrinter(handle, text_data)
                    win32print.EndPagePrinter(handle)
                    win32print.EndDocPrinter(handle)
                finally:
                    win32print.ClosePrinter(handle)
                return printer
            except Exception as e:
                last_error = e
                logger.warning(f'[_send_text_to_windows_printer] fallo datatype={datatype}: {e}')

        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(prefix='pdv_ticket_', suffix='.txt')
            with os.fdopen(fd, 'wb') as f:
                f.write(text_data)
            result = subprocess.run(
                ['notepad.exe', '/pt', tmp_path, printer],
                capture_output=True,
                timeout=20,
            )
            if result.returncode == 0:
                logger.warning(f'[_send_text_to_windows_printer] fallback notepad OK en {printer}')
                return printer
            detalle = (result.stderr or result.stdout).decode(errors='ignore').strip()
            raise RuntimeError(detalle or 'fallo notepad /pt')
        except Exception as e:
            raise RuntimeError(
                f'Error enviando texto a impresora Windows "{printer}": {last_error}; '
                f'fallback notepad fallo: {e}'
            )
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _send_raw_to_linux_printer(self, data):
        cmd = ['lp']
        if self.printer_name:
            cmd.extend(['-d', self.printer_name])
        cmd.extend(['-o', 'raw', '-t', 'PDV Ticket'])
        try:
            result = subprocess.run(cmd, input=data, capture_output=True, timeout=10)
        except FileNotFoundError:
            raise RuntimeError('No se encontro el comando lp (CUPS).')
        except Exception as e:
            raise RuntimeError(f'Error enviando a CUPS: {e}')
        if result.returncode != 0:
            detalle = (result.stderr or result.stdout).decode(errors='ignore').strip()
            raise RuntimeError(f'Error enviando a impresora Linux: {detalle or "desconocido"}')
        return self.printer_name or 'default (CUPS)'

    def _send_text_to_linux_printer(self, text_data):
        cmd = ['lp']
        if self.printer_name:
            cmd.extend(['-d', self.printer_name])
        cmd.extend(['-t', 'PDV Ticket'])
        try:
            result = subprocess.run(cmd, input=text_data, capture_output=True, timeout=10)
        except FileNotFoundError:
            raise RuntimeError('No se encontro el comando lp (CUPS).')
        except Exception as e:
            raise RuntimeError(f'Error enviando texto a CUPS: {e}')
        if result.returncode != 0:
            detalle = (result.stderr or result.stdout).decode(errors='ignore').strip()
            raise RuntimeError(f'Error enviando a impresora Linux: {detalle or "desconocido"}')
        return self.printer_name or 'default (CUPS)'

    def _looks_like_escpos_printer(self):
        if not self.printer_name:
            return True
        name = self.printer_name.lower()
        escpos_hints = ['tm-', 'epson tm', 'pos', 'thermal', 'ticket', '80mm', '58mm', 'xp-', 'impter']
        return any(h in name for h in escpos_hints)

    def _build_text_ticket_data(self, lineas):
        text = '\r\n'.join(linea.rstrip('\n') for linea in lineas) + '\r\n\r\n'
        return text.encode('cp1252', errors='replace')

    def _send_text_data(self, text_data, etiqueta=''):
        sistema = platform.system()
        if _is_wsl():
            raise RuntimeError('Impresion por texto no soportada en WSL. Ejecuta el servidor en Windows.')
        if sistema == 'Windows':
            destino = self._send_text_to_windows_printer(text_data)
            logger.warning(f'[_send_text_data{etiqueta}] enviado texto a impresora Windows: {destino}')
            return destino
        destino = self._send_text_to_linux_printer(text_data)
        logger.warning(f'[_send_text_data{etiqueta}] enviado texto a impresora Linux: {destino}')
        return destino

    def _send_raw_data(self, data, etiqueta=''):
        sistema = platform.system()
        if self._is_local_printer_mode():
            if _is_wsl():
                raise RuntimeError('Impresion por nombre no soportada en WSL. Usa servidor en Windows o IP de impresora de red.')
            if sistema == 'Windows':
                destino = self._send_raw_to_windows_printer(data)
                logger.warning(f'[_send_raw_data{etiqueta}] enviado a impresora Windows: {destino}')
                return destino
            destino = self._send_raw_to_linux_printer(data)
            logger.warning(f'[_send_raw_data{etiqueta}] enviado a impresora Linux: {destino}')
            return destino

        _enviar_tcp(data, ip=self.ip, etiqueta=etiqueta)
        return f'POS-80C ({self.ip}:{PUERTO_IMPRESORA})'

    def check_connectivity(self, timeout=1):
        if self._is_local_printer_mode():
            disponibles = self.list_printers() or []
            for p in disponibles:
                if p.lower() == self.printer_name.lower():
                    self.printer_name = p
                    return True
            for p in disponibles:
                if self.printer_name.lower() in p.lower() or p.lower() in self.printer_name.lower():
                    self.printer_name = p
                    return True
            return False

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
        logger.warning(f'[_print_escpos{etiqueta}] printer_name={self.printer_name}')

        if self._is_local_printer_mode():
            try:
                disponibles = self.list_printers() or []
            except Exception as e:
                logger.warning(f'[_print_escpos{etiqueta}] error list_printers: {e}')
                disponibles = []

            matched = None
            for p in disponibles:
                if p.lower() == (self.printer_name or '').lower():
                    matched = p
                    break
            if not matched:
                for p in disponibles:
                    if (self.printer_name or '').lower() in p.lower() or p.lower() in (self.printer_name or '').lower():
                        matched = p
                        break

            if matched:
                self.printer_name = matched
                text_data = self._build_text_ticket_data(lineas)
                logger.warning(f'[_print_escpos{etiqueta}] impresora sistema encontrada, usando spool de texto: {self.printer_name}')
                return self._send_text_data(text_data, etiqueta=etiqueta)

            if not self._looks_like_escpos_printer():
                text_data = self._build_text_ticket_data(lineas)
                logger.warning(f'[_print_escpos{etiqueta}] impresora no ESC/POS detectada por nombre, usando spool de texto')
                return self._send_text_data(text_data, etiqueta=etiqueta)

        buf = EscposBuffer()
        buf._buf.extend(b'\x1b\x74\x10')
        buf.set(align='left', bold=False)
        logger.warning(f'[_print_escpos{etiqueta}] {len(lineas)} lineas')
        for linea in lineas:
            buf.text(linea.rstrip('\n') + '\n')
        buf._buf.extend(b'\x1b\x64\x04\x1b\x69')
        data = b'\x1b\x40' + buf.build()
        logger.warning(f'[_print_escpos{etiqueta}] buffer: {len(data)} bytes, primeras 3 lineas: {lineas[:3]}')
        destino = self._send_raw_data(data, etiqueta=etiqueta)
        return destino

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
            if self._is_local_printer_mode():
                raise RuntimeError(f'Impresora local no disponible: {self.printer_name}')
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
            try:
                resultado = subprocess.run(['lpstat', '-p'], capture_output=True, text=True, timeout=10)
            except Exception:
                return []
            if resultado.returncode == 0:
                lineas = resultado.stdout.strip().split('\n')
                return [l.split()[1] for l in lineas if 'printer' in l]
            return []
