import json

from django.contrib.auth import authenticate, login as django_login, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.http.response import JsonResponse, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .forms import CustomAuthenticationForm, RegistrationForm, ForgotPasswordForm
from .models import get_preferences_default

User = get_user_model()


class LogoutView(DjangoLogoutView):
    next_page = reverse_lazy('lab:index')


def login(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request.POST)

        request.session['just_signed_up'] = False
        request.session['password_sent'] = False

        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            user = authenticate(username=email, password=password)
            django_login(request, user)
            return redirect(reverse('lab:index'))
        else:
            return render(request, 'accounts/login.html', {'form': form})
    else:
        form = CustomAuthenticationForm()
        return render(request, 'accounts/login.html', {'form': form})


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.set_password(user.raw_password)
            user.save()
            user.send_password()
            request.session['just_signed_up'] = True
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

def preferences_view(request):
    if request.is_ajax and request.method == "GET":
        cur_user = request.user
        if cur_user.is_anonymous:
            json_dump = json.dumps(get_preferences_default())
            return JsonResponse({"instance": json_dump}, status=200)

        preferences = json.dumps(cur_user.preferences)
        return JsonResponse({"instance": preferences}, status=200)
    else:
        # some form errors occurred.
        return JsonResponse({"error": "something went wrong"}, status=400)


@login_required()
@method_decorator(csrf_exempt)
def set_preferred_mute_value(request):
    if request.method == 'POST':
        request.user.preferences['mute'] = json.loads(request.POST.get('mute'))
        request.user.save()
    return HttpResponse(json.dumps(request.user.preferences))


@login_required()
@method_decorator(csrf_exempt)
def set_preferred_volume(request):
    if request.method == 'POST':
        request.user.preferences['volume'] = request.POST.get('volume')
        request.user.save()
    return HttpResponse(json.dumps(request.user.preferences))
