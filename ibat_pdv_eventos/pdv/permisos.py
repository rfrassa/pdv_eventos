from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import PuntoVenta

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


def caja_restringida(user):
    """Caja a la que está atado el usuario; None si no tiene restricción (administrador).

    Un cajero sin caja asignada no puede operar: se corta con 403 y un mensaje claro.
    """
    if es_admin(user):
        return None
    caja = PuntoVenta.objects.filter(usuario=user).first()
    if caja is None:
        raise PermissionDenied('Tu usuario no tiene una caja asignada. Pedile al administrador que te la asigne.')
    return caja


def exigir_pedido_de_su_caja(user, pedido):
    """403 si un cajero intenta tocar un pedido de otra caja. El administrador no tiene restricción."""
    caja = caja_restringida(user)
    if caja is not None and pedido.punto_venta_id != caja.id:
        raise PermissionDenied('Este pedido es de otra caja.')
