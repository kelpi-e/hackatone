# pyexec/urls.py
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from codeapp import views  # ← импортируем из codeapp

urlpatterns = [
    path('', views.home, name='home'),
    path('admin/', admin.site.urls),
    path('run/', views.index, name='index'),
    path('run_code/', views.run_code, name='run_code'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else None)