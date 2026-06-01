from rest_framework import viewsets, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication
from apps.activities.models import Activity
from apps.activities.serializers import ActivitySerializer

class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    authentication_classes = (JWTAuthentication,)
    filterset_fields = ['is_free']
    ordering_fields = ['created_at', 'price']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]
