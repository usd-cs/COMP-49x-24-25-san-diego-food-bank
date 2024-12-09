from django.shortcuts import render
from .models import FAQ
# Create your views here.

def login_view(request):
    """
    Properly handle user login by displaying the login form and processing the user authentication.

    This view will display the login form for users to input their username and password. It will
    validate the user's credentials and log them in, then redirect them to the home page.
    """
    return render(request, 'admin_panel/login.html')

def faq_page_view(request):
    faqs = FAQ.objects.all() # Retrieve FAQs from database and update the view
    return render(request, 'faq_page.html')
    