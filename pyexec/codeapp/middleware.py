"""
Middleware для проверки бана пользователей
"""
from django.shortcuts import redirect
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin


class BanCheckMiddleware(MiddlewareMixin):
    """
    Middleware для проверки, забанен ли пользователь.
    Блокирует доступ ко всем страницам для забаненных пользователей.
    """
    
    # Исключаем эти URL из проверки бана (для выхода, статики и т.д.)
    EXCLUDED_PATHS = [
        '/logout/',
        '/static/',
        '/media/',
        '/admin/logout/',
    ]
    
    def process_request(self, request):
        """
        Проверяет, забанен ли пользователь перед обработкой запроса
        """
        # Пропускаем исключенные пути
        if any(request.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return None
        
        # Проверяем только аутентифицированных пользователей
        if request.user.is_authenticated and hasattr(request.user, 'is_banned'):
            if request.user.is_banned:
                # Устанавливаем флаг в сессии для отображения модального окна
                request.session['show_ban_modal'] = True
                # Для AJAX запросов возвращаем JSON
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.http import JsonResponse
                    return JsonResponse({
                        'banned': True,
                        'reason': request.user.ban_reason or 'Вы заблокированы за нарушение правил'
                    }, status=403)
        
        return None

