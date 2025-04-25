from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from ..models import Log
from django.db.models import Q
from django.http import HttpResponse
from datetime import datetime


@login_required
def main_page_view(request):
    """
    Display the Audit Logs page.
    """
    query = request.GET.get('q')
    date_str = request.GET.get("date", "").strip() 
    logs_qs = Log.objects.all().order_by("-time_started")

    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            logs_qs = logs_qs.filter(time_started__date=target_date)
        except ValueError:
            pass

    if query:
        # Look in to changing this or adding filter, right now to properly search 
        # using date would need to type 2025-04-20
        logs_qs = logs_qs.filter(phone_number__icontains=query)
    
    paginator = Paginator(logs_qs, 10)

    pg_num = request.GET.get("page")
    logs = paginator.get_page(pg_num)

    return render(request, 'audit_logs.html', {"logs": logs, "query": query, "date_str": date_str,})

@login_required
def single_log_view(request, log_id):
    log = get_object_or_404(Log, id=log_id)

    # Remove weird large spacing caused by \n\r in the messages  for transcript
    cleaned_transcript = []
    for entry in log.transcript:
        message = entry.get('message', '')
        cleaned_message = ' '.join(message.replace('\n', ' ').replace('\r', ' ').split())
        cleaned_transcript.append({
            'speaker': entry.get('speaker', ''),
            'message': cleaned_message
        })

    return render(request, 'single_audit_log.html', {"log": log, "cleaned_transcript": cleaned_transcript})