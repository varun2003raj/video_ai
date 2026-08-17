from django.urls import path
from .views import (
    DocumentToVideoView,
    HealthView,
    JobStatusView,
    VideoStreamView,
)

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("convert/", DocumentToVideoView.as_view(), name="convert"),
    path("jobs/<str:job_id>/", JobStatusView.as_view()),
    path("jobs/<str:job_id>/video/",VideoStreamView.as_view(),),
]
