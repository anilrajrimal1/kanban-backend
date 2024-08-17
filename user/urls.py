from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from rest_framework import routers
from rest_framework_simplejwt import views as jwt_views

from .views import (
    CustomTokenObtainPairView,
    UserProfileViewSet,
    UserRegisterViewSet,
    UserSignIn,
    activate_user,
    change_password,
    forgot_password,
    reset_passoword,
)

router = routers.DefaultRouter()
router.register(r"sign-up", UserRegisterViewSet, basename="users")
router.register(r"user-profile", UserProfileViewSet, basename="user-profile")

urlpatterns = [
    path("", include(router.urls)),
    path("token/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", jwt_views.TokenRefreshView.as_view(), name="token_refresh"),
    path("sign-in/", UserSignIn.as_view()),
    path(
        "email-verification/<str:uidb64>/<str:token>/",
        activate_user,
        name="email_activate",
    ),
    path("change-password/", change_password, name="change_password"),
    path("forgot-password/", forgot_password, name="forgot_password"),
    path(
        "reset-password/<str:uidb64>/<str:token>/",
        reset_passoword,
        name="reset_password",
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
