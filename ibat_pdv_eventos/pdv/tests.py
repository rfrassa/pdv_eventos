from datetime import date, datetime, timezone as dtz
from decimal import Decimal
from io import BytesIO

from django.test import TestCase
from openpyxl import load_workbook
from rest_framework.test import APIClient

from .models import Categoria, Evento, LineaPedido, Pago, Pedido, Producto, PuntoVenta
from .views import resumen_ventas


def utc(*args):
    return datetime(*args, tzinfo=dtz.utc)


class DatosVentas(TestCase):
    """Base sin tests: dos eventos, dos cajas y dos productos."""

    @classmethod
    def setUpTestData(cls):
        cls.junio = Evento.objects.create(nombre='Peña 2026', fecha=date(2026, 6, 12), activo=False)
        cls.expo = Evento.objects.create(nombre='Expo 2026', fecha=date(2026, 10, 22), activo=True)
        # La caja se usó en junio y después se pasó a la Expo (como en producción).
        cls.caja = PuntoVenta.objects.create(nombre='Caja 1', evento=cls.expo)
        cls.caja2 = PuntoVenta.objects.create(nombre='Caja 2', evento=cls.expo)
        cat = Categoria.objects.create(nombre='Comidas', evento=cls.expo)
        cls.choripan = Producto.objects.create(nombre='Choripán', precio=Decimal('1000'), categoria=cat, evento=cls.expo)
        cls.agua = Producto.objects.create(nombre='Agua', precio=Decimal('500'), categoria=cat, evento=cls.expo)

    def pedido(self, evento, creado, cantidad=1, producto=None, metodo='EF', cerrado=True, caja=None):
        producto = producto or self.choripan
        total = producto.precio * cantidad
        p = Pedido.objects.create(
            punto_venta=caja or self.caja, evento=evento, cerrado=cerrado,
            subtotal=total, total_final=total,
        )
        Pedido.objects.filter(id=p.id).update(creado=creado)  # auto_now_add
        LineaPedido.objects.create(pedido=p, producto=producto, cantidad=cantidad, precio_unitario=producto.precio)
        if cerrado:
            Pago.objects.create(pedido=p, metodo=metodo, monto=total)
        return p


