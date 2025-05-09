from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth.decorators import permission_required
from ..models import Admin
from django.db.models import Q
from ..forms import AccountForm


@permission_required("admin_panel.can_approve_users", raise_exception=True)
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
    return render(request, "account_approval.html", context) 

@permission_required("admin_panel.can_approve_users", raise_exception=True)
def deny_account(request, account_id):
    """
    Deny an account that is approved or awaiting approval. Prohibits access to admin panel.
    """
    account = get_object_or_404(Admin, id=account_id)
    account.approved_for_admin_panel = None
    account.save()

    return redirect("account_approval")

@permission_required("admin_panel.can_approve_users", raise_exception=True)
def approve_account(request,  account_id):
    """
    Approve an account that is denied or awaiting approval. Allows access to admin panel.
    """
    account = get_object_or_404(Admin, id=account_id)
    account.approved_for_admin_panel = True
    account.save()

    return redirect("account_approval")

@permission_required("admin_panel.can_approve_users", raise_exception=True)
def delete_account(request,  account_id):
    """
    Delete account that is approved, denied, or awaiting approval.
    """
    account = get_object_or_404(Admin, id=account_id)
    account.delete()

    return redirect("account_approval")

@permission_required("admin_panel.can_approve_users", raise_exception=True)
def add_account_page(request):
    """
    A page to add an employee to the Admin database to allow them to create an account.
    """
    if request.method == "POST":
        form = AccountForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("account_approval")
    else:
        form = AccountForm()

    return render(request, 'add_account.html', {'form': form})