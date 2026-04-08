from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Income
from .serializers import IncomeSerializer


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def income_list_create(request):
    if request.method == "GET":
        qs = Income.objects.filter(user=request.user).order_by("-income_date", "-id")
        return Response(IncomeSerializer(qs, many=True).data)

    serializer = IncomeSerializer(data=request.data)
    if serializer.is_valid():
        income_date = serializer.validated_data.get("income_date") or timezone.localdate().replace(day=1)
        obj = serializer.save(
            user=request.user,
            income_date=income_date,
        )
        return Response(IncomeSerializer(obj).data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def income_update_delete(request, pk: int):
    try:
        obj = Income.objects.get(pk=pk, user=request.user)
    except Income.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = IncomeSerializer(obj, data=request.data, partial=False)
    if serializer.is_valid():
        income_date = serializer.validated_data.get("income_date") or obj.income_date
        serializer.save(
            user=request.user,
            income_date=income_date,
        )
        return Response(serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)