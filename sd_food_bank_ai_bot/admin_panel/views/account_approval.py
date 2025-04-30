from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from ..models import Admin
from django.db.models import Q
from django.http import HttpResponse

# TODO: Update all admin pages (except login and creation) to check that it is a verified account
#           Possibly just update log in to only allow user ot log in when account is approved
@login_required # TODO: Add permission only for admin account later
def account_approval_page(request):
    """
    Display the account approval page. Only available to one Admin.
    """
    query = request.GET.get('q')
    selected_status = request.GET.get('status', '')
    page_number = request.GET.get('page')

    admins = Admin.objects.all()

    # Filter admins based on the search query
    if query:
        admins = admins.filter(
            Q(foodbank_id__icontains=query) | 
            Q(foodbank_email__icontains=query)
        )

    if selected_status:
        if selected_status == "None":
            admins = admins.filter(approved_for_admin_panel=None)
        elif selected_status == "True":
            admins = admins.filter(approved_for_admin_panel=True)
        elif selected_status == "False":
            admins = admins.filter(approved_for_admin_panel=False)

    paginator = Paginator(admins, 10) # 10 FAQs per page
    approval_page = paginator.get_page(page_number)

    context = {
        "accounts": approval_page, 
        "query": query,
        "selected_status": selected_status
    }
    print(context)
    return render(request, "account_approval.html", context) 

def deny_account(request):
    """
    Deny an account that is approved or awaiting approval. Prohibits access to admin panel.
    """

    return HttpResponse("Denied")

def approve_account(request):
    """
    Approve an account that is denied or awaiting approval. Allows access to admin panel.
    """

    return HttpResponse("Approved")

def delete_account(request):
    """
    Delete account that is approved, denied, or awaiting approval.
    """

    return HttpResponse("Deleted")

def add_account_page(request):
    """
    Put text here.
    """

    return HttpResponse("Add account page")