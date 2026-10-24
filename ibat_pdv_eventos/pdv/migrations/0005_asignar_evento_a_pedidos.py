from datetime import datetime, timezone

from django.db import migrations

# TODO(deuda): rangos y ids fijos, válidos solo para la base de producción de
# octubre 2026 (tras borrar las pruebas, fase 1a). En una base sin pedidos no
# hace nada. Si hay pedidos fuera de estos rangos, falla a propósito.
JUNIO_FIN = datetime(2026, 7, 1, tzinfo=timezone.utc)
EXPO_INICIO = datetime(2026, 10, 22, 22, 0, tzinfo=timezone.utc)
EVENTO_PENA_JUNIO = 2
EVENTO_EXPO = 3


def asignar_evento(apps, schema_editor):
    Pedido = apps.get_model('pdv', 'Pedido')
    if not Pedido.objects.exists():
        return

    Pedido.objects.filter(creado__lt=JUNIO_FIN).update(evento_id=EVENTO_PENA_JUNIO)
    Pedido.objects.filter(creado__gte=EXPO_INICIO).update(evento_id=EVENTO_EXPO)

    sin_asignar = Pedido.objects.filter(evento__isnull=True).count()
    if sin_asignar:
        raise RuntimeError(f'{sin_asignar} pedidos quedaron sin evento; migración abortada.')


class Migration(migrations.Migration):

    dependencies = [
        ('pdv', '0004_pedido_evento'),
    ]

    operations = [
        migrations.RunPython(asignar_evento, migrations.RunPython.noop),
    ]
