from django.shortcuts import render, HttpResponse, redirect
from django.contrib.auth import login 
from django.contrib.auth.forms import AuthenticationForm

def login_view(request):
    """
    Properly handle user login by displaying the login form and processing the user authentication.
    This view will display the login form for users to input their email and password. It will
    validate the user's credentials and log them in, then redirect them to the home page.
    """
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'web_forum/login.html', {'form': form})