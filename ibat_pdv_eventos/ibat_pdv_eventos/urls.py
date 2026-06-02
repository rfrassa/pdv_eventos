from django.contrib import admin
from django.urls import include, path
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pdv.urls')),
]

# Serve static files (including contrib static like admin) in DEBUG using
# staticfiles finders so app/static and admin files are available.
if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    from django.conf.urls.static import static

    # Serve collected static files (STATIC_ROOT) as well as app/static in DEBUG
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
