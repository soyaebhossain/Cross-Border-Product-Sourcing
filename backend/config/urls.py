from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from . import views

def home(request):
    return JsonResponse({"status": "ok", "message": "API running"})

urlpatterns = [
    path("", home),
    path("admin/dashboard/", admin.site.admin_view(views.admin_dashboard), name="admin-dashboard"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("catalog.urls")),
    path("api/", include("orders.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
