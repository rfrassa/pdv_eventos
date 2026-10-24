"""Exportación del resumen de ventas a XLSX.

No calcula nada: recibe el dict de views.resumen_ventas(con_pedidos=True), que es
la misma fuente de la pantalla y de la versión imprimible.
"""
from io import BytesIO

from django.utils.text import slugify
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import Pago

FORMATO_PESOS = '"$"#,##0.00'
ENCABEZADO = PatternFill('solid', fgColor='1F3864')


def periodo_texto(resumen):
    if resumen['desde'] and resumen['hasta']:
        return f"{resumen['desde']} a {resumen['hasta']}"
    if resumen['desde']:
        return f"desde {resumen['desde']}"
    if resumen['hasta']:
        return f"hasta {resumen['hasta']}"
    return 'Todo el período'


def nombre_archivo(resumen, extension):
    partes = ['ventas', slugify(resumen['evento']) or 'evento']
    if resumen['desde'] or resumen['hasta']:
        partes += [resumen['desde'] or 'inicio', resumen['hasta'] or 'hoy']
    return '_'.join(partes) + '.' + extension


def _encabezado(ws, fila, columnas):
    for i, titulo in enumerate(columnas, start=1):
        c = ws.cell(row=fila, column=i, value=titulo)
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = ENCABEZADO
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)


def _ajustar_columnas(ws, minimo=10, maximo=45):
    for col in ws.columns:
        ancho = max((len(str(c.value)) for c in col if c.value is not None), default=0)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(ancho + 2, minimo), maximo)


def _hoja_resumen(ws, r):
    ws['A1'] = 'Resumen de ventas'
    ws['A1'].font = Font(bold=True, size=14)
    datos = [
        ('Evento', r['evento']),
        ('Período (hora de Argentina)', periodo_texto(r)),
        ('Total vendido', r['total_general']),
        ('Pedidos cobrados', r['total_pedidos']),
        ('Ticket promedio', r['ticket_promedio']),
        ('Unidades vendidas', r['unidades_total']),
        ('Impuestos', r['total_impuestos']),
    ]
    for i, (etiqueta, valor) in enumerate(datos, start=3):
        ws.cell(row=i, column=1, value=etiqueta).font = Font(bold=True)
        c = ws.cell(row=i, column=2, value=valor)
        if etiqueta in ('Total vendido', 'Ticket promedio', 'Impuestos'):
            c.number_format = FORMATO_PESOS
        c.alignment = Alignment(horizontal='left')

    fila = 3 + len(datos) + 1
    ws.cell(row=fila, column=1, value='Por método de pago').font = Font(bold=True, size=12)
    _encabezado(ws, fila + 1, ['Método', 'Total'])
    fila += 2
    for m in r['total_por_metodo']:
        ws.cell(row=fila, column=1, value=m['metodo_display'])
        ws.cell(row=fila, column=2, value=m['total']).number_format = FORMATO_PESOS
        fila += 1

    fila += 1
    ws.cell(row=fila, column=1, value='Ventas por franja de 15 minutos').font = Font(bold=True, size=12)
    _encabezado(ws, fila + 1, ['Franja (inicio)', 'Pedidos', 'Total'])
    fila += 2
    for f in r['por_franja']:
        ws.cell(row=fila, column=1, value=f['franja'])
        ws.cell(row=fila, column=2, value=f['pedidos'])
        ws.cell(row=fila, column=3, value=f['total']).number_format = FORMATO_PESOS
        fila += 1
    _ajustar_columnas(ws, minimo=14)


def _hoja_productos(ws, r):
    _encabezado(ws, 1, ['Producto', 'Unidades', 'Importe'])
    for fila, p in enumerate(r['por_producto'], start=2):
        ws.cell(row=fila, column=1, value=p['nombre'])
        ws.cell(row=fila, column=2, value=p['unidades'])
        ws.cell(row=fila, column=3, value=p['importe']).number_format = FORMATO_PESOS
    total = len(r['por_producto']) + 2
    ws.cell(row=total, column=1, value='TOTAL').font = Font(bold=True)
    ws.cell(row=total, column=2, value=r['unidades_total']).font = Font(bold=True)
    c = ws.cell(row=total, column=3, value=round(sum(p['importe'] for p in r['por_producto']), 2))
    c.font = Font(bold=True)
    c.number_format = FORMATO_PESOS
    ws.freeze_panes = 'A2'
    _ajustar_columnas(ws)


def _hoja_cajas(ws, r):
    metodos = [(cod, nombre) for cod, nombre in Pago.METODOS
               if any(cod in c['por_metodo'] for c in r['por_caja'])]
    _encabezado(ws, 1, ['Caja', 'Pedidos', 'Total'] + [nombre for _, nombre in metodos])
    for fila, c in enumerate(r['por_caja'], start=2):
        ws.cell(row=fila, column=1, value=c['nombre'])
        ws.cell(row=fila, column=2, value=c['pedidos'])
        ws.cell(row=fila, column=3, value=c['total']).number_format = FORMATO_PESOS
        for j, (cod, _) in enumerate(metodos, start=4):
            ws.cell(row=fila, column=j, value=c['por_metodo'].get(cod, 0)).number_format = FORMATO_PESOS
    total = len(r['por_caja']) + 2
    ws.cell(row=total, column=1, value='TOTAL').font = Font(bold=True)
    ws.cell(row=total, column=2, value=sum(c['pedidos'] for c in r['por_caja'])).font = Font(bold=True)
    celda = ws.cell(row=total, column=3, value=round(sum(c['total'] for c in r['por_caja']), 2))
    celda.font = Font(bold=True)
    celda.number_format = FORMATO_PESOS
    for j, (cod, _) in enumerate(metodos, start=4):
        celda = ws.cell(row=total, column=j, value=round(sum(c['por_metodo'].get(cod, 0) for c in r['por_caja']), 2))
        celda.font = Font(bold=True)
        celda.number_format = FORMATO_PESOS
    ws.freeze_panes = 'A2'
    _ajustar_columnas(ws, minimo=14)


def _hoja_pedidos(ws, r):
    _encabezado(ws, 1, ['Nº pedido', 'Fecha y hora', 'Evento', 'Caja', 'Subtotal', 'Impuestos', 'Total', 'Pagos'])
    for fila, p in enumerate(r['pedidos'], start=2):
        ws.cell(row=fila, column=1, value=p['id'])
        ws.cell(row=fila, column=2, value=p['creado']).number_format = 'dd/mm/yyyy hh:mm:ss'
        ws.cell(row=fila, column=3, value=p['evento'])
        ws.cell(row=fila, column=4, value=p['caja'])
        for j, clave in ((5, 'subtotal'), (6, 'impuestos'), (7, 'total')):
            ws.cell(row=fila, column=j, value=p[clave]).number_format = FORMATO_PESOS
        ws.cell(row=fila, column=8, value=p['pagos'])
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    _ajustar_columnas(ws)


def resumen_a_xlsx(resumen):
    """Devuelve los bytes de un .xlsx con Resumen, Por producto, Por caja y método de pago, Pedidos."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Resumen'
    _hoja_resumen(ws, resumen)
    _hoja_productos(wb.create_sheet('Por producto'), resumen)
    _hoja_cajas(wb.create_sheet('Por caja y método de pago'), resumen)
    _hoja_pedidos(wb.create_sheet('Pedidos'), resumen)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
