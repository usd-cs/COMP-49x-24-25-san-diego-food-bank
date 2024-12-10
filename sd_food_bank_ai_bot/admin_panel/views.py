from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login
from django.db.models import Q
from .models import FAQ, Tag

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
            return redirect('faq_page') 
    else: 
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def faq_page_view(request):
    query = request.GET.get('q')
    selected_tag = request.GET.get('tag', '')

    if query:
        faqs = FAQ.objects.filter(Q(question__icontains=query) | Q(answer__icontains=query))
    else:
        faqs = FAQ.objects.all() # Retrieve FAQs from database and update the view

    if selected_tag:
        faqs = faqs.filter(tags__id=selected_tag)

    tags = Tag.objects.all()

    return render(request, 'faq_page.html', {"faqs": faqs, "query": query, "tags": tags,
        "selected_tag": int(selected_tag) if selected_tag else None,})

def delete_faq(request, faq_id):
    if request.method == 'POST':
        faq = get_object_or_404(FAQ, id=faq_id)
        faq.delete()
        return redirect('faq_page')
