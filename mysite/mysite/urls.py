from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # ✅ All API routes live in core/urls.py
    path("api/", include("core.urls")),
]