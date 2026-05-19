import logging
import os
import platform
import subprocess
import tempfile

logger = logging.getLogger(__name__)

IP_IMPRESORA = '192.168.0.58'
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


def _enviar_tcp(data, etiqueta=''):
    import socket
    try:
        logger.warning(f'[_enviar_tcp{etiqueta}] conectando a {IP_IMPRESORA}:{PUERTO_IMPRESORA}, {len(data)} bytes...')
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((IP_IMPRESORA, PUERTO_IMPRESORA))
        n = sock.send(data)
        sock.close()
        logger.warning(f'[_enviar_tcp{etiqueta}] enviados {n} bytes OK')
        return True
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        logger.error(f'[_enviar_tcp{etiqueta}] ERROR: {e}')
        raise RuntimeError(f'Impresora no disponible: {e}')


def _is_wsl():
    return 'microsoft' in platform.uname().release.lower()


def _generate_ticket_html(pedido, categoria_nombre=None, etiqueta=None, sufijo=None, simple=False):
    evento = pedido.punto_venta.evento.nombre if hasattr(pedido.punto_venta, 'evento') else ''
    pdv = pedido.punto_venta.nombre
    fecha = pedido.creado.strftime('%d/%m/%Y %H:%M') if pedido.creado else ''
    ticket_id = f"#{pedido.id}-{sufijo}" if sufijo else f"#{pedido.id}"
    etiqueta_html = f'<div style="text-align:center;font-size:14px;font-weight:bold;margin:4px 0">--- {etiqueta} ---</div>' if etiqueta else ''

    if simple:
        lineas_html = ''
        for l in pedido.lineas.all():
            if categoria_nombre and l.producto.categoria.nombre != categoria_nombre:
                continue
            nota = f'<br><span style="font-size:12px;color:#666">({l.nota})</span>' if l.nota else ''
            lineas_html += f'<div style="padding:4px 0;font-size:14px">{l.cantidad}x {l.producto.nombre}{nota}</div>'

        if not lineas_html.strip():
            return None

        return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body {{ font-family: Arial, Helvetica, sans-serif; font-size: 14px; width: 80mm; margin: 0 auto; padding: 10px; }}
    .hdr {{ text-align: center; font-weight: bold; font-size: 16px; margin: 0 0 2px; }}
    .sub {{ text-align: center; font-weight: bold; font-size: 18px; margin: 0 0 4px; }}
    .event {{ text-align: center; font-size: 15px; font-weight: bold; margin: 4px 0 6px; }}
    .info {{ font-size: 13px; margin-bottom: 8px; }}
</style>
</head>
<body>
    <div class="hdr">CENTRO DE ESTUDIANTES</div>
    <div class="sub">IBAT San Jose</div>
    <div class="event">Pena IBAT 2026</div>
    {etiqueta_html}
    <div class="info">
        PDV: {pdv} | {ticket_id}<br>
        {fecha}
    </div>
    {lineas_html}
