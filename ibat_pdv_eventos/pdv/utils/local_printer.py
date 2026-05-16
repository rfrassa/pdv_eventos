import logging
import os
import platform
import subprocess
import tempfile

logger = logging.getLogger(__name__)


def _is_wsl():
    return 'microsoft' in platform.uname().release.lower()

CAT_COMIDA = 'Comidas'
CAT_BEBIDA = 'Bebidas'


def _generate_ticket_html(pedido, categoria_nombre=None, etiqueta=None, sufijo=None):
    evento = pedido.punto_venta.evento.nombre if hasattr(pedido.punto_venta, 'evento') else ''
    pdv = pedido.punto_venta.nombre
    fecha = pedido.creado.strftime('%d/%m/%Y %H:%M') if pedido.creado else ''
    ticket_id = f"#{pedido.id}-{sufijo}" if sufijo else f"#{pedido.id}"

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

    etiqueta_html = f'<div style="text-align:center;font-size:14px;font-weight:bold;margin:4px 0">--- {etiqueta} ---</div>' if etiqueta else ''

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
    <div class="sub">IBAT San Jos&eacute;</div>
    <div class="event">Pe&ntilde;a IBAT 2026</div>
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
    <div class="brand">created by Ra&iacute;zDigital&reg;</div>
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

    def _print_windows_via_powershell(self, html, printer_name):
        try:
            import uuid
            tmpname = os.path.join(tempfile.gettempdir(), f'ticket_{uuid.uuid4().hex}.html')
            with open(tmpname, 'w', encoding='utf-8') as f:
                f.write(html)
            ps_cmd = f'''
$printer = "{printer_name or ""}";
if (-not $printer) {{ $printers = Get-Printer; if ($printers) {{ $printer = $printers[0].Name }} }}
if ($printer) {{ Start-Process -FilePath "msedge.exe" -ArgumentList "--print-to-printer=""$printer""",""--print""",""{tmpname}"" -WindowStyle Hidden -Wait }}
else {{ Write-Error "No printer found" }}
'''
            subprocess.run(['powershell.exe', '-Command', ps_cmd], capture_output=True, text=True, timeout=30)
            return printer_name or 'default'
        except Exception as e:
            raise RuntimeError(f'Error imprimiendo desde WSL: {e}')

    def _categorias_en_pedido(self, pedido):
        return set(l.producto.categoria.nombre for l in pedido.lineas.all())

    def _imprimir_html(self, pedido, categoria_nombre=None, etiqueta=None, sufijo=None):
        sistema = platform.system()
        is_wsl = _is_wsl()
        if sistema == 'Windows':
            from .ticket_formatter import TicketFormatter
            formatter = TicketFormatter()
            lineas = formatter.formatear(pedido, categoria_nombre=categoria_nombre, etiqueta=etiqueta, sufijo=sufijo)
            return self._print_windows(lineas)
        elif is_wsl:
            html = _generate_ticket_html(pedido, categoria_nombre=categoria_nombre, etiqueta=etiqueta, sufijo=sufijo)
            if html is None:
                return None
            return self._print_windows_via_powershell(html, self.printer_name)
        else:
            html = _generate_ticket_html(pedido, categoria_nombre=categoria_nombre, etiqueta=etiqueta, sufijo=sufijo)
            if html is None:
                return None
            return self._print_linux(html)

    def print_ticket(self, pedido):
        categorias = self._categorias_en_pedido(pedido)
        nombre = None

        if CAT_COMIDA in categorias and CAT_BEBIDA in categorias:
            for cat, etiqueta, suf in [(CAT_BEBIDA, 'BEBIDAS', 'B'), (CAT_COMIDA, 'COMIDAS', 'C')]:
                n = self._imprimir_html(pedido, categoria_nombre=cat, etiqueta=etiqueta, sufijo=suf)
                if n:
                    nombre = n
        else:
            nombre = self._imprimir_html(pedido)

        if nombre:
            logger.info(f'Ticket #{pedido.id} enviado a impresora: {nombre}')
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
