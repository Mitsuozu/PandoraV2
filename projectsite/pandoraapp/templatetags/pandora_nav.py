from django import template
from ..navigation import access_for

register = template.Library()


@register.simple_tag
def workspace_access(user):
    return access_for(user) if user.is_authenticated else {}


@register.simple_tag(takes_context=True)
def navigation(context, access):
    request = context['request']
    if not request.user.is_authenticated:
        return []
    links = [
        ('Overview', 'home', 'Dashboard', 'dashboard', None),
        ('Sales', 'sale_history', 'Sales', 'receipt', 'sale_history_access'),
        ('Sales', 'warranty_claims', 'Warranty claims', 'shield', 'warranty_access'),
        ('Inventory', 'products', 'Products', 'package', 'catalog_access'),
        ('Inventory', 'inventory_report', 'Stock levels', 'warehouse', 'inventory_access'),
        ('Inventory', 'categories', 'Categories', 'tag', 'category_access'),
        ('Inventory', 'reorder', 'Reorder report', 'alert', 'inventory_access'),
        ('Inventory', 'movement_report', 'Stock movements', 'transfer', 'inventory_access'),
        ('Purchasing', 'purchase_history', 'Purchases', 'cart', 'purchase_history_access'),
        ('Purchasing', 'suppliers', 'Suppliers', 'truck', 'supplier_access'),
        ('Locations', 'branches', 'Branches', 'building', 'branch_access'),
        ('Locations', 'location_map', 'Map', 'map', 'map_access'),
        ('Finance', 'sales_report', 'Sales summary', 'bars', 'financial_access'),
        ('Finance', 'profit_report', 'Profit and loss', 'balance', 'financial_access'),
        ('Finance', 'performance_report', 'Product performance', 'trend', 'financial_access'),
        ('Finance', 'expenses', 'Operating expenses', 'wallet', 'expense_access'),
    ]
    return [(group, 'pandoraapp:' + route, label, icon) for group, route, label, icon, permission
            in links if permission is None or access[permission]]
