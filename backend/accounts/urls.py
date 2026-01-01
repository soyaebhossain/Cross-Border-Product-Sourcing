from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import RegisterView, LoginView, MeView, SocialStartView, SocialCallbackView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("social/<str:provider>/start/", SocialStartView.as_view(), name="social_start"),
    path("social/<str:provider>/callback/", SocialCallbackView.as_view(), name="social_callback"),
]
