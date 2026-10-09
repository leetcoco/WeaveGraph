from django.urls import path
from . import views

urlpatterns = [
    path('', views.colornetvis, name='colorvis_home'),
    path('colornetvis/', views.colornetvis, name='colornetvis'),
    path('colorspace.png', views.colorspace_png, name='colorspace_png'),
]
