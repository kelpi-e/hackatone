
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from codeapp import views

urlpatterns = [
    path('', views.home, name='home'),                 # Главная: index.html
    path('runcode/', views.index, name='runcode'),     # Редактор: ide.html
    path('run_code/', views.run_code, name='run_code'),  # POST для запуска кода
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)