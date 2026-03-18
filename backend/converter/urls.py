from django.urls import path

from .views import DocumentToVideoView, HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("convert/", DocumentToVideoView.as_view(), name="convert"),
]
