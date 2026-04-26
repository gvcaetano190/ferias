from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView


urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard:home", permanent=False)),
    path("admin/", admin.site.urls),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", include(("apps.dashboard.urls", "dashboard"), namespace="dashboard")),
    path("accesses/", include(("apps.accesses.urls", "accesses"), namespace="accesses")),

    path("block/", include(("apps.block.urls", "block"), namespace="block")),
    path("passwords/", include(("apps.passwords.urls", "passwords"), namespace="passwords")),
    path("sync/", include(("apps.sync.urls", "sync"), namespace="sync")),
]
