from django.http import JsonResponse
from django.views import View
from django.utils import timezone
from django.utils.timezone import now
from django.db.models import Count
from django.db.models.functions import TruncYear, TruncMonth, TruncDay
from django.shortcuts import render
from zoneinfo import ZoneInfo
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

def get_call_language(request):
    """
    Returns the count of calls grouped by language (english or spanish)
    """
    gran = request.GET.get('granularity', 'year')
    pst = ZoneInfo("America/Los_Angeles")
    now = timezone.now().astimezone(pst)
    qs = Log.objects.all()

    if gran == 'year':
        qs = qs.filter(time_started__year=now.year)
    elif gran == 'month':
        qs = qs.filter(time_started__year=now.year, time_started__month=now.month)
    elif gran == 'day':
        qs = qs.filter(time_started__date=now.date())
    
    else: 
        return JsonResponse({"error": "Invalid"}, status=400)
    
    # count by language
    data = qs.values('language').annotate(count=Count('id'))
    
    counts = {'en': 0, 'es': 0}
    for row in data:
        counts[row['language']] = row['count']

    return JsonResponse({
        'labels': ['English', 'Spanish'],
        'counts': [counts['en'], counts['es']],
    })

def get_calls_forwarded(request):
    """
    Returns counts of forwarded calls split by caller's request vs. automatic (based on strikes).
    """
    qs = Log.objects.filter(forwarded=True)
    pst = ZoneInfo("America/Los_Angeles")
    now = timezone.now().astimezone(pst)
    gran = request.GET.get('granularity', 'year')

    if gran == 'year':
        qs = qs.filter(time_started__year=now.year)
    elif gran == 'month':
        qs = qs.filter(time_started__year=now.year, time_started__month=now.month)
    elif gran == 'day':
        qs = qs.filter(time_started__date=now.date())

    data = (
        qs.values('forwarded_reason')
          .annotate(count=Count('id'))
          .order_by('-count')
    )

    labels, counts = [], []
    total = 0
    for row in data:
        labels.append(
            "Caller Requested" if row['forwarded_reason']=='caller'
            else "Automatic"
        )
        counts.append(row['count'])
        total += row['count']

    return JsonResponse({
        'total': total,
        'labels': labels,
        'counts': counts,
    })

def get_time_of_day(request):
    """
    Returns the count of calls grouped by time of day.
    """

    gran = request.GET.get('granularity', 'year')
    qs = Log.objects.all()
    
    pst = ZoneInfo("America/Los_Angeles")
    now = timezone.now().astimezone(pst)

    if gran == 'year':
        qs = qs.filter(time_started__year=now.year)
    elif gran == 'month':
        qs = qs.filter(time_started__year=now.year, time_started__month=now.month)
    elif gran == 'day':
        qs = qs.filter(time_started__date=now.date())
    else:
        return JsonResponse({'error': 'Invalid granularity'}, status=400)
    
    buckets = {
        "8am-12pm": 0,
        "12pm-4pm": 0,
        "4pm-8pm": 0,
        "8pm-8am": 0
    }
    
    for entry in qs:
        ts = entry.time_started
        ts_pst = ts.astimezone(pst)
        hour = ts_pst.hour

        if 8 <= hour < 12:
            bucket = "8am-12pm"
        elif 12 <= hour < 16:
            bucket = "12pm-4pm"
        elif 16 <= hour < 20:
            bucket = "4pm-8pm"
        else:
            bucket = "8pm-8am"

        buckets[bucket] += 1
    
    labels = list(buckets.keys())
    counts = list(buckets.values())

    return JsonResponse({"labels": labels, "counts": counts})
