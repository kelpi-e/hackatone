# pyexec/urls.py
from django.contrib import admin
from django.urls import path
from codeapp import views  # ← импортируем из codeapp

urlpatterns = [
    path('admin/', admin.site.urls),
    path('run/', views.index, name='index'),
    path('run_code/', views.run_code, name='run_code'),
]