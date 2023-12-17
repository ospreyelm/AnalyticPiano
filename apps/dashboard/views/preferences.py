from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from apps.dashboard.forms import KeyboardForm


@login_required()
def dashboard_preferences_view(request):
    kbd_size_form = KeyboardForm()
    kbd_size_form.fields["keyboard_size"].initial = request.user.preferences[
        "keyboard_size"
    ]
    try:
        kbd_size_form.fields["keyboard_octaves_offset"].initial = request.user.preferences[
            "keyboard_octaves_offset"
        ]
    except:
        kbd_size_form.fields["keyboard_octaves_offset"].initial = 0
    kbd_size_form.fields["auto_advance"].initial = request.user.preferences[
        "auto_advance"
    ]
    kbd_size_form.fields["auto_advance_delay"].initial = request.user.preferences[
        "auto_advance_delay"
    ]
    kbd_size_form.fields["auto_repeat"].initial = request.user.preferences[
        "auto_repeat"
    ]
    kbd_size_form.fields["auto_repeat_delay"].initial = request.user.preferences[
        "auto_repeat_delay"
    ]
    try:
        kbd_size_form.fields["auto_sustain_duration"].initial = request.user.preferences[
            "auto_sustain_duration"
        ]
    except:
        kbd_size_form.fields["auto_sustain_duration"].initial = 20

    if request.method == "POST":
        kbd_size_form = KeyboardForm(request.POST)
        if kbd_size_form.is_valid():
            request.user.preferences["keyboard_size"] = kbd_size_form.cleaned_data[
                "keyboard_size"
            ]
            request.user.preferences["keyboard_octaves_offset"] = kbd_size_form.cleaned_data[
                "keyboard_octaves_offset"
            ]
            request.user.preferences["auto_advance"] = kbd_size_form.cleaned_data[
                "auto_advance"
            ]
            request.user.preferences["auto_advance_delay"] = kbd_size_form.cleaned_data[
                "auto_advance_delay"
            ]
            request.user.preferences["auto_repeat"] = kbd_size_form.cleaned_data[
                "auto_repeat"
            ]
            request.user.preferences["auto_repeat_delay"] = kbd_size_form.cleaned_data[
                "auto_repeat_delay"
            ]
            request.user.preferences["auto_sustain_duration"] = kbd_size_form.cleaned_data[
                "auto_sustain_duration"
            ]
            request.user.save()
        return HttpResponseRedirect(reverse("dashboard:preferences"))

    return render(request, "dashboard/preferences.html", {"form": kbd_size_form})
