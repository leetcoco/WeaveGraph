from django.urls import path
from . import views

app_name = 'fashion'

urlpatterns = [
    path('', views.fashion_design, name='design'),
    path('analyze/', views.analyze_design_network, name='analyze'),
    path('generate/', views.generate_design, name='generate'),
    path('map-v8/', views.map_v8, name='map_v8'),
    path('detect-subject/', views.detect_subject, name='detect_subject'),
    path('downloads/<str:filename>', views.download_file, name='download_file'),
]
