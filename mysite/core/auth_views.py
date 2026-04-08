import re
import random

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import IntegrityError, transaction

from .models import PasswordResetOTP


USERNAME_REGEX = re.compile(r"^(?=.*[A-Z])(?=.*\d).+$")
PASSWORD_REGEX = re.compile(r"^(?=.*[A-Z])(?=.*\d).{8,}$")


def _generate_otp():
    return f"{random.randint(100000, 999999)}"


# =========================
# Register
# =========================
@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    User = get_user_model()

    username = (request.data.get("username") or "").strip()
    password = request.data.get("password") or ""

    email = (request.data.get("email") or "").strip()
    first_name = (request.data.get("first_name") or "").strip()
    last_name = (request.data.get("last_name") or "").strip()

    if not username or not password or not email:
        return Response(
            {"message": "username, password and email are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not USERNAME_REGEX.match(username):
        return Response(
            {"message": "Username must contain at least one uppercase letter and one number"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not PASSWORD_REGEX.match(password):
        return Response(
            {"message": "Password must be at least 8 characters long and include one uppercase letter and one number"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(username__iexact=username).exists():
        return Response({"message": "This username is already registered"}, status=status.HTTP_409_CONFLICT)

    # optional: prevent same email reuse
    # if User.objects.filter(email__iexact=email).exists():
    #     return Response({"message": "This email is already registered"}, status=status.HTTP_409_CONFLICT)

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )
    except IntegrityError:
        return Response({"message": "Registration failed"}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "message": "Registration successful",
            "user": {
                "username": user.username,
                "first_name": getattr(user, "first_name", ""),
                "last_name": getattr(user, "last_name", ""),
                "email": getattr(user, "email", ""),
            },
        },
        status=status.HTTP_201_CREATED,
    )
# =========================
# Login
# =========================
@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    User = get_user_model()

    username = (request.data.get("username") or "").strip()
    password = request.data.get("password") or ""

    if not username or not password:
        return Response(
            {"message": "username and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(username__iexact=username)
    except User.DoesNotExist:
        return Response(
            {"message": "Invalid username or password"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.check_password(password):
        return Response(
            {"message": "Invalid username or password"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    refresh = RefreshToken.for_user(user)

    return Response(
        {
            "message": "Login successful",
            "token": str(refresh.access_token),
            "refreshToken": str(refresh),
            "user": {"name": user.username, "username": user.username},
        },
        status=status.HTTP_200_OK,
    )


# =========================
# Profile
# =========================
@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def profile_view(request):
    User = get_user_model()
    u = request.user

    if request.method == "PATCH":
        username = request.data.get("username", None)
        first_name = request.data.get("first_name", None)
        last_name = request.data.get("last_name", None)
        email = request.data.get("email", None)

        errors = {}

        if username is not None:
            username = (username or "").strip()
            if not username:
                errors["username"] = "Username cannot be empty."
            elif User.objects.filter(username__iexact=username).exclude(pk=u.pk).exists():
                errors["username"] = "This username is already taken."
            else:
                u.username = username

        if first_name is not None:
            u.first_name = (first_name or "").strip()

        if last_name is not None:
            u.last_name = (last_name or "").strip()

        if email is not None and hasattr(u, "email"):
            u.email = (email or "").strip()

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            u.save()
        except IntegrityError:
            return Response({"message": "This username is already taken."}, status=status.HTTP_409_CONFLICT)

    joined = ""
    dj = getattr(u, "created_at", None)
    if dj:
        joined = dj.strftime("%B %Y")

    return Response(
        {
            "username": u.username,
            "first_name": getattr(u, "first_name", "") or "",
            "last_name": getattr(u, "last_name", "") or "",
            "email": getattr(u, "email", "") if hasattr(u, "email") else "",
            "joined": joined,
        },
        status=status.HTTP_200_OK,
    )

# =========================
# Change Password (Logged-in)
# =========================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    u = request.user

    old_password = request.data.get("old_password") or ""
    new_password = request.data.get("new_password") or ""
    confirm_password = request.data.get("confirm_password") or ""

    if not old_password or not new_password or not confirm_password:
        return Response(
            {"message": "old_password, new_password and confirm_password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # verify old password
    if not u.check_password(old_password):
        return Response(
            {"message": "Old password is incorrect"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # match new + confirm
    if new_password != confirm_password:
        return Response(
            {"message": "New password and confirm password do not match"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # enforce your password policy
    if not PASSWORD_REGEX.match(new_password):
        return Response(
            {"message": "Password must be at least 8 characters long and include one uppercase letter and one number"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # prevent same password
    if old_password == new_password:
        return Response(
            {"message": "New password must be different from old password"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    u.set_password(new_password)
    u.save()

    return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)
# =========================
# Forgot Password (OTP)
# =========================
@api_view(["POST"])
@permission_classes([AllowAny])
def forgot_send_otp(request):
    User = get_user_model()
    username = (request.data.get("username") or "").strip()
    email = (request.data.get("email") or "").strip()

    if not username or not email:
        return Response(
            {"message": "username and email are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(username__iexact=username)
    except User.DoesNotExist:
        return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    # Strict email match if field exists
    if hasattr(user, "email"):
        saved_email = (getattr(user, "email", "") or "").strip().lower()
        if saved_email and saved_email != email.lower():
            return Response(
                {"message": "Email does not match this username"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    otp = _generate_otp()

    # Invalidate previous OTPs for this username+email
    PasswordResetOTP.objects.filter(username__iexact=username, email__iexact=email).delete()

    PasswordResetOTP.objects.create(
        username=username,
        email=email,
        otp_hash=make_password(otp),
        created_at=timezone.now(),
    )

    subject = "Your Password Reset OTP"
    message = f"Your OTP is {otp}. It is valid for 10 minutes."
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None)

    try:
        send_mail(subject, message, from_email, [email], fail_silently=False)
    except Exception:
        return Response(
            {"message": "Failed to send OTP email. Check email settings."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response({"message": "OTP sent successfully"}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def forgot_verify_otp(request):
    username = (request.data.get("username") or "").strip()
    email = (request.data.get("email") or "").strip()
    otp = (request.data.get("otp") or "").strip()

    if not username or not email or not otp:
        return Response(
            {"message": "username, email and otp are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        rec = PasswordResetOTP.objects.get(username__iexact=username, email__iexact=email)
    except PasswordResetOTP.DoesNotExist:
        return Response(
            {"message": "OTP not found. Please request again."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if rec.is_expired():
        rec.delete()
        return Response(
            {"message": "OTP expired. Please request again."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not check_password(otp, rec.otp_hash):
        return Response({"message": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"message": "OTP verified"}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def forgot_reset_password(request):
    User = get_user_model()

    username = (request.data.get("username") or "").strip()
    email = (request.data.get("email") or "").strip()
    otp = (request.data.get("otp") or "").strip()
    new_password = request.data.get("new_password") or ""

    if not username or not email or not otp or not new_password:
        return Response(
            {"message": "username, email, otp and new_password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not PASSWORD_REGEX.match(new_password):
        return Response(
            {"message": "Password must be at least 8 characters long and include one uppercase letter and one number"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        rec = PasswordResetOTP.objects.get(username__iexact=username, email__iexact=email)
    except PasswordResetOTP.DoesNotExist:
        return Response(
            {"message": "OTP not found. Please request again."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if rec.is_expired():
        rec.delete()
        return Response(
            {"message": "OTP expired. Please request again."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not check_password(otp, rec.otp_hash):
        return Response({"message": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(username__iexact=username)
    except User.DoesNotExist:
        return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    user.set_password(new_password)
    user.save()

    rec.delete()  # OTP one-time use

    return Response({"message": "Password reset successful"}, status=status.HTTP_200_OK)