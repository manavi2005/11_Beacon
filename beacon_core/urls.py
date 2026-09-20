"""Project-level URL configuration for Beacon.

Only routing lives here; each feature app keeps its own urls.py and is included
below, so teammates never edit the same file for their own feature.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("preparation.urls")),
]

# During development, let Django serve uploaded resumes. In production this is
# the web server's job, so the list stays empty.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Branding for the admin site (visible on the login and index pages).
admin.site.site_header = "Beacon Admin - Team Career Coaches"
admin.site.site_title = "Beacon Admin"
admin.site.index_title = "Data model control centre"