class ResumenVentasTests(DatosVentas):
    """El resumen es el número que se le informa al colegio: cada evento por separado,
    solo pedidos cobrados y fechas en hora de Argentina (UTC-3)."""

    def test_cada_evento_por_separado_y_sin_pedidos_sin_cobrar(self):
        self.pedido(self.junio, utc(2026, 6, 12, 15, 0), cantidad=2)            # 2.000
        self.pedido(self.junio, utc(2026, 6, 12, 16, 0), producto=self.agua)    # 500
        self.pedido(self.expo, utc(2026, 10, 23, 0, 30), cantidad=3)            # 3.000
        self.pedido(self.expo, utc(2026, 10, 23, 0, 40), cerrado=False)         # abierto: no cuenta

        r_junio = resumen_ventas(self.junio)
        r_expo = resumen_ventas(self.expo)

        self.assertEqual((r_junio['total_pedidos'], r_junio['total_general']), (2, 2500))
        self.assertEqual((r_expo['total_pedidos'], r_expo['total_general']), (1, 3000))
        self.assertEqual(r_junio['ticket_promedio'], 1250)
        self.assertEqual(r_junio['unidades_total'], 3)
        self.assertEqual([(p['nombre'], p['unidades'], p['importe']) for p in r_junio['por_producto']],
                         [('Choripán', 2, 2000), ('Agua', 1, 500)])
        self.assertEqual(r_expo['total_por_metodo'][0]['total'], 3000)

    def test_todos_los_eventos(self):
        self.pedido(self.junio, utc(2026, 6, 12, 15, 0))
        self.pedido(self.expo, utc(2026, 10, 23, 0, 30))
        r = resumen_ventas(None)
        self.assertEqual((r['evento'], r['total_pedidos'], r['total_general']), ('Todos los eventos', 2, 2000))

    def test_se_cuenta_por_el_evento_del_pedido_no_por_el_de_la_caja(self):
        # self.caja hoy pertenece a la Expo, pero este pedido es de junio.
        self.pedido(self.junio, utc(2026, 6, 12, 15, 0))
        self.assertEqual(resumen_ventas(self.junio)['total_pedidos'], 1)
        self.assertEqual(resumen_ventas(self.expo)['total_pedidos'], 0)

    def test_rango_de_fechas_en_hora_de_argentina(self):
        antes_de_medianoche = self.pedido(self.junio, utc(2026, 6, 13, 2, 30))   # 12/06 23:30 ART
        despues_de_medianoche = self.pedido(self.junio, utc(2026, 6, 13, 3, 30))  # 13/06 00:30 ART

        dia12 = resumen_ventas(self.junio, desde=date(2026, 6, 12), hasta=date(2026, 6, 12))
        dia13 = resumen_ventas(self.junio, desde=date(2026, 6, 13), hasta=date(2026, 6, 13))
        self.assertEqual(dia12['total_pedidos'], 1)
        self.assertEqual(dia13['total_pedidos'], 1)
        self.assertEqual(resumen_ventas(self.junio, desde=date(2026, 6, 12), hasta=date(2026, 6, 13))['total_pedidos'], 2)
        self.assertEqual(resumen_ventas(self.junio, desde=date(2026, 6, 13))['total_pedidos'], 1)
        self.assertEqual(resumen_ventas(self.junio, hasta=date(2026, 6, 12))['total_pedidos'], 1)
        self.assertIsNotNone(antes_de_medianoche.id)
        self.assertIsNotNone(despues_de_medianoche.id)

    def test_franjas_de_15_minutos_en_hora_local(self):
        self.pedido(self.junio, utc(2026, 6, 12, 13, 7))    # 10:07 ART
        self.pedido(self.junio, utc(2026, 6, 12, 13, 14))   # 10:14 ART
        self.pedido(self.junio, utc(2026, 6, 12, 13, 15))   # 10:15 ART
        franjas = resumen_ventas(self.junio)['por_franja']
        self.assertEqual([(f['franja'], f['pedidos'], f['total']) for f in franjas],
                         [('12/06 10:00', 2, 2000), ('12/06 10:15', 1, 1000)])

    def test_por_caja_y_metodo(self):
        self.pedido(self.expo, utc(2026, 10, 23, 0, 30), metodo='EF')
        self.pedido(self.expo, utc(2026, 10, 23, 0, 31), metodo='TR', caja=self.caja2)
        cajas = {c['nombre']: c for c in resumen_ventas(self.expo)['por_caja']}
        self.assertEqual(cajas['Caja 1']['por_metodo'], {'EF': 1000})
        self.assertEqual(cajas['Caja 2']['por_metodo'], {'TR': 1000})
        self.assertEqual(sum(c['total'] for c in cajas.values()), 2000)


