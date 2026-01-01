from rest_framework import generics, permissions
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import RegisterSerializer, UserSerializer
from django.conf import settings
from .social import exchange_google_code, exchange_facebook_code, SocialError
from urllib.parse import urlencode
from django.shortcuts import redirect

class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Accept identifier (email/phone/username) + password
        identifier = (
            request.data.get("identifier")
            or request.data.get("email")
            or request.data.get("username")
            or request.data.get("phone")
        )
        password = request.data.get("password")

        if not identifier or not password:
            return Response({"detail": "identifier and password required"}, status=400)

        user = authenticate(request, username=identifier, password=password)

        # Fallback: look up by email/phone, then verify password
        if user is None:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                lookup = {"email": identifier} if "@" in identifier else {"phone": identifier}
                u = User.objects.get(**lookup)
                if u.check_password(password):
                    user = u
            except User.DoesNotExist:
                user = None

        if user is None:
            return Response({"detail": "Invalid credentials"}, status=401)

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
            "roles": user.roles_list(),
        })

class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class SocialStartView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, provider):
        if provider not in ["google", "facebook"]:
            return Response({"detail": "Unsupported provider"}, status=400)

        base_url = request.build_absolute_uri(f"/api/auth/social/{provider}/callback/")
        if provider == "google":
            client_id = settings.GOOGLE_CLIENT_ID
            if not client_id:
                return Response({"detail": "Google not configured"}, status=503)
            params = {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": base_url,
                "scope": "openid email profile",
                "access_type": "online",
                "prompt": "select_account",
            }
            url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
            return Response({"auth_url": url})

        if provider == "facebook":
            client_id = settings.FACEBOOK_APP_ID
            if not client_id:
                return Response({"detail": "Facebook not configured"}, status=503)
            params = {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": base_url,
                "scope": "email,public_profile",
            }
            url = "https://www.facebook.com/v19.0/dialog/oauth?" + urlencode(params)
            return Response({"auth_url": url})


class SocialCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, provider):
        code = request.query_params.get("code")
        if not code:
            return Response({"detail": "Missing code"}, status=400)

        redirect_uri = request.build_absolute_uri()

        try:
            if provider == "google":
                profile = exchange_google_code(code, redirect_uri)
            elif provider == "facebook":
                profile = exchange_facebook_code(code, redirect_uri)
            else:
                return Response({"detail": "Unsupported provider"}, status=400)
        except SocialError as e:
            return Response({"detail": str(e)}, status=400)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        email = profile.get("email")
        username = email or f"{provider}_{profile.get('id')}"
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={"username": username, "role": User.ROLE_CUSTOMER},
        )

        refresh = RefreshToken.for_user(user)
        frontend_redirect = settings.GOOGLE_REDIRECT_FRONTEND if provider == "google" else settings.FACEBOOK_REDIRECT_FRONTEND
        qs = urlencode({"access": str(refresh.access_token), "refresh": str(refresh)})
        return redirect(f"{frontend_redirect}?{qs}")
