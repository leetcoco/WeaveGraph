from django.db import models
from django.utils.text import slugify
import re

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name='分类名称')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='URL标识')
    description = models.TextField(blank=True, verbose_name='分类描述')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '分类'
        verbose_name_plural = '分类'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Exhibition(models.Model):
    title = models.CharField(max_length=200, verbose_name='展览标题')
    slug = models.SlugField(max_length=200, unique=True, verbose_name='URL标识')
    description = models.TextField(verbose_name='展览描述')
    image = models.ImageField(upload_to='exhibitions/', blank=True, verbose_name='封面图片')
    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')
    is_active = models.BooleanField(default=True, verbose_name='是否显示')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '专题展览'
        verbose_name_plural = '专题展览'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class Artifact(models.Model):
    name = models.CharField(max_length=200, verbose_name='文物名称')
    slug = models.SlugField(max_length=200, unique=True, verbose_name='URL标识')
    description = models.TextField(verbose_name='文物描述')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name='分类')
    era = models.CharField(max_length=100, verbose_name='年代')
    color = models.CharField(max_length=50, verbose_name='颜色')
    image = models.ImageField(upload_to='artifacts/', verbose_name='文物图片')
    image_thumbnail = models.ImageField(upload_to='artifacts/thumbnails/', blank=True, verbose_name='缩略图')
    exhibition = models.ForeignKey(Exhibition, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='所属展览')
    material = models.CharField(max_length=100, blank=True, verbose_name='材质')
    dimensions = models.CharField(max_length=200, blank=True, verbose_name='尺寸')
    collection_number = models.CharField(max_length=100, blank=True, verbose_name='收藏编号')
    is_active = models.BooleanField(default=True, verbose_name='是否显示')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    color_palette = models.TextField(blank=True, null=True, verbose_name='主色调')
    external_image = models.URLField(blank=True, null=True, verbose_name='外部图片地址')

    class Meta:
        verbose_name = '文物'
        verbose_name_plural = '文物'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def parsed_color_palette(self):
        """解析 JSON 格式的调色板数据"""
        if not self.color_palette:
            return []
        try:
            import json
            return json.loads(self.color_palette)
        except:
            return []

    @property
    def era_display(self):
        value = (self.era or "").strip()
        if not value:
            return "未知"
        lower = value.lower()
        if "qing" in lower:
            return "清代"
        if "ming" in lower:
            return "明代"
        if "yuan" in lower:
            return "元代"
        if "northern song" in lower:
            return "北宋"
        if "southern song" in lower:
            return "南宋"
        if "song" in lower:
            return "宋代"
        if "tang" in lower:
            return "唐代"
        if "han" in lower:
            return "汉代"
        if "jin dynasty" in lower:
            return "金代"
        if "liao" in lower:
            return "辽"
        if "sui" in lower:
            return "隋"
        chinese_pairs = [
            ("南宋", "南宋"),
            ("北宋", "北宋"),
            ("五代", "五代"),
            ("秦", "秦"),
            ("汉", "汉代"),
            ("唐", "唐代"),
            ("宋", "宋代"),
            ("元", "元代"),
            ("明", "明代"),
            ("清", "清代"),
            ("晋", "晋"),
            ("隋", "隋"),
            ("辽", "辽"),
            ("金", "金代"),
        ]
        for key, label in chinese_pairs:
            if key in value:
                return label
        years = re.findall(r"\d{3,4}", value)
        for y in years:
            try:
                year = int(y)
            except Exception:
                continue
            if 1644 <= year <= 1911:
                return "清代"
            if 1368 <= year <= 1644:
                return "明代"
            if 1271 <= year <= 1368:
                return "元代"
            if 960 <= year <= 1279:
                return "宋代"
            if 618 <= year <= 907:
                return "唐代"
        if years:
            try:
                first = int(years[0])
                if first <= 1911:
                    return "古代"
                return "近现代"
            except Exception:
                pass
        return "未知"
