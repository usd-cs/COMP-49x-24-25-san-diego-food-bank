from django.http import JsonResponse
from django.views import View
from django.utils.timezone import now
from django.db.models import Count
from django.db.models.functions import TruncYear, TruncMonth, TruncDay
from django.shortcuts import render
from ..models import Log  

def monitoring_dashboard(request):
    """
    Render the monitoring dashboard page template.
    """
    return render(request, "monitoring_page.html")

def get_total_calls(request):
    """
    Returns total calls and a breakdown by the given granularity (time period).
    """
    # Retrieve desired time period level from the request by user
    gran = request.GET.get('granularity', 'year')
    qs = Log.objects.all() # Might want to change this from all call logs to maybe past 12 months, etc.

    if gran == 'year':
        qs = qs.annotate(period=TruncYear('time_started'))
    elif gran == 'month':
        qs = qs.annotate(period=TruncMonth('time_started'))
    elif gran == 'day':
        qs = qs.annotate(period=TruncDay('time_started'))
    else:
        return JsonResponse({
            'error': 'Invalid granularity'}, status=400)
    # Group by time period and count number of logs in each 
    data = qs.values('period') \
                .annotate(count=Count('id')) \
                .order_by('period')

    labels = []
    counts = []
    for entry in data:
        dt = entry['period']
        # Format the label based on time period 
        if gran == 'year':
            label = dt.year
        elif gran == 'month':
            label = dt.strftime('%Y-%m')
        else:
            label = dt.strftime('%Y-%m-%d')
        labels.append(label)
        counts.append(entry['count'])

    total = sum(counts)
    # Return the total metrics as JSON 
    return JsonResponse({
        'total': total,
        'labels': labels,
        'counts': counts,
    })
