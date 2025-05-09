from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.db.models import Q
from django.core.paginator import Paginator
from ..models import FAQ, Tag, Admin
from ..forms import FAQForm


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
            if user.approved_for_admin_panel:
                login(request, user)
                return redirect('faq_page')
            else:
                form._errors.pop('__all__', None)
                form.add_error(None, "Please wait for your account to be confirmed.")
        else:
            # clear the errors generated for the form and add custom message to display on login page about what went wrong
            form._errors.pop('__all__', None)
            form.add_error(None, "Username or password is incorrect")
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    """
    Properly handle user logout and redirect back to the login page
    """
    logout(request)
    return redirect('login')

def create_account_view(request):
    """
    Render the create account page for foodbank admin employees.
    Only employees with valid foodbank credentials (foodbank ID and email)
    and approved_for_admin_panel=True can create an account.
    """
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        foodbank_employee_id = request.POST.get("foodbank_employee_id", "").strip()
        foodbank_email = request.POST.get("foodbank_email", "").strip()

        if not (username and password and foodbank_employee_id and foodbank_email):
            messages.error(request, "All fields are required.")
            return render(request, "create_account.html")

        # Look for an approved admin record with the provided credentials.
        try:
            admin_candidate = Admin.objects.get(
                foodbank_id=foodbank_employee_id,
                foodbank_email=foodbank_email
            )
        except Admin.DoesNotExist:
            messages.error(request, "No approved admin record found for the provided credentials.")
            return render(request, "create_account.html")

        if admin_candidate.approved_for_admin_panel is None:
            admin_candidate.username = username
            admin_candidate.password = make_password(password) # Hash password for security purposes
            admin_candidate.approved_for_admin_panel = False
            admin_candidate.save()
            
            messages.error(request, "You're account has been created but not approved. Please request approval.")
            return render(request, "create_account.html")
        
        elif admin_candidate.approved_for_admin_panel is False:
            admin_candidate.username = username
            admin_candidate.password = make_password(password) # Hash password for security purposes
            admin_candidate.save()

            messages.error(request, "You're account has been created and is pending approval. Please wait for approval.")
            return render(request, "create_account.html")
        
        if Admin.objects.filter(username=username).exists():
            messages.error(request, "This username is already in use.")
            return render(request, "create_account.html")

        admin_candidate.username = username
        admin_candidate.password = make_password(password) # Hash password for security purposes
        admin_candidate.save()

        messages.success(request, "Account created successfully! Please log in.")
        return redirect("login")  

    return render(request, "create_account.html")

@login_required
def faq_page_view(request):
    """
    Display the FAQ page.

    This view retrieves FAQs from the database and displays them on a page. Admins can
    search for FAQs or filter them by their assigned tag. All available tags are also displayed
    for the admins to select.
    """
    query = request.GET.get('q')
    selected_tag = request.GET.get('tag', '')
    page_number = request.GET.get('page')

    faqs_qs = FAQ.objects.all()

    # Filter FAQs based on the search query
    if query:
        faqs_qs = faqs_qs.filter(
            Q(question__icontains=query) | 
            Q(answer__icontains=query)
        )

    if selected_tag:
        faqs_qs = faqs_qs.filter(tags__id=selected_tag)

    paginator = Paginator(faqs_qs.order_by("id"), 10) # 10 FAQs per page
    faqs_page = paginator.get_page(page_number)

    context = {
        "faqs": faqs_page, 
        "query": query,
        "tags": Tag.objects.all(),
        "selected_tag":int(selected_tag) if selected_tag else None,
    }
    return render(request, "faq_page.html", context) 

@login_required
def delete_faq(request, faq_id):
    """
    Allows admins to delete a specific FAQ.

    This view will allow admins to delete an FAQ entry based on the faq_id.
    After successfully deleting, the user is redirected back to the faq page.
    """
    if request.method == 'POST':
        faq = get_object_or_404(FAQ, id=faq_id)
        faq.delete()
        return redirect('faq_page')


@login_required
def create_faq(request):
    """
    Allows admin to create a new FAQ entry with the properly associated tags.

    This view handles the creation of new FAQs, including the ability to group them
    with existing or new tags that can be created.
    """
    if request.method == "POST":
        form = FAQForm(request.POST)
        if form.is_valid():
            faq = form.save(commit=False)
            faq.save()
            # Add existing tags to the FAQ
            existing_tags = form.cleaned_data['existing_tags']
            for tag in existing_tags:
                faq.tags.add(tag)
            # Process and add new tags to the FAQ
            new_tags = form.cleaned_data['new_tags']
            if new_tags:
                new_tag_names = [name.strip() for name in new_tags.split(',') if name.strip()]
                for tag_name in new_tag_names:
                    tag, created = Tag.objects.get_or_create(name=tag_name)
                    faq.tags.add(tag)
            return redirect("faq_page")
    else:
        form = FAQForm()  # Empty form for FAQ creation

    return render(request, "create_faq.html", {"form": form})


def edit_faq(request, faq_id):
    """
    Allows admins to edit existing FAQs.

    This view retrieves an FAQ based on its faq_id and allows admins to update its content
    and tags. The older FAQs can be replaced with newer, updated information. New tags can
    also be added and existing tags can be reassigned.
    """
    old_faq = get_object_or_404(FAQ, id=faq_id)

    if request.method == 'POST':
        form = FAQForm(request.POST)
        # Extract content from form of old fag to decipher if any was changed and update accordingly
        if form.is_valid():
            new_faq = form.save(commit=False)
            new_faq.id = old_faq.id
            new_faq.tags.clear()
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
            new_faq.save()

            return redirect('faq_page')
    else:
        form = FAQForm(instance=old_faq)

    return render(request, 'edit_faq.html', {'form': form, 'faq': old_faq})
