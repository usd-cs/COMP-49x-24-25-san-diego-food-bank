from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import FAQ, Tag
from .forms import FAQForm
import json
from django.http import HttpResponse
from twilio.twiml.voice_response import VoiceResponse, Gather, Say


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
    """
    Display the FAQ page.

    This view retrieves FAQs from the database and displays them on a page. Admins can
    search for FAQs or filter them by their assigned tag. All available tags are also displayed
    for the admins to select.
    """
    query = request.GET.get('q')
    selected_tag = request.GET.get('tag', '')

    # Filter FAQs based on the search query
    if query:
        faqs = FAQ.objects.filter(Q(question__icontains=query) | Q(answer__icontains=query))
    else:
        # Retrieve all FAQs and update the view if no search query is specified
        faqs = FAQ.objects.all()

    if selected_tag:
        faqs = faqs.filter(tags__id=selected_tag)

    tags = Tag.objects.all()

    # Render FAQ page with the FAQs, search query, and tags
    return render(request, 'faq_page.html', {"faqs": faqs, "query": query, "tags": tags,
                  "selected_tag": int(selected_tag) if selected_tag else None, })


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

@csrf_exempt
def answer_call(request):
    """
    Brief greeting upon answering incoming phone calls.
    """
    resp = VoiceResponse()
    resp.say("Thank you for calling!")
    return HttpResponse(str(resp), content_type='text/xml')

@csrf_exempt
def speech_to_text(request):
    """
    Converts speech input to text.
    """
    caller_response = VoiceResponse()
    gather = Gather(input='speech', action='/completed/')
    caller_response.append(gather)
    return HttpResponse(str(caller_response), content_type='text/xml')

@csrf_exempt
def completed(request):
    speech_input = request.GET.get('SpeechResult', '')
    return HttpResponse(f"Speech input received: {speech_input}", content_type='text/plain')

@csrf_exempt
def twilio_webhook(request):
    """
    Properly handle incoming Twilio webhook requests to process user intent. 

    This method checks for a POST request with a JSON payload that contains the keys 
    for the current task and user input details. Based on the "CurrentTask", it determines 
    the appropriate response action. It then returns a JSON response with the appropriate Twilio
    actions for the Twilio AI Assistant to execute.
    """
    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        # Extract the task and intent info from the payload
        current_task = payload.get("CurrentTask", "")
        user_input = payload.get("Field", {}).get("user_input", "")

        # Example template 
        if current_task == 'faq_query':
            answer = " " # Need to replace later with actual FAQ lookup logic
            actions = [
                {"say": answer},
                {"say": "Did that answer your question?"},
                {"listen": True}
            ]
        else:
            actions = [
                {"say": "I didn't understand that. Could you please rephrase?"},
                {"listen": True}
            ]
        return JsonResponse({"actions": actions}) # JSON response for actions to be executed
    else:
        return JsonResponse({"error": "Method not allowed"}, status=405)