</body>
</html>'''

    lineas_html = ''
    subtotal_cat = 0
    impuestos_cat = 0
    for l in pedido.lineas.all():
        if categoria_nombre and l.producto.categoria.nombre != categoria_nombre:
            continue
        total = l.cantidad * float(l.precio_unitario)
        subtotal_cat += total
        tasa = float(l.producto.tasa_impuesto)
        impuestos_cat += total * tasa / 100
        nota = f'<br><span style="font-size:12px;color:#666">({l.nota})</span>' if l.nota else ''
        lineas_html += f'''
            <tr>
                <td style="padding:4px 0;font-size:14px">{l.cantidad}x {l.producto.nombre}{nota}</td>
                <td style="padding:4px 0;font-size:14px;text-align:right">${total:.2f}</td>
            </tr>'''

    if not lineas_html.strip():
        return None

    pagos_html = ''
    for p in pedido.pagos.all():
        extra = ''
        if p.metodo == 'EF' and p.monto_recibido:
            vuelto = float(p.monto_recibido) - float(p.monto)
            extra = f'<br><span style="font-size:12px;color:#666">Recibido: ${float(p.monto_recibido):.2f} | Vuelto: ${vuelto:.2f}</span>'
        pagos_html += f'''
            <tr>
                <td style="padding:4px 0;font-size:14px">{p.get_metodo_display()}{extra}</td>
                <td style="padding:4px 0;font-size:14px;text-align:right">${float(p.monto):.2f}</td>
            </tr>'''

    total_cat = subtotal_cat + impuestos_cat
    total_str = f'${total_cat:.2f}' if categoria_nombre else f'${float(pedido.total_final):.2f}'

    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body {{ font-family: Arial, Helvetica, sans-serif; font-size: 14px; width: 80mm; margin: 0 auto; padding: 10px; }}
    .hdr {{ text-align: center; font-weight: bold; font-size: 16px; margin: 0 0 2px; }}
    .sub {{ text-align: center; font-weight: bold; font-size: 18px; margin: 0 0 4px; }}
    .event {{ text-align: center; font-size: 15px; font-weight: bold; margin: 4px 0 6px; }}
    .info {{ font-size: 13px; margin-bottom: 8px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    td {{ padding: 4px 0; font-size: 14px; }}
    .sep {{ border-top: 1px dashed #000; }}
    .total {{ font-weight: bold; font-size: 18px; }}
    .total td {{ padding: 6px 0; }}
    .center {{ text-align: center; }}
    .foot {{ text-align: center; font-size: 13px; margin-top: 8px; }}
    .brand {{ text-align: center; font-size: 11px; color: #555; margin-top: 2px; }}
</style>
</head>
<body>
    <div class="hdr">CENTRO DE ESTUDIANTES</div>
    <div class="sub">IBAT San Jose</div>
    <div class="event">Pena IBAT 2026</div>
    {etiqueta_html}
    <div class="info">
        PDV: {pdv} | {ticket_id}<br>
        {fecha}
    </div>
    <table>
        <tr><td class="sep" colspan="2"></td></tr>
        {lineas_html}
        <tr><td class="sep" colspan="2"></td></tr>
    </table>
    <table>
        <tr class="total"><td>TOTAL</td><td style="text-align:right">{total_str}</td></tr>
        <tr><td class="sep" colspan="2"></td></tr>
        {pagos_html}
        <tr><td class="sep" colspan="2"></td></tr>
    </table>
    <br>
    <div class="foot">Gracias por su compra</div>
    <div class="brand">created by RaizDigital</div>
</body>
</html>'''


