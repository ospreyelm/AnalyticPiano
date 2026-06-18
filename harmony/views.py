from django.shortcuts import redirect, render

from apps.accounts.navigation import home_url_for_user


def home_redirect(request):
    return redirect(home_url_for_user(request.user))


def error_404(request, exception):
    data = {}

    # try to render the error message that is raised
    try:
        error_message = getattr(exception, "args", "")
        if error_message and isinstance(error_message, tuple):
            if isinstance(error_message[0], str):
                data["error_message"] = error_message[0]
    except:
        pass

    return render(request, "404.html", data, status=404)
