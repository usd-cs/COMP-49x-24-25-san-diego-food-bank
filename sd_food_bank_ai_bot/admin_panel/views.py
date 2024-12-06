from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login
# Create your views here.

def login_view(request):
    """
    Properly handle user login by displaying the login form and processing the user authentication.

    This view will display the login form for users to input their username and password. It will
    validate the user's credentials and log them in, then redirect them to the home page.
    """
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect() # No Home page yet, need to add redirect later
        else: 
            form = AuthenticationForm()
        return render(request, 'admin_panel/login.html')

def faq_page_view(request):
    return render(request, 'faq_page.html')
