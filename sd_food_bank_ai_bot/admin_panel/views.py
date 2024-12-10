from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login,logout
from django.db.models import Q
from .models import FAQ, Tag
from .forms import FAQForm


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

def logout_view(request):
    """ 
    Properly handle user logout and redirect back to the login page
    """
    logout(request)
    return redirect('login')

@login_required
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

@login_required
def delete_faq(request, faq_id):
    if request.method == 'POST':
        faq = get_object_or_404(FAQ, id=faq_id)
        faq.delete()
        return redirect('faq_page')

@login_required
def create_faq(request):
    if request.method == "POST":
        form = FAQForm(request.POST)
        if form.is_valid():
            faq = form.save(commit=False)
            faq.save()
        
            existing_tags = form.cleaned_data['existing_tags']
            for tag in existing_tags:
                faq.tags.add(tag)

            new_tags = form.cleaned_data['new_tags']
            if new_tags:
                new_tag_names = [name.strip() for name in new_tags.split(',') if name.strip()]
                for tag_name in new_tag_names:
                    tag, created = Tag.objects.get_or_create(name=tag_name)
                    faq.tags.add(tag)
            return redirect("faq_page")
    else:
        form = FAQForm()

    return render(request, "create_faq.html", {"form": form})

def edit_faq(request, faq_id):
    old_faq = get_object_or_404(FAQ, id=faq_id)

    if request.method == 'POST':
        form = FAQForm(request.POST)
        if form.is_valid():
            new_faq = form.save(commit=False)
            new_faq.save()

            existing_tags = form.cleaned_data['existing_tags']
            for tag in existing_tags:
                new_faq.tags.add(tag)

            new_tags = form.cleaned_data['new_tags']
            if new_tags:
                new_tag_names = [name.strip() for name in new_tags.split(',') if name.strip()]
                for tag_name in new_tag_names:
                    tag, created = Tag.objects.get_or_create(name=tag_name)
                    new_faq.tags.add(tag)

            old_faq.delete()

            return redirect('faq_page')
    else:
        form = FAQForm(instance=old_faq)

    return render(request, 'edit_faq.html', {'form': form, 'faq': old_faq})
