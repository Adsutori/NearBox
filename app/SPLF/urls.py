from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", views.landing, name="landing"),
    path("map/", views.index, name="index"),
    path("api/", include("points.urls")),
]
