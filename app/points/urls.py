from django.urls import path
from .views import points_view

urlpatterns = [
    path("points/", points_view),
]