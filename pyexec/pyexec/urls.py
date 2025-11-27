
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from codeapp import views

urlpatterns = [
    path('', views.home, name='home'),                 # Главная: index.html
    path('runcode/', views.index, name='runcode'),     # Редактор: ide.html
    path('run_code/', views.run_code, name='run_code'),  # POST для запуска кода
    path('interview/', views.interview, name='interview'),  # Интервью
    path('interview/api/', views.interview_api, name='interview_api'),  # API для интервью
    path('code/chat/', views.code_chat_api, name='code_chat_api'),  # API для чата во время кодинга
    path('register/', views.register, name='register'),  # Регистрация
    path('login/', views.user_login, name='login'),      # Вход
    path('logout/', views.user_logout, name='logout'),   # Выход
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)