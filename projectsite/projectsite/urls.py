from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import TemplateView

from pandoraapp.api import router

urlpatterns = [
    # Served by Django at the root (not /static/) so the service worker can control every page.
    path('manifest.webmanifest', TemplateView.as_view(template_name='pandoraapp/manifest.webmanifest',
         content_type='application/manifest+json'), name='manifest'),
    path('sw.js', TemplateView.as_view(template_name='pandoraapp/sw.js',
         content_type='text/javascript'), name='service_worker'),
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='pandoraapp/login.html',
         next_page='pandoraapp:home'), name='login'),
    path('accounts/', include('allauth.urls')),  # Google/GitHub sign-in callbacks
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('', include('pandoraapp.urls')),
]
