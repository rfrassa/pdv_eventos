from django.urls import path

from . import views

urlpatterns = [
    path('', views.pwa_index, name='pwa-index'),
    path('api/productos/', views.productos_list, name='productos-list'),
    path('api/productos/<int:producto_id>/', views.producto_detail, name='producto-detail'),
    path('api/pedidos/', views.pedido_create, name='pedido-create'),
    path('api/pedidos/abiertos/', views.pedidos_abiertos, name='pedidos-abiertos'),
    path('api/pedidos/historial/', views.pedidos_historial, name='pedidos-historial'),
    path('api/pedidos/<int:pedido_id>/', views.pedido_detail, name='pedido-detail'),
    path('api/pedidos/<int:pedido_id>/reimprimir/', views.pedido_reimprimir, name='pedido-reimprimir'),
    path('api/pedidos/<int:pedido_id>/imprimir-local/', views.pedido_imprimir_local, name='pedido-imprimir-local'),
    path('api/pedidos/<int:pedido_id>/imprimir-pdf/', views.pedido_imprimir_pdf, name='pedido-imprimir-pdf'),
    path('api/test-print/', views.test_print, name='test-print'),
    path('api/impresoras/', views.impresoras_disponibles, name='impresoras-disponibles'),
    path('api/cierre-caja/', views.cierre_caja, name='cierre-caja'),
    path('api/resumen-ventas/', views.resumen_ventas_view, name='resumen-ventas'),
    path('api/pdv/', views.pdvs_list, name='pdvs-list'),
]
