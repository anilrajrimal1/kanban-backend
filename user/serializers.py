from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _
from requests.exceptions import HTTPError
from rest_framework import serializers, exceptions
from .models import UserProfile

import datetime

try:
    from allauth.account import app_settings as allauth_settings
    from allauth.socialaccount.helpers import complete_social_login
    from allauth.socialaccount.models import SocialAccount
    from allauth.socialaccount.providers.base import AuthProcess
except ImportError:
    raise ImportError("allauth needs to be added to INSTALLED_APPS.")
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email", "username", "password"]
        extra_kwargs = {
            "email": {"write_only": True, "required": True},
            "username": {"write_only": True, "required": True},
            "password": {"write_only": True, "required": True},
            "first_name": {"write_only": True, "required": True},
            "last_name": {"write_only": True, "required": False},
            "date_joined": {"write_only": True, "required": False},
        }


class UserProfileSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = "__all__"

    def get_is_active(self, obj):
        status = obj.user.is_active
        return status

    def get_username(self, obj):
        username = obj.user.username
        return username


# serializers for social login (facebook and google), remove all code below this if you don't need social login
class SocialLoginSerializer(serializers.Serializer):
    access_token = serializers.CharField(required=False, allow_blank=True)
    code = serializers.CharField(required=False, allow_blank=True)
    id_token = serializers.CharField(required=False, allow_blank=True)

    def _get_request(self):
        request = self.context.get("request")
        if not isinstance(request, HttpRequest):
            request = request._request
        return request

    def get_social_login(self, adapter, app, token, response):
        """
        :param adapter: allauth.socialaccount Adapter subclass.
            Usually OAuthAdapter or Auth2Adapter
        :param app: `allauth.socialaccount.SocialApp` instance
        :param token: `allauth.socialaccount.SocialToken` instance
        :param response: Provider's response for OAuth1. Not used in the
        :returns: A populated instance of the
            `allauth.socialaccount.SocialLoginView` instance
        """
        request = self._get_request()
        social_login = adapter.complete_login(request, app, token, response=response)
        social_login.token = token
        return social_login

    def set_callback_url(self, view, adapter_class):
        # first set url from view
        self.callback_url = getattr(view, "callback_url", None)
        if not self.callback_url:
            # auto generate base on adapter and request
            try:
                self.callback_url = reverse(
                    viewname=adapter_class.provider_id + "_callback",
                    request=self._get_request(),
                )
            except NoReverseMatch:
                raise serializers.ValidationError(
                    _("Define callback_url in view"),
                )

    def validate(self, attrs):
        view = self.context.get("view")
        request = self._get_request()

        if not view:
            raise serializers.ValidationError(
                _("View is not defined, pass it as a context variable"),
            )

        adapter_class = getattr(view, "adapter_class", None)
        if not adapter_class:
            raise serializers.ValidationError(_("Define adapter_class in view"))

        adapter = adapter_class(request)
        app = adapter.get_provider().get_app(request)

        # More info on code vs access_token
        # http://stackoverflow.com/questions/8666316/facebook-oauth-2-0-code-and-token

        access_token = attrs.get("access_token")
        code = attrs.get("code")
        # Case 1: We received the access_token
        if access_token:
            tokens_to_parse = {"access_token": access_token}
            token = access_token
            # For sign in with apple
            id_token = attrs.get("id_token")
            if id_token:
                tokens_to_parse["id_token"] = id_token

        # Case 2: We received the authorization code
        elif code:
            self.set_callback_url(view=view, adapter_class=adapter_class)
            self.client_class = getattr(view, "client_class", None)

            if not self.client_class:
                raise serializers.ValidationError(
                    _("Define client_class in view"),
                )

            provider = adapter.get_provider()
            scope = provider.get_scope(request)
            client = self.client_class(
                request,
                app.client_id,
                app.secret,
                adapter.access_token_method,
                adapter.access_token_url,
                self.callback_url,
                scope,
                scope_delimiter=adapter.scope_delimiter,
                headers=adapter.headers,
                basic_auth=adapter.basic_auth,
            )
            token = client.get_access_token(code)
            access_token = token["access_token"]
            tokens_to_parse = {"access_token": access_token}

            # If available we add additional data to the dictionary
            for key in ["refresh_token", "id_token", adapter.expires_in_key]:
                if key in token:
                    tokens_to_parse[key] = token[key]
        else:
            raise serializers.ValidationError(
                _("Incorrect input. access_token or code is required."),
            )

        social_token = adapter.parse_token(tokens_to_parse)
        social_token.app = app

        try:
            login = self.get_social_login(adapter, app, social_token, token)
            complete_social_login(request, login)
        except HTTPError:
            raise serializers.ValidationError(_("Incorrect value"))

        if not login.is_existing:
            # We have an account already signed up in a different flow
            # with the same email address: raise an exception.
            # This needs to be handled in the frontend. We can not just
            # link up the accounts due to security constraints
            if allauth_settings.UNIQUE_EMAIL:
                # Do we have an account already with this email address?
                account_exists = (
                    get_user_model()
                    .objects.filter(
                        email=login.user.email,
                    )
                    .exists()
                )
                user = get_user_model().objects.filter(email=login.user.email)
                token, created = Token.objects.get_or_create(user=user[0])
                if account_exists:
                    attrs["user"] = user[0]

                    return attrs

            # login.lookup()
            # login.save(request, connect=True)

        attrs["user"] = login.account.user
        return attrs


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    source:https://stackoverflow.com/questions/56978424/django-rest-framework-custom-jwt-authentication
    """

    def validate(self, attrs):
        username_or_email = attrs.get("username", None)
        password = attrs.get("password", None)
        if not password or not username_or_email:
            error_message = "username/email or password is missing."
            error_name = "invalid_credentials"
            raise exceptions.AuthenticationFailed(error_message, error_name)
        if User.objects.filter(username=username_or_email).exists():
            user = User.objects.filter(username=username_or_email)[0]
        elif User.objects.filter(email=username_or_email).exists():
            user = User.objects.filter(email=username_or_email)[0]
            attrs["username"] = user.username
        else:
            error_message = "Account with this username/email does not exists."
            error_name = "invalid_username/email"
            raise exceptions.AuthenticationFailed(error_message, error_name)
        if not user.check_password(password):
            error_message = "Incorrect Password"
            error_name = "password"
            raise exceptions.AuthenticationFailed(error_message, error_name)
        # update last_login after getting token
        user.last_login = datetime.datetime.now(datetime.timezone.utc)
        user.save()
        return super().validate(attrs)
