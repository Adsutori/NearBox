from django.shortcuts import render

def index(request):
    return render(request, 'index.html')

def landing(request):
    return render(request, "landing.html")

