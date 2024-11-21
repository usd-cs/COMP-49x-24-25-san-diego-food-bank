from django.shortcuts import render, HttpResponse

# Create your views here.
def hello_page(request):
    return HttpResponse("Hello World!")
