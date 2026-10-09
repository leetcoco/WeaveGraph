from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views
from . import composition_views

urlpatterns = [
    # 主页
    path('', views.home, name='home'),
    
    # 文物相关
    path('artifacts/', views.artifact_list, name='artifact_list'),
    path('artifacts/<slug:slug>/', views.artifact_detail, name='artifact_detail'),
    path('artifacts/<slug:slug>/export/json/', views.export_palette_json, name='export_palette_json'),
    path('artifacts/<slug:slug>/export/png/', views.export_palette_png, name='export_palette_png'),
    
    # 复杂网络分析（功能已移除）
    # path('artifacts/<slug:slug>/network/', views.network_analysis, name='network_analysis'),
    # path('artifacts/<slug:slug>/analyze-network/', views.analyze_network, name='analyze_network'),
    
    # 分类和展览
    path('category/<slug:slug>/', views.category_artifacts, name='category_artifacts'),
    path('exhibition/<slug:slug>/', views.exhibition_detail, name='exhibition_detail'),
    
    # 用户认证
    path('register/', views.user_register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
    path('profile/', views.user_profile, name='profile'),
    
    # 色彩统计
    path('color-stats/', views.color_stats, name='color_stats'),
    
    # 构图分析
    path('composition/', composition_views.composition_dashboard, name='composition_dashboard'),
    path('composition/list/', composition_views.composition_list, name='composition_list'),
    path('composition/analyze/<slug:slug>/', composition_views.composition_analyze, name='composition_analyze'),
    path('composition/detail/<int:analysis_id>/', composition_views.composition_detail, name='composition_detail'),
    path('composition/elements/<int:analysis_id>/', composition_views.composition_elements, name='composition_elements'),
    path('composition/editor/<int:analysis_id>/', composition_views.composition_editor, name='composition_editor'),
    path('composition/generate/', composition_views.composition_generate, name='composition_generate'),
    
    # 模板
    path('templates/', composition_views.template_list, name='template_list'),
    path('templates/<int:template_id>/', composition_views.template_detail, name='template_detail'),
    
    # API
    path('api/analysis/<int:analysis_id>/status/', composition_views.api_analysis_status, name='api_analysis_status'),
    path('api/analysis/<int:analysis_id>/regions/', composition_views.api_analysis_regions, name='api_analysis_regions'),
    path('api/template/<int:template_id>/layout/', composition_views.api_template_layout, name='api_template_layout'),
    path('api/auto-layout/', composition_views.api_auto_layout, name='api_auto_layout'),
]
