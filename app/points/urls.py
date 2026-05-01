from django.urls import path
from . import views

urlpatterns = [
    path("points/", views.points_view, name='points'),
    path("ai/",     views.ai_recommend_view, name="ai_recommend"),
]