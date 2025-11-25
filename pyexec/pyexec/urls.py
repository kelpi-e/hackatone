from django.contrib import admin
from django.urls import path
from codeapp import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.run_code, name='index'),  # главная страница сразу с редактором
    path('run/', views.run_code, name='run_code'),  # можно оставить для формы
]
