from django.urls import path
from . import views

urlpatterns = [
    path("points/", views.points_view, name='points'),
    path("points/stream/",  views.points_stream_view, name='points_stream'),
    path("ai/",     views.ai_recommend_view, name="ai_recommend"),
]