class TableroEndpointsTests(DatosVentas):
    """Las tres salidas (JSON, XLSX, HTML) salen del mismo cálculo."""

    def setUp(self):
        self.client = APIClient()
        self.pedido(self.junio, utc(2026, 6, 12, 15, 0), cantidad=1500)   # 1.500.000
        self.pedido(self.expo, utc(2026, 10, 23, 0, 30), cantidad=3)
        self.pedido(self.expo, utc(2026, 10, 23, 0, 40), cerrado=False)

    def test_por_defecto_es_el_evento_activo(self):
        data = self.client.get('/api/resumen-ventas/').json()
        self.assertEqual((data['evento_id'], data['total_pedidos'], data['total_general']), (self.expo.id, 1, 3000))

    def test_evento_explicito_y_todos(self):
        data = self.client.get('/api/resumen-ventas/', {'evento': self.junio.id}).json()
        self.assertEqual(data['total_general'], 1500000)
        data = self.client.get('/api/resumen-ventas/', {'evento': 'todos'}).json()
        self.assertEqual((data['total_pedidos'], data['total_general']), (2, 1503000))

    def test_parametros_invalidos_dan_400(self):
        for params in ({'desde': '23-10-2026'}, {'evento': 'abc'}, {'punto_venta_id': 'x'},
                       {'desde': '2026-10-23', 'hasta': '2026-10-22'}):
            self.assertEqual(self.client.get('/api/resumen-ventas/', params).status_code, 400, params)
        self.assertEqual(self.client.get('/api/resumen-ventas/', {'evento': 9999}).status_code, 404)

    def test_xlsx_tiene_las_hojas_y_los_mismos_totales(self):
        resp = self.client.get('/api/resumen-ventas/xlsx/', {'evento': self.junio.id})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment; filename="ventas_pena-2026.xlsx"', resp['Content-Disposition'])
        wb = load_workbook(BytesIO(resp.content))
        self.assertEqual(wb.sheetnames, ['Resumen', 'Por producto', 'Por caja y método de pago', 'Pedidos'])
        resumen = {fila[0]: fila[1] for fila in wb['Resumen'].iter_rows(min_row=3, max_row=9, values_only=True)}
        self.assertEqual(resumen['Total vendido'], 1500000)
        self.assertEqual(resumen['Pedidos cobrados'], 1)
        self.assertEqual(wb['Pedidos'].max_row, 2)   # encabezado + 1 pedido

    def test_imprimible_muestra_el_total_formateado(self):
        resp = self.client.get('/api/resumen-ventas/imprimir/', {'evento': self.junio.id})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '$1.500.000,00')
        self.assertContains(resp, '@media print')


