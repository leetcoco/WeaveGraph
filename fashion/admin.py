from django.contrib import admin
from .models import (
    PaintingElement,
    GarmentType,
    ElementNetwork,
    FashionDesign,
    NetworkMetrics
)


@admin.register(PaintingElement)
class PaintingElementAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'element_type', 'color_code', 'frequency', 'created_at']
    list_filter = ['element_type']
    search_fields = ['name', 'description']


@admin.register(GarmentType)
class GarmentTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'gender', 'category', 'created_at']
    list_filter = ['gender', 'category']
    search_fields = ['name', 'description']


@admin.register(ElementNetwork)
class ElementNetworkAdmin(admin.ModelAdmin):
    list_display = ['id', 'source', 'target', 'relation_type', 'weight', 'created_at']
    list_filter = ['relation_type']
    search_fields = ['source__name', 'target__name']


@admin.register(FashionDesign)
class FashionDesignAdmin(admin.ModelAdmin):
    list_display = ['id', 'design_id', 'gender', 'garment_type', 'network_score', 'created_at']
    list_filter = ['gender', 'garment_type']
    search_fields = ['design_id']


@admin.register(NetworkMetrics)
class NetworkMetricsAdmin(admin.ModelAdmin):
    list_display = ['element', 'degree_centrality', 'betweenness_centrality',
                    'closeness_centrality', 'pagerank', 'updated_at']
    list_display_links = ['element']
