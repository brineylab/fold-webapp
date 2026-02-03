from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from bioportal.forms import CustomLoginForm


urlpatterns = [
    path("admin/", admin.site.urls),
    path("console/", include("console.urls")),
    path("api/", include("api.urls")),
    path(
        "login/",
        auth_views.LoginView.as_view(authentication_form=CustomLoginForm),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("jobs.urls")),
]


