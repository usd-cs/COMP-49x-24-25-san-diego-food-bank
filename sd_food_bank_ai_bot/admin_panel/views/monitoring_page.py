from django.http import JsonResponse
from django.views import View
from django.utils import timezone
from django.utils.timezone import now
from django.db.models import Count, Avg
from django.db.models.functions import TruncYear, TruncMonth, TruncDay
from django.shortcuts import render
from zoneinfo import ZoneInfo
from ..models import Log
from collections import defaultdict
from datetime import timedelta


def monitoring_dashboard(request):
    """
    Render the monitoring dashboard page template.
    """
    return render(request, "monitoring_page.html")

def filter_by_topic_qs(qs, topic):
    """Filters QuerySet by topic if possible (used before .values())."""
    if topic == "All" or not topic:
        return qs
    return qs.filter(**{f"intents__has_key": topic})

def filter_by_topic_list(qs, topic):
    """Filters a list of logs (for manual iteration cases)."""
    if topic == "All" or not topic:
        return qs

    def topic_filter(log):
        if not log.intents:
            return False
        if topic == "faq":
            return "faq" in log.intents and log.intents["faq"]
        return topic in log.intents

    return [log for log in qs if topic_filter(log)]


def get_total_calls(request):
    """
    Returns total calls and a breakdown by the given granularity (time period).
    """
    # Retrieve desired time period level from the request by user
    gran = request.GET.get('granularity', 'year')
    topic = request.GET.get('topic')
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
    
    if topic and topic != "All":
        qs = filter_by_topic_qs(qs, topic)

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
    topic = request.GET.get('topic')
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
    
    if topic and topic != "All":
        qs = filter_by_topic_qs(qs, topic)

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
    topic = request.GET.get('topic')
    pst = ZoneInfo("America/Los_Angeles")
    now = timezone.now().astimezone(pst)
    gran = request.GET.get('granularity', 'year')

    if gran == 'year':
        qs = qs.filter(time_started__year=now.year)
    elif gran == 'month':
        qs = qs.filter(time_started__year=now.year, time_started__month=now.month)
    elif gran == 'day':
        qs = qs.filter(time_started__date=now.date())

    if topic and topic != "All":
        qs = filter_by_topic_qs(qs, topic)

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
    topic = request.GET.get('topic')
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
    
    if topic and topic != "All":
        qs = filter_by_topic_list(qs, topic)

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

def get_reason_for_calling(request):
    """
    Returns the count of calls grouped by the users reason for calling.
    """

    gran = request.GET.get('granularity', 'year')
    topic = request.GET.get('topic')
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
    

    # Only filter topic AFTER time filtering
    logs = list(qs)
    if topic and topic != "All":
        logs = filter_by_topic_list(logs, topic)

    intent_counts = defaultdict(int)
    total = 0

    for log in logs:
        intents = log.intents or {}

        if topic == "faq":
            faq_data = intents.get("faq", {})
            if isinstance(faq_data, dict):
                for question, count in faq_data.items():
                    if isinstance(count, int):
                        intent_counts[question] += count
                        total += count
        else:
            if topic == "All":
                for key, value in intents.items():
                    if isinstance(value, dict):
                        count = len(value)
                    else:
                        count = int(value)
                    intent_counts[key] += count
                    total += count
            elif topic in intents:
                value = intents[topic]
                if isinstance(value, dict):
                    count = len(value)
                else:
                    count = int(value)
                intent_counts[topic] += count
                total += count

    return JsonResponse({
        "labels": list(intent_counts.keys()),
        "counts": list(intent_counts.values()),
        "total": total,
        "type": topic,
    })

def get_avg_length(request):
    """
    Returns average call length and a breakdown by the given granularity (time period).
    """
    # Retrieve desired time period level from the request by user
    gran = request.GET.get('granularity', 'year')
    topic = request.GET.get('topic')
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
    
    if topic and topic != "All":
        qs = filter_by_topic_qs(qs, topic)

    # Group by time period and count number of logs in each 
    data = qs.values('period') \
                .annotate(avg_length=Avg('length_of_call')) \
                .order_by('period')

    labels = []
    avg_lengths = []
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
        avg_lengths.append(entry['avg_length'].total_seconds())

    total_avg_lengths = qs.aggregate(avg_length=Avg('length_of_call'))['avg_length']
    if total_avg_lengths is not None:
        total_avg_lengths = str(timedelta(seconds=int(total_avg_lengths.total_seconds())))
    else:
        total_avg_lengths = "00:00:00"
    
    # Return the total metrics as JSON 
    return JsonResponse({
        'total_average_lengths': total_avg_lengths,
        'labels': labels,
        'average_lengths': avg_lengths,
    })