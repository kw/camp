from django.conf import settings
from django.contrib import admin
from django.templatetags.static import static
from django.urls import include
from django.urls import path
from django.views.generic.base import RedirectView

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("camp.accounts.urls")),
    path("events/", include("camp.events.urls")),
    path("pages/", include("django.contrib.flatpages.urls")),
    path("characters/", include("camp.character.urls")),
    path("", include("camp.game.urls")),
    # Most pages will use the favicon defined by the template, but for cases
    # where no template is used, at least serve a favicon when asked.
    path("favicon.ico", RedirectView.as_view(url=static("images/favicon.png"))),
]

if settings.DEBUG:
    urlpatterns.insert(0, path("__debug__/", include("debug_toolbar.urls")))
