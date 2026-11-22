"""REST API at /api/: list, create, read, update and delete for seven Pandora tables.

Sales, purchases, stock movements and expenses are left out on purpose: they change stock and money,
so they only go through the audited services in services.py and expense_services.py.
"""
from django.db.models.deletion import ProtectedError
from rest_framework import serializers, status, viewsets
from rest_framework.filters import SearchFilter
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter

from .geocode import coordinates_for
from .models import Branch, Category, Customer, ExpenseCategory, Product, Supplier, WarrantyClaim


class ModelPermissions(DjangoModelPermissions):
    """Django model permissions from the role groups, including view permission for reads."""
    perms_map = {**DjangoModelPermissions.perms_map,
                 'GET': ['%(app_label)s.view_%(model_name)s'],
                 'HEAD': ['%(app_label)s.view_%(model_name)s']}


def serializer_for(model_class, read_only=()):
    meta = type('Meta', (), {'model': model_class, 'fields': '__all__', 'read_only_fields': read_only})
    return type(f'{model_class.__name__}Serializer', (serializers.ModelSerializer,), {'Meta': meta})


class ProductSerializer(serializer_for(Product, read_only=('current_stock', 'cost_price'))):
    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        # Cashiers may browse the catalog but not see what the store paid.
        if not (request and request.user.has_perm('pandoraapp.change_product')):
            fields.pop('cost_price')
        return fields


class PandoraViewSet(viewsets.ModelViewSet):
    permission_classes = [ModelPermissions]
    filter_backends = [SearchFilter]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({'detail': 'This record is still used by other records, so it cannot be '
                             'deleted. Deactivate it or remove those records first.'},
                            status=status.HTTP_409_CONFLICT)


class LocatedViewSet(PandoraViewSet):
    """Looks up map coordinates from OpenStreetMap when the address changes and none were typed."""

    def perform_create(self, serializer):
        data, old = serializer.validated_data, serializer.instance
        moved = 'address' in data and (old is None or data['address'] != old.address)
        typed = 'latitude' in data or 'longitude' in data
        serializer.save(**(coordinates_for(data['address']) if moved and not typed else {}))

    perform_update = perform_create


def viewset(model_class, base=PandoraViewSet, serializer=None, search=('name',)):
    return type(f'{model_class.__name__}ViewSet', (base,), {
        'queryset': model_class.objects.order_by('pk'),
        'serializer_class': serializer or serializer_for(model_class),
        'search_fields': search})


router = DefaultRouter()
router.register('categories', viewset(Category))
router.register('products', viewset(Product, serializer=ProductSerializer,
                                    search=('sku', 'name', 'brand', 'model')))
router.register('suppliers', viewset(Supplier, LocatedViewSet, search=('name', 'contact_person')))
router.register('expense-categories', viewset(ExpenseCategory))
router.register('branches', viewset(Branch, LocatedViewSet))
router.register('customers', viewset(Customer, LocatedViewSet, search=('name', 'contact_number')))
router.register('warranty-claims', viewset(WarrantyClaim,
                                           search=('serial_number', 'customer__name', 'product__name')))
