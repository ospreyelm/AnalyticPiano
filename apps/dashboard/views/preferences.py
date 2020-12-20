from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from apps.dashboard.forms import KeyboardForm


@login_required()
def dashboard_preferences_view(request):
    kbd_size_form = KeyboardForm()
    if request.user.keyboard_size:
        kbd_size_form.fields['keyboard_size'].initial = request.user.keyboard_size

    if request.method == 'POST':
        kbd_size_form = KeyboardForm(request.POST)
        if kbd_size_form.is_valid():
            request.user.keyboard_size = kbd_size_form.cleaned_data['keyboard_size']
            request.user.save()
        return HttpResponseRedirect(reverse('dashboard:preferences'))

    return render(request, 'dashboard/preferences.html', {'form': kbd_size_form})