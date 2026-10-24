from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .permisos import es_admin, es_cajero


class FormularioLogin(AuthenticationForm):
    """Solo entran administradores y cajeros; cualquier otro usuario se rechaza con un mensaje claro."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)  # rechaza usuarios inactivos
        if not (es_admin(user) or es_cajero(user)):
            raise ValidationError('Este usuario no es cajero ni administrador.', code='sin_rol')