class LocalPrinterService:
    def __init__(self, printer_name=None):
        self.printer_name = printer_name

    def _get_available_printers_windows(self):
        try:
            import win32print
            printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
            return printers
        except Exception:
            return []

    def _get_default_printer_windows(self):
        try:
            import win32print
            return win32print.GetDefaultPrinter()
        except Exception:
            return None

    def _print_windows(self, lineas):
        nombre = self.printer_name or self._get_default_printer_windows()
        if not nombre:
            printers = self._get_available_printers_windows()
            if not printers:
                raise RuntimeError('No hay impresoras disponibles en Windows')
            nombre = printers[0]

        import win32ui
        import win32print

        dc = win32ui.CreateDC()
        dc.CreatePrinterDC(nombre)

        page_width = dc.GetDeviceCaps(110)
        page_height = dc.GetDeviceCaps(111)
        ml = int(page_width * 0.04)
        ancho_util = page_width - ml * 2
        alto_fuente = int(ancho_util / 48 * 1.5)

        font = win32ui.CreateFont({'name': 'Consolas', 'height': -alto_fuente, 'weight': 700})

        dc.SelectObject(font)
        leading = int(dc.GetTextExtent('X')[1] * 1.25)

        dc.StartDoc('Ticket PDV')
        dc.StartPage()

        y = int(page_height * 0.03)

        for linea in lineas:
            if not linea.strip():
                y += leading // 3
                continue

            dc.SelectObject(font)
            dc.TextOut(ml, y, linea)
            y += leading

            if y > page_height - int(page_height * 0.06):
                dc.EndPage()
                dc.StartPage()
                y = int(page_height * 0.03)

        dc.EndPage()
        dc.EndDoc()
        return nombre

    def _print_linux(self, html):
        import subprocess
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html)
            tmpname = f.name
        try:
            cmd = ['lp']
            if self.printer_name:
                cmd.extend(['-d', self.printer_name])
            cmd.extend(['-o', 'media=80x150mm'])
            cmd.append(tmpname)
            resultado = subprocess.run(cmd, capture_output=True, text=True)
            if resultado.returncode != 0:
                raise RuntimeError(f'Error lp: {resultado.stderr}')
            return self.printer_name or 'default'
        finally:
            try:
                os.unlink(tmpname)
            except Exception:
                pass

    def _print_text_via_powershell(self, lineas, printer_name):
        try:
            import socket
            ip = '192.168.0.58'
            puerto = 9100
            texto = '\r\n'.join(lineas) + '\r\n'
            escpos_data = b'\x1b\x40' + texto.encode('cp1252', errors='replace') + b'\x1b\x64\x02\x1b\x69'
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, puerto))
            sock.send(escpos_data)
            sock.close()
            return f'POS-80C ({ip}:{puerto})'
        except Exception as e:
            raise RuntimeError(f'Error imprimiendo por TCP: {e}')

    def _print_escpos(self, lineas, etiqueta=''):
        buf = EscposBuffer()
        buf._buf.extend(b'\x1b\x74\x10')
        buf.set(align='left', bold=False)
        logger.warning(f'[_print_escpos{etiqueta}] {len(lineas)} lineas')
        for i, linea in enumerate(lineas):
            t = linea.rstrip('\n')
            buf.text(t + '\n')
        buf._buf.extend(b'\x1b\x64\x04\x1b\x69')
        data = b'\x1b\x40' + buf.build()
        logger.warning(f'[_print_escpos{etiqueta}] buffer: {len(data)} bytes, primeras 3 lineas: {lineas[:3]}')
        _enviar_tcp(data, etiqueta)
        return f'POS-80C ({IP_IMPRESORA}:{PUERTO_IMPRESORA})'

    def _print_windows_via_powershell(self, html, printer_name):
        try:
            import uuid
            import subprocess as sub
            result = sub.run(
                ['cmd.exe', '/c', 'echo', '%TEMP%'],
                capture_output=True
            )
            win_temp = result.stdout.decode('cp1252', errors='replace').strip()
            tmpname = f'{win_temp}\\ticket_{uuid.uuid4().hex}.html'
            tmpname_wsl = tmpname.replace('C:\\', '/mnt/c/').replace('\\', '/')
            with open(tmpname_wsl, 'w', encoding='cp1252', errors='replace') as f:
                f.write(html)
            ps_cmd = (
                f'$printer = "{printer_name or ""}"; '
                'if (-not $printer) { $printers = Get-Printer; if ($printers) { $printer = $printers[0].Name } }; '
                'if ($printer) { '
                f'Start-Process -FilePath "msedge.exe" -ArgumentList @("--headless", "--disable-gpu", "--print-to-printer=""$printer""", "file:///{tmpname}") -WindowStyle Hidden -Wait '
                '} else { Write-Error "No printer found" }'
            )
            result = sub.run(['powershell.exe', '-NoProfile', '-Command', ps_cmd], capture_output=True, timeout=60)
            if result.returncode != 0:
                err = result.stderr.decode('cp1252', errors='replace').strip() or result.stdout.decode('cp1252', errors='replace').strip()
                raise RuntimeError(f'PowerShell error: {err}')
            return printer_name or 'default'
        except Exception as e:
            raise RuntimeError(f'Error imprimiendo desde WSL: {e}')

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
        categorias = self._categorias_en_pedido(pedido)
        logger.warning(f'[print_ticket #{pedido.id}] categorias={categorias}, total_lineas={pedido.lineas.count()}')
        nombre = None

        n = self._imprimir_html(pedido)
        if n: nombre = n
        else: logger.warning(f'[print_ticket #{pedido.id}] _imprimir_html retorno None')

        self._pausa(0.5)

        if 'Comidas' in categorias:
            n = self._imprimir_comanda(pedido, 'Comidas', 'COMIDAS', 'C')
            if n: nombre = n
            else: logger.warning(f'[print_ticket #{pedido.id}] comanda Comidas retorno None')

        self._pausa(0.5)

        if 'Bebidas' in categorias:
            n = self._imprimir_comanda(pedido, 'Bebidas', 'BEBIDAS', 'B')
            if n: nombre = n
            else: logger.warning(f'[print_ticket #{pedido.id}] comanda Bebidas retorno None')

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
