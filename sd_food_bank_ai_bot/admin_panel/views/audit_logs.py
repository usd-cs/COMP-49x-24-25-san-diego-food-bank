from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from ..models import Log
from django.db.models import Q
from django.http import HttpResponse


@login_required
def main_page_view(request):
    """
    Display the Audit Logs page.
    """
    query = request.GET.get('q')

    if query:
        # Look in to changing this or adding filter, right now to properly search 
        # using date would need to type 2025-04-20
        logs_list = Log.objects.filter(Q(phone_number__icontains=query)).order_by("-time_started")
    else:
        logs_list = Log.objects.all().order_by("-time_started")
    
    paginator = Paginator(logs_list, 10)

    pg_num = request.GET.get("page")
    logs = paginator.get_page(pg_num)

    return render(request, 'audit_logs.html', {"logs": logs, "query": query})

@login_required
def single_log_view(request, log_id):
    log = get_object_or_404(Log, id=log_id)

    cleaned_transcript = []
    for entry in log.transcript:
        message = entry.get('message', '')
        cleaned_message = ' '.join(message.replace('\n', ' ').replace('\r', ' ').split())
        cleaned_transcript.append({
            'speaker': entry.get('speaker', ''),
            'message': cleaned_message
        })
    # Replace with transcript stuff
    return render(request, 'single_audit_log.html', {"log": log, "cleaned_transcript": cleaned_transcript})
    # return HttpResponse(str(log_id))