from django import forms
from django.contrib.auth import authenticate, login as django_login
from django.contrib.auth.views import LogoutView as DjangoLogoutView, LoginView as DjangoLoginView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import CustomAuthenticationForm, RegistrationForm


class LogoutView(DjangoLogoutView):
    next_page = reverse_lazy('lab:index')


def login(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            user = authenticate(username=email, password=password)
            django_login(request, user)
            return redirect(reverse_lazy('lab:index'))
        else:
            return render(request, 'accounts/login.html', {'form': form})
    else:
        form = CustomAuthenticationForm()
        raw_password = request.session.get('raw_password')
        if raw_password:
            request.session.pop('raw_password')
        return render(request, 'accounts/login.html', {'form': form, 'raw_password': raw_password})


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.set_password(user.raw_password)
            user.save()
            request.session['raw_password'] = user.raw_password
            return redirect(reverse_lazy('custom-login'))
        else:
            return render(request, 'accounts/register.html', {'form': form})
    else:
        form = RegistrationForm()
        return render(request, 'accounts/register.html', {'form': form})