class CierreDeEventoTests(DatosVentas):
    """Cerrar un evento: acción del admin (solo staff), sin tocar pedidos, y con las
    reglas de borrado/edición de pedidos cobrados o de eventos cerrados."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        self.cobrado = self.pedido(self.expo, utc(2026, 10, 23, 0, 30), cantidad=3)
        self.abierto = self.pedido(self.expo, utc(2026, 10, 23, 0, 40), cerrado=False)
        self.api = APIClient()
        self.admin_client = self.client_class()
        self.admin_client.force_login(get_user_model().objects.create_superuser('admin', 'a@a.com', 'x'))

    def accion_cerrar(self, cliente, ids, confirmar=False):
        datos = {'action': 'cerrar_evento', '_selected_action': ids}
        if confirmar:
            datos.update({'confirmar': 'si', 'post': 'yes'})
        return cliente.post('/admin/pdv/evento/', datos)

    def cerrar_expo(self):
        self.accion_cerrar(self.admin_client, [self.expo.id], confirmar=True)
        self.expo.refresh_from_db()

    # --- la acción del admin ---
    def test_la_confirmacion_muestra_el_total_y_todavia_no_cierra(self):
        resp = self.accion_cerrar(self.admin_client, [self.expo.id])
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '$3.000,00')
        self.assertContains(resp, '1 pedido sin cobrar')
        self.expo.refresh_from_db()
        self.assertIsNone(self.expo.cerrado_en)
        self.assertTrue(self.expo.activo)

    def test_confirmar_cierra_sin_tocar_los_pedidos(self):
        antes = list(Pedido.objects.order_by('id').values_list('id', 'cerrado', 'total_final'))
        resp = self.accion_cerrar(self.admin_client, [self.expo.id], confirmar=True)
        self.assertEqual(resp.status_code, 302)
        self.expo.refresh_from_db()
        self.assertFalse(self.expo.activo)
        self.assertIsNotNone(self.expo.cerrado_en)
        self.assertEqual(list(Pedido.objects.order_by('id').values_list('id', 'cerrado', 'total_final')), antes)
        self.assertEqual(resumen_ventas(self.expo)['total_general'], 3000)  # el resumen sigue igual

    def test_sin_login_de_staff_no_cierra(self):
        resp = self.accion_cerrar(self.client_class(), [self.expo.id], confirmar=True)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/admin/login/', resp['Location'])
        self.expo.refresh_from_db()
        self.assertIsNone(self.expo.cerrado_en)

    def test_no_se_cierran_dos_eventos_a_la_vez(self):
        self.accion_cerrar(self.admin_client, [self.expo.id, self.junio.id], confirmar=True)
        self.expo.refresh_from_db()
        self.junio.refresh_from_db()
        self.assertIsNone(self.expo.cerrado_en)
        self.assertIsNone(self.junio.cerrado_en)

    def test_cerrar_dos_veces_no_cambia_la_hora(self):
        self.cerrar_expo()
        primera = self.expo.cerrado_en
        self.accion_cerrar(self.admin_client, [self.expo.id], confirmar=True)
        self.expo.refresh_from_db()
        self.assertEqual(self.expo.cerrado_en, primera)

    def test_un_evento_cerrado_no_puede_quedar_activo(self):
        from django.core.exceptions import ValidationError
        self.cerrar_expo()
        self.expo.activo = True
        with self.assertRaises(ValidationError):
            self.expo.full_clean()
        self.expo.cerrado_en = None  # reabrir es vaciar "Cerrado en"
        self.expo.full_clean()

    # --- pedidos nuevos ---
    def nuevo_pedido(self):
        return self.api.post('/api/pedidos/', {
            'punto_venta': self.caja.id, 'lineas': [{'producto': self.choripan.id, 'cantidad': 1}],
        }, format='json')

    def test_se_rechazan_pedidos_nuevos_de_un_evento_cerrado(self):
        self.assertEqual(self.nuevo_pedido().status_code, 201)
        self.cerrar_expo()
        resp = self.nuevo_pedido()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('punto_venta', resp.json())

    def test_cerrado_en_rechaza_aunque_quede_activo(self):
        Evento.objects.filter(id=self.expo.id).update(cerrado_en=utc(2026, 10, 23, 12, 0))
        resp = self.nuevo_pedido()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('cerrado', str(resp.json()['punto_venta']))

    # --- DELETE / PATCH ---
    def test_no_se_borra_un_pedido_cobrado(self):
        resp = self.api.delete(f'/api/pedidos/{self.cobrado.id}/')
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(Pedido.objects.filter(id=self.cobrado.id).exists())

    def test_si_se_borra_un_pedido_abierto(self):
        self.assertEqual(self.api.delete(f'/api/pedidos/{self.abierto.id}/').status_code, 204)
        self.assertFalse(Pedido.objects.filter(id=self.abierto.id).exists())

    def test_con_el_evento_cerrado_no_se_borra_ni_edita_nada(self):
        self.cerrar_expo()
        for pedido in (self.cobrado, self.abierto):
            self.assertEqual(self.api.delete(f'/api/pedidos/{pedido.id}/').status_code, 409)
            resp = self.api.patch(f'/api/pedidos/{pedido.id}/', {'lineas': [{'producto': self.agua.id, 'cantidad': 1}]}, format='json')
            self.assertEqual(resp.status_code, 409)
        self.assertEqual(Pedido.objects.count(), 2)
        self.assertEqual(self.abierto.lineas.get().producto_id, self.choripan.id)

    def test_se_puede_editar_un_pedido_abierto_de_un_evento_abierto(self):
        resp = self.api.patch(f'/api/pedidos/{self.abierto.id}/', {'lineas': [{'producto': self.agua.id, 'cantidad': 2}]}, format='json')
        self.assertEqual(resp.status_code, 200)

    # --- tablero ---
    def test_eventos_informa_el_cierre(self):
        self.cerrar_expo()
        data = {e['id']: e for e in self.api.get('/api/eventos/').json()}
        self.assertIsNotNone(data[self.expo.id]['cerrado_en'])
        self.assertIsNone(data[self.junio.id]['cerrado_en'])
        self.assertEqual(self.api.get('/api/resumen-ventas/', {'evento': self.expo.id}).json()['total_general'], 3000)
