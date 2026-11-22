"""Branch and warranty claim list and add/edit screens."""
from datetime import date

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from . import services
from .models import Branch, Customer, Product, WarrantyClaim
from .supplier_views import fill_coordinates

ROLES = {'Admin', 'Inventory Staff', 'Cashier'}


def _authorize(user, permission):
    return services._authorize(user, ROLES, permission)


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['name', 'contact_number', 'address', 'latitude', 'longitude', 'is_active']
        help_texts = {'latitude': 'Leave blank and Pandora looks the address up on OpenStreetMap.'}
        widgets = {'address': forms.Textarea(attrs={'rows': 3})}


class WarrantyClaimForm(forms.ModelForm):
    new_customer = forms.CharField(max_length=150, required=False, label='Or new customer name',
                                   help_text='Type a name here if the customer is not in the list yet.')
    new_customer_contact = forms.CharField(max_length=50, required=False, label='New customer contact number')

    class Meta:
        model = WarrantyClaim
        fields = ['customer', 'new_customer', 'new_customer_contact', 'product', 'serial_number', 'branch',
                  'issue', 'received_date', 'status', 'resolution']
        widgets = {'received_date': forms.DateInput(attrs={'type': 'date'}),
                   'issue': forms.Textarea(attrs={'rows': 3}), 'resolution': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, can_add_customer=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].required = False
        self.fields['customer'].queryset = Customer.objects.order_by('name')
        self.fields['product'].queryset = Product.objects.order_by('name')
        self.fields['branch'].queryset = Branch.objects.filter(is_active=True).order_by('name')
        if self.instance.branch_id:  # keep an inactive branch selectable on old claims
            self.fields['branch'].queryset |= Branch.objects.filter(pk=self.instance.branch_id)
        if not self.instance.pk:
            self.fields['received_date'].initial = date.today()
        if not can_add_customer:
            del self.fields['new_customer'], self.fields['new_customer_contact']

    def clean(self):
        data = super().clean()
        name = (data.get('new_customer') or '').strip()
        if not data.get('customer') and not name:
            self.add_error('customer', 'Choose a customer or type a new customer name.')
        elif data.get('customer') and name:
            self.add_error('new_customer', 'Choose an existing customer or type a new one, not both.')
        return data

    def save(self, commit=True):
        name = (self.cleaned_data.get('new_customer') or '').strip()
        if name:
            self.instance.customer = Customer.objects.create(
                name=name, contact_number=(self.cleaned_data.get('new_customer_contact') or '').strip())
        return super().save(commit)


@login_required(login_url='/login/')
@require_GET
def branch_list(request):
    user = _authorize(request.user, 'view_branch')
    query = request.GET.get('q', '').strip()[:100]
    status = request.GET.get('status', '')
    rows = Branch.objects.all()
    if query:
        rows = rows.filter(Q(name__icontains=query) | Q(address__icontains=query)
                           | Q(contact_number__icontains=query))
    if status in ('active', 'inactive'):
        rows = rows.filter(is_active=status == 'active')
    else:
        status = ''
    return render(request, 'pandoraapp/branches.html', {
        'page': Paginator(rows.order_by('-is_active', 'name', 'pk'), 25).get_page(request.GET.get('page')),
        'q': query, 'status': status,
        'can_add': user.has_perm('pandoraapp.add_branch'), 'can_edit': user.has_perm('pandoraapp.change_branch')})


@login_required(login_url='/login/')
@require_http_methods(['GET', 'POST'])
def branch_edit(request, pk=None):
    branch = get_object_or_404(Branch, pk=pk) if pk else None
    _authorize(request.user, 'change_branch' if branch else 'add_branch')
    form = BranchForm(request.POST or None, instance=branch)
    if request.method == 'POST' and form.is_valid():
        fill_coordinates(request, form)
        form.save()
        messages.success(request, f'Branch {"updated" if branch else "added"}.')
        return redirect('pandoraapp:branches')
    return render(request, 'pandoraapp/simple_form.html', {
        'form': form, 'title': f'Edit {branch.name}' if branch else 'Add branch',
        'description': 'Branches with an address appear on the map.', 'button': 'Save branch'})


@login_required(login_url='/login/')
@require_GET
def warranty_list(request):
    user = _authorize(request.user, 'view_warrantyclaim')
    query = request.GET.get('q', '').strip()[:100]
    status = request.GET.get('status', '')
    rows = WarrantyClaim.objects.select_related('customer', 'product', 'branch')
    if query:
        rows = rows.filter(Q(serial_number__icontains=query) | Q(customer__name__icontains=query)
                           | Q(product__name__icontains=query) | Q(product__sku__icontains=query))
    if status in dict(WarrantyClaim.STATUSES):
        rows = rows.filter(status=status)
    else:
        status = ''
    return render(request, 'pandoraapp/warranty_claims.html', {
        'page': Paginator(rows.order_by('-received_date', '-pk'), 25).get_page(request.GET.get('page')),
        'q': query, 'status': status, 'statuses': WarrantyClaim.STATUSES,
        'can_add': user.has_perm('pandoraapp.add_warrantyclaim'),
        'can_edit': user.has_perm('pandoraapp.change_warrantyclaim')})


@login_required(login_url='/login/')
@require_http_methods(['GET', 'POST'])
def warranty_edit(request, pk=None):
    claim = get_object_or_404(WarrantyClaim, pk=pk) if pk else None
    user = _authorize(request.user, 'change_warrantyclaim' if claim else 'add_warrantyclaim')
    form = WarrantyClaimForm(request.POST or None, instance=claim,
                             can_add_customer=user.has_perm('pandoraapp.add_customer'))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Warranty claim {"updated" if claim else "added"}.')
        return redirect('pandoraapp:warranty_claims')
    return render(request, 'pandoraapp/simple_form.html', {
        'form': form, 'title': 'Edit warranty claim' if claim else 'New warranty claim',
        'description': 'Track a product a customer brought back for repair or replacement.',
        'button': 'Save claim'})
