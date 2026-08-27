from django.urls import path

from .views.auth_view import LoginView, RefreshView, LogoutView, CurrentUserView
from .views.register_view import RegistrationView, VerifyRegistrationView, ResendRegisterVerificationCodeView
from .views.forgot_password_view import (
ForgotPasswordView,
VerifyForgotPasswordView,
ResendForgotPasswordVerificationCodeView,
ResetPasswordView
)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RefreshView.as_view(), name="refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/user/", CurrentUserView.as_view(), name="current_user"),

    path("register/", RegistrationView.as_view(), name="register"),
    path("register/verify/", VerifyRegistrationView.as_view(), name="register_verify" ),
    path("register/resend/", ResendRegisterVerificationCodeView.as_view(), name="resend_register_code" ),

    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot_password"),
    path("forgot-password/verify/", VerifyForgotPasswordView.as_view(), name="forgot_password_verify"),
    path("forgot-password/resend/", ResendForgotPasswordVerificationCodeView.as_view(), name="resend_forgot_password_code"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset_password"),
]