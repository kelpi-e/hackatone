from django.contrib.auth.backends import ModelBackend
from .models import User


class UsernameOnlyBackend(ModelBackend):
    """Бэкенд аутентификации только по никнейму (без пароля)"""
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('username')
        
        if username is None:
            return None
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None
        
        # Возвращаем пользователя без проверки пароля
        return user if self.user_can_authenticate(user) else None

