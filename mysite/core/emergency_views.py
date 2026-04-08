from decimal import Decimal
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import EmergencyFund, EmergencyFundContribution
from .serializers import EmergencyFundSerializer
from .services import (
    send_emergency_success_email,
    send_emergency_created_email,
)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def emergency_list_create(request):
    """
    GET  /api/emergency/  -> list current user's emergency funds
    POST /api/emergency/  -> create a fund for current user
    """
    if request.method == "GET":
        funds = EmergencyFund.objects.filter(user=request.user).order_by("-id")
        serializer = EmergencyFundSerializer(funds, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # POST
    serializer = EmergencyFundSerializer(data=request.data)
    if serializer.is_valid():
        fund = serializer.save(user=request.user)

        # Optional:
        # If created with initial saved_amount > 0, treat it as first contribution
        initial_saved = Decimal(str(fund.saved_amount or 0))
        if initial_saved > 0:
            EmergencyFundContribution.objects.create(
                user=request.user,
                emergency_fund=fund,
                amount=initial_saved,
                contribution_date=timezone.localdate(),
            )
            fund.last_contribution_at = timezone.now()
            fund.save(update_fields=["last_contribution_at"])

        # ✅ send created email even if saved_amount = 0
        send_emergency_created_email(fund)

        return Response(EmergencyFundSerializer(fund).data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def emergency_update_delete(request, pk):
    """
    PUT    /api/emergency/<pk>/  -> update current user's fund
    DELETE /api/emergency/<pk>/  -> delete current user's fund

    ✅ If saved_amount increases: update last_contribution_at and send success email.
    """
    try:
        fund = EmergencyFund.objects.get(pk=pk, user=request.user)
    except EmergencyFund.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "PUT":
        old_saved = Decimal(str(fund.saved_amount or 0))

        serializer = EmergencyFundSerializer(fund, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        updated = serializer.save()
        new_saved = Decimal(str(updated.saved_amount or 0))

        # ✅ Saving increased => treat as contribution
        if new_saved > old_saved:
            added_amount = new_saved - old_saved

            updated.last_contribution_at = timezone.now()
            updated.save(update_fields=["last_contribution_at"])

            EmergencyFundContribution.objects.create(
                user=request.user,
                emergency_fund=updated,
                amount=added_amount,
                contribution_date=timezone.localdate(),
            )

            send_emergency_success_email(updated, added_amount)

        return Response(EmergencyFundSerializer(updated).data, status=status.HTTP_200_OK)

    # DELETE
    fund.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)