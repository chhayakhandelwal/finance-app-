from decimal import Decimal
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import SavingsGoal, SavingsContribution
from .serializers import SavingsGoalSerializer
from .services import (
    send_savings_goal_created_email,
    send_contribution_added,
    maybe_send_thresholds,
    send_goal_achieved,
)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def saving_list_create(request):
    # ---------- GET ----------
    if request.method == "GET":
        qs = SavingsGoal.objects.filter(user=request.user).order_by("target_date", "-id")
        return Response(SavingsGoalSerializer(qs, many=True).data)

    # ---------- POST ----------
    serializer = SavingsGoalSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    obj = serializer.save(user=request.user)

    # ✅ ALWAYS send goal created mail
    send_savings_goal_created_email(obj)

    # ✅ If created with initial saved_amount > 0, treat as a contribution + notify
    saved = Decimal(obj.saved_amount or 0)
    target = Decimal(obj.target_amount or 0)

    if saved > 0:
        SavingsContribution.objects.create(
            goal=obj,
            user=request.user,
            amount=saved,
            contribution_date=timezone.localdate(),
        )

        send_contribution_added(obj, saved)
        maybe_send_thresholds(obj)

        if target > 0 and saved >= target:
            send_goal_achieved(obj)

    return Response(SavingsGoalSerializer(obj).data, status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def saving_update_delete(request, pk: int):
    try:
        obj = SavingsGoal.objects.get(pk=pk, user=request.user)
    except SavingsGoal.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    # ---------- DELETE ----------
    if request.method == "DELETE":
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ---------- PUT ----------
    old_saved = Decimal(obj.saved_amount or 0)

    serializer = SavingsGoalSerializer(obj, data=request.data, partial=False)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    updated_obj = serializer.save(user=request.user)

    new_saved = Decimal(updated_obj.saved_amount or 0)
    target = Decimal(updated_obj.target_amount or 0)

    # ✅ Only when saved_amount increased -> "new saving added"
    if new_saved > old_saved:
        delta = new_saved - old_saved

        SavingsContribution.objects.create(
            goal=updated_obj,
            user=request.user,
            amount=delta,
            contribution_date=timezone.localdate(),
        )

        send_contribution_added(updated_obj, delta)
        maybe_send_thresholds(updated_obj)

        if target > 0 and new_saved >= target:
            send_goal_achieved(updated_obj)

    return Response(SavingsGoalSerializer(updated_obj).data)