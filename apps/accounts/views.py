import json
from django import forms
from django.contrib.auth import authenticate, login as django_login, get_user_model
from django.contrib.auth.views import LogoutView as DjangoLogoutView, LoginView as DjangoLoginView
from django.core import serializers
from django.http.response import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import CustomAuthenticationForm, RegistrationForm, ForgotPasswordForm
from .models import User

User = get_user_model()


class LogoutView(DjangoLogoutView):
    next_page = reverse_lazy('lab:index')


def login(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            user = authenticate(username=email, password=password)
            goto = request.GET.get('next', '/lab/')
            django_login(request, user)
            return redirect(goto)
        else:
            return render(request, 'accounts/login.html', {'form': form})
    else:
        form = CustomAuthenticationForm()
        raw_password = request.session.get('raw_password')
        if raw_password:
            request.session.pop('raw_password')
        
        password_sent = request.session.get('password_sent')
        if password_sent:
            request.session.pop('password_sent')
            
        return render(request, 'accounts/login.html', {'form': form, 
                                                       'raw_password': raw_password,
                                                       'password_sent': password_sent})


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


def forgot_password_view(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            request.session['password_sent'] = True
            return redirect(reverse_lazy('custom-login'))
        else:
            return render(request, 'accounts/send_password.html', {'form': form})
    else:
        form = ForgotPasswordForm()
        return render(request, 'accounts/send_password.html', {'form': form})


# The following view function is used to send the keyboard size to the front-end
# Can be extended to include other preferences as it sends a JSON

def send_keyboard_size(request):
    if request.is_ajax and request.method == "GET":
        cur_user = request.user
        if cur_user.is_anonymous:
            data_set = {"keyboard_size": 49}
            json_dump = json.dumps(data_set)
            return JsonResponse({"instance": json_dump}, status=200)

        keyboard_size = cur_user.keyboard_size
        print ("keyboard size is ", keyboard_size)
        data_set = {"keyboard_size": keyboard_size}
        json_dump = json.dumps(data_set)
        return JsonResponse({"instance": json_dump}, status=200)
    else:
         # some form errors occured.
        return JsonResponse({"error": "something went wrong"}, status=400)
