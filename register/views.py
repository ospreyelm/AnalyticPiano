
from django.shortcuts import render, redirect
from .forms import RegisterForm
from django.contrib import messages


# Create your views here.
def register(response):
    if response.method == "POST":
	    form = RegisterForm(response.POST)
	    if form.is_valid():
	        new_user = form.save()
            
	    return redirect("/accounts/login")
    else:
        form = RegisterForm()

    return render(response, "register/register.html", {"form":form})