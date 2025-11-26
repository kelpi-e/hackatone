from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from codeapp import views

urlpatterns = [
    path('', views.home, name='home'),                 # http://127.0.0.1:8000/
    path('runcode/', views.index, name='runcode'),    # http://127.0.0.1:8000/runcode
    path('run_code/', views.run_code, name='run_code'),  # для кнопки Run
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
