from django.db import models
from django.utils.text import slugify


class PaintingElement(models.Model):
    """画作元素：颜色、图案、纹样等"""
    ELEMENT_TYPES = [
        ('color', '颜色'),
        ('pattern', '图案'),
        ('motif', '纹样'),
        ('texture', '质感'),
    ]

    name = models.CharField(max_length=200, verbose_name='元素名称')
    element_type = models.CharField(max_length=20, choices=ELEMENT_TYPES, verbose_name='元素类型')
    color_code = models.CharField(max_length=10, blank=True, help_text='颜色代码（如果是颜色类型）', verbose_name='颜色代码')
    description = models.TextField(blank=True, verbose_name='描述')
    image = models.ImageField(upload_to='painting_elements/', blank=True, verbose_name='元素图片')
    frequency = models.IntegerField(default=0, verbose_name='出现频率')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '画作元素'
        verbose_name_plural = '画作元素'

    def __str__(self):
        return f"{self.get_element_type_display()}: {self.name}"


class GarmentType(models.Model):
    """服装类型"""
    GENDER_CHOICES = [
        ('male', '男'),
        ('female', '女'),
    ]

    GARMENT_CATEGORIES = [
        ('upper', '上装'),
        ('lower', '下装'),
        ('full_body', '全身装'),
        ('accessory', '配饰'),
    ]

    name = models.CharField(max_length=200, verbose_name='服装名称')
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, verbose_name='性别')
    category = models.CharField(max_length=20, choices=GARMENT_CATEGORIES, verbose_name='服装分类')
    description = models.TextField(blank=True, verbose_name='描述')
    image = models.ImageField(upload_to='garments/', blank=True, null=True, verbose_name='服装图片')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '服装类型'
        verbose_name_plural = '服装类型'

    def __str__(self):
        return f"{self.get_gender_display()} - {self.name}"


class ElementNetwork(models.Model):
    """元素关系网络：复杂网络的边"""
    RELATION_TYPES = [
        ('cooccurrence', '共现'),
        ('aesthetic', '审美关联'),
        ('style_match', '风格匹配'),
    ]

    source = models.ForeignKey(
        PaintingElement,
        on_delete=models.CASCADE,
        related_name='outgoing_relations',
        verbose_name='源元素'
    )
    target = models.ForeignKey(
        PaintingElement,
        on_delete=models.CASCADE,
        related_name='incoming_relations',
        verbose_name='目标元素'
    )
    relation_type = models.CharField(max_length=20, choices=RELATION_TYPES, verbose_name='关系类型')
    weight = models.FloatField(default=1.0, verbose_name='权重')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '元素关系'
        verbose_name_plural = '元素关系'
        unique_together = ['source', 'target', 'relation_type']

    def __str__(self):
        return f"{self.source.name} -> {self.target.name} ({self.get_relation_type_display()})"


class FashionDesign(models.Model):
    """时尚设计记录"""
    design_id = models.CharField(max_length=100, unique=True, verbose_name='设计ID')
    gender = models.CharField(max_length=10, verbose_name='性别')
    garment_type = models.ForeignKey(
        GarmentType,
        on_delete=models.CASCADE,
        verbose_name='服装类型'
    )
    primary_color = models.ForeignKey(
        PaintingElement,
        on_delete=models.CASCADE,
        related_name='primary_designs',
        verbose_name='主色'
    )
    secondary_colors = models.ManyToManyField(
        PaintingElement,
        related_name='secondary_designs',
        verbose_name='配色'
    )
    patterns = models.ManyToManyField(
        PaintingElement,
        related_name='pattern_designs',
        verbose_name='图案'
    )
    design_image = models.ImageField(upload_to='fashion_designs/', verbose_name='设计图片')
    network_score = models.FloatField(default=0.0, verbose_name='网络评分')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '时尚设计'
        verbose_name_plural = '时尚设计'

    def __str__(self):
        return f"设计 {self.design_id}"


class NetworkMetrics(models.Model):
    """网络指标：复杂网络的中心性等指标"""
    element = models.OneToOneField(
        PaintingElement,
        on_delete=models.CASCADE,
        primary_key=True,
        verbose_name='元素'
    )
    degree_centrality = models.FloatField(default=0.0, verbose_name='度中心性')
    betweenness_centrality = models.FloatField(default=0.0, verbose_name='介数中心性')
    closeness_centrality = models.FloatField(default=0.0, verbose_name='接近中心性')
    pagerank = models.FloatField(default=0.0, verbose_name='PageRank')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '网络指标'
        verbose_name_plural = '网络指标'

    def __str__(self):
        return f"{self.element.name} 指标"
