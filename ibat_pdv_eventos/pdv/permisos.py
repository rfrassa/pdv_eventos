from rest_framework.permissions import SAFE_METHODS, BasePermission

GRUPO_CAJERO = 'Cajero'


def es_admin(user):
    return bool(user and user.is_authenticated and user.is_staff)


def es_cajero(user):
    return bool(user and user.is_authenticated and user.groups.filter(name=GRUPO_CAJERO).exists())


class EsAdmin(BasePermission):
    """Solo administrador (is_staff): tablero, Excel, eventos, cierre, productos."""
    message = 'Solo el administrador puede hacer esto.'

    def has_permission(self, request, view):
        return es_admin(request.user)


class EsCajeroOAdmin(BasePermission):
    """Operación de caja: cobrar, reimprimir, historial."""
    message = 'Tu usuario no es cajero ni administrador.'

    def has_permission(self, request, view):
        return es_admin(request.user) or es_cajero(request.user)


class CajeroLeeAdminEscribe(BasePermission):
    """Cajero o administrador pueden leer; solo el administrador puede escribir."""
    message = 'Solo el administrador puede modificar esto.'

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return es_admin(request.user) or es_cajero(request.user)
        return es_admin(request.user)
