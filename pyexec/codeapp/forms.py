from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import User


class UserRegistrationForm(forms.ModelForm):
    """Форма регистрации пользователя (только никнейм и роль)"""
    
    class Meta:
        model = User
        fields = ['username', 'role']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Никнейм'
            }),
            'role': forms.Select(attrs={
                'class': 'form-select'
            }, choices=User.ROLE_CHOICES)
        }
        labels = {
            'username': 'Никнейм',
            'role': 'Роль'
        }
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise forms.ValidationError('Никнейм обязателен для заполнения.')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Пользователь с таким никнеймом уже существует.')
        return username
    
    def save(self, commit=True):
        user = super().save(commit=False)
        # Устанавливаем случайный пароль (не используется при входе по никнейму)
        user.set_unusable_password()
        if commit:
            user.save()
        return user


class UserLoginForm(forms.Form):
    """Форма входа пользователя (только по никнейму)"""
    
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Никнейм'
        }),
        label='Никнейм',
        max_length=150
    )
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise forms.ValidationError('Введите никнейм.')
        return username

