from django.contrib import admin
from .models import Artifact, Category, Exhibition

@admin.register(Artifact)
class ArtifactAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'era', 'color', 'created_at']
    list_filter = ['category', 'era', 'color']
    search_fields = ['name', 'description']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']

@admin.register(Exhibition)
class ExhibitionAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'start_date', 'end_date', 'is_active']
