import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pdv', '0005_asignar_evento_a_pedidos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pedido',
            name='evento',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pedidos', to='pdv.evento'),
        ),
    ]
