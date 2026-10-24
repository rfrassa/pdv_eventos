from getpass import getpass

from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

CAJEROS = ['caja1', 'caja2', 'caja3']
GRUPO_CAJERO = 'Cajero'


class Command(BaseCommand):
    help = (
        'Crea los usuarios caja1, caja2 y caja3 en el grupo Cajero. Pide la contraseña por teclado. '
        'Los que ya existen no se tocan. La caja de cada usuario se asigna después, en el admin.'
    )

    def _pedir_clave(self, username):
        clave = getpass(f'Contraseña para {username}: ')
        if clave != getpass(f'Repetir contraseña para {username}: '):
            raise CommandError(f'Las contraseñas de {username} no coinciden.')
        try:
            validate_password(clave)
        except ValidationError as e:
            raise CommandError(f'Contraseña de {username} rechazada: ' + ' '.join(e.messages))
        return clave

    def handle(self, *args, **options):
        grupo, _ = Group.objects.get_or_create(name=GRUPO_CAJERO)
        for username in CAJEROS:
            if User.objects.filter(username=username).exists():
                self.stdout.write(f'{username}: ya existe, no se modifica.')
                continue
            usuario = User.objects.create_user(username, password=self._pedir_clave(username))
            usuario.groups.add(grupo)
            self.stdout.write(self.style.SUCCESS(f'{username}: creado.'))
