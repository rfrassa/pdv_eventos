from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic.base import RedirectView
from django.views.static import serve as static_serve
from django.conf import settings

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),
    path('admin/', admin.site.urls),
    re_path(r'^static/(?P<path>.*)$', static_serve, {'document_root': settings.BASE_DIR / 'static'}),
    path('', include('pdv.urls')),
]
