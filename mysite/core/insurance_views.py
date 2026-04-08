# core/views_insurance.py  (or keep inside core/views.py)
from django.db import models
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import InsurancePolicy
from .serializers import InsurancePolicySerializer


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def insurance_list_create(request):
    """
    GET  /api/insurance/  -> list current user's policies
    POST /api/insurance/  -> create policy for current user
    """
    if request.method == "GET":
        # Optional query params:
        #   ?q=life (search by name/policy_number)
        #   ?ordering=end_date or -end_date
        q = (request.query_params.get("q") or "").strip()
        ordering = request.query_params.get("ordering") or "end_date"

        qs = InsurancePolicy.objects.filter(user=request.user)

        if q:
            # Avoid importing Q unless you need it; simple icontains filter:
            qs = qs.filter(models.Q(name__icontains=q) | models.Q(policy_number__icontains=q))  # noqa

        # Safe ordering allowlist
        allowed_orderings = {"end_date", "-end_date", "created_at", "-created_at", "name", "-name"}
        if ordering not in allowed_orderings:
            ordering = "end_date"

        qs = qs.order_by(ordering, "-id")
        serializer = InsurancePolicySerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # POST
    serializer = InsurancePolicySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    policy = serializer.save(user=request.user)
    return Response(InsurancePolicySerializer(policy).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def insurance_detail(request, pk):
    """
    GET    /api/insurance/<id>/  -> retrieve policy (only owner)
    PUT    /api/insurance/<id>/  -> full update (only owner)
    PATCH  /api/insurance/<id>/  -> partial update (only owner)
    DELETE /api/insurance/<id>/  -> delete (only owner)
    """
    try:
        policy = InsurancePolicy.objects.get(pk=pk, user=request.user)
    except InsurancePolicy.DoesNotExist:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(InsurancePolicySerializer(policy).data, status=status.HTTP_200_OK)

    if request.method in ("PUT", "PATCH"):
        serializer = InsurancePolicySerializer(
            policy,
            data=request.data,
            partial=(request.method == "PATCH"),
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()  # user stays same (owner)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # DELETE
    policy.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)