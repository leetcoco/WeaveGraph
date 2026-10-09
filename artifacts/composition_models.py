"""
中国画结构分解与再组合系统 - 数据模型
"""
from django.db import models
import json


class CompositionAnalysis(models.Model):
    """画作构图分析主表"""
    artifact = models.OneToOneField('Artifact', on_delete=models.CASCADE, related_name='composition_analysis')
    
    # 分析状态
    STATUS_CHOICES = [
        ('pending', '待分析'),
        ('processing', '分析中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # 分析参数
    edge_detection_method = models.CharField(max_length=50, default='canny', verbose_name='边缘检测方法')
    segmentation_method = models.CharField(max_length=50, default='watershed', verbose_name='分割方法')
    region_count = models.IntegerField(default=0, verbose_name='区域数量')
    
    # 结果文件路径
    edge_image = models.ImageField(upload_to='composition/edges/', blank=True, verbose_name='线条提取图')
    segmented_image = models.ImageField(upload_to='composition/segments/', blank=True, verbose_name='区域分割图')
    structure_json = models.TextField(blank=True, verbose_name='结构数据JSON')
    
    # 元数据
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processing_time = models.FloatField(default=0, verbose_name='处理时间(秒)')
    
    class Meta:
        verbose_name = '构图分析'
        verbose_name_plural = '构图分析'
    
    def __str__(self):
        return f"{self.artifact.name} - 构图分析"
    
    @property
    def structure_data(self):
        """获取结构数据"""
        if self.structure_json:
            return json.loads(self.structure_json)
        return None
    
    def set_structure_data(self, data):
        """设置结构数据"""
        self.structure_json = json.dumps(data, ensure_ascii=False)


class StructuralElement(models.Model):
    """结构单元 - 分解后的独立区域"""
    analysis = models.ForeignKey(CompositionAnalysis, on_delete=models.CASCADE, related_name='elements')
    
    # 单元标识
    element_id = models.IntegerField(verbose_name='单元编号')
    name = models.CharField(max_length=100, blank=True, verbose_name='单元名称')
    
    # 语义分类
    SEMANTIC_TYPES = [
        ('mountain', '山体'),
        ('water', '水体'),
        ('tree', '树木'),
        ('rock', '岩石'),
        ('cloud', '云雾'),
        ('building', '建筑'),
        ('figure', '人物'),
        ('sky', '天空'),
        ('ground', '地面'),
        ('flower', '花卉'),
        ('bird', '禽鸟'),
        ('boat', '舟船'),
        ('bridge', '桥梁'),
        ('unknown', '未知'),
    ]
    semantic_type = models.CharField(max_length=20, choices=SEMANTIC_TYPES, default='unknown', verbose_name='语义类型')
    confidence = models.FloatField(default=0, verbose_name='分类置信度')
    
    # 几何属性
    bounding_box = models.CharField(max_length=100, verbose_name='边界框(x,y,w,h)')
    center_x = models.FloatField(verbose_name='中心点X')
    center_y = models.FloatField(verbose_name='中心点Y')
    area = models.IntegerField(verbose_name='面积(像素)')
    perimeter = models.FloatField(verbose_name='周长')
    
    # 形状特征
    aspect_ratio = models.FloatField(verbose_name='长宽比')
    compactness = models.FloatField(verbose_name='紧凑度')
    elongation = models.FloatField(verbose_name='伸长率')
    
    # 颜色特征
    dominant_color = models.CharField(max_length=50, blank=True, verbose_name='主色调')
    color_histogram = models.TextField(blank=True, verbose_name='颜色直方图')
    
    # 层次信息
    layer_order = models.IntegerField(default=0, verbose_name='层次顺序')
    depth_order = models.IntegerField(default=0, verbose_name='深度顺序(近景=0,远景=n)')
    
    # 掩码图像
    mask_image = models.ImageField(upload_to='composition/masks/', blank=True, verbose_name='掩码图')
    isolated_image = models.ImageField(upload_to='composition/isolated/', blank=True, verbose_name='独立图像')
    
    # 空间关系
    adjacent_elements = models.TextField(blank=True, verbose_name='相邻单元ID列表')
    contained_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, 
                                     related_name='contains', verbose_name='被包含于')
    
    class Meta:
        verbose_name = '结构单元'
        verbose_name_plural = '结构单元'
        ordering = ['analysis', 'layer_order', 'depth_order', 'element_id']
    
    def __str__(self):
        return f"{self.analysis.artifact.name} - {self.get_semantic_type_display()} [{self.element_id}]"


class CompositionTemplate(models.Model):
    """构图模板 - 传统美学比例规则"""
    name = models.CharField(max_length=200, verbose_name='模板名称')
    description = models.TextField(blank=True, verbose_name='描述')
    
    # 模板类型
    TEMPLATE_TYPES = [
        ('three_distances', '三远法'),
        ('golden_ratio', '黄金分割'),
        ('rule_thirds', '三分法则'),
        ('symmetric', '对称构图'),
        ('s_curve', 'S形构图'),
        ('diagonal', '对角线构图'),
        ('radial', '放射构图'),
        ('custom', '自定义'),
    ]
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES, verbose_name='模板类型')
    
    # 参考朝代/画家
    dynasty_reference = models.CharField(max_length=50, blank=True, verbose_name='参考朝代')
    artist_reference = models.CharField(max_length=100, blank=True, verbose_name='参考画家')
    
    # 模板规则（JSON格式）
    rules_json = models.TextField(verbose_name='构图规则JSON')
    
    # 视觉示例
    diagram_image = models.ImageField(upload_to='composition/templates/', blank=True, verbose_name='示意图')
    
    # 使用统计
    usage_count = models.IntegerField(default=0, verbose_name='使用次数')
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    
    class Meta:
        verbose_name = '构图模板'
        verbose_name_plural = '构图模板'
    
    def __str__(self):
        return self.name
    
    @property
    def rules(self):
        if self.rules_json:
            return json.loads(self.rules_json)
        return {}
    
    def set_rules(self, rules):
        self.rules_json = json.dumps(rules, ensure_ascii=False)


class RecombinationProject(models.Model):
    """重组项目 - 基于结构单元的再创作"""
    name = models.CharField(max_length=200, verbose_name='项目名称')
    description = models.TextField(blank=True, verbose_name='描述')
    
    # 来源分析
    source_analysis = models.ForeignKey(CompositionAnalysis, on_delete=models.CASCADE, 
                                       related_name='recombinations', verbose_name='源分析')
    
    # 使用的模板
    template = models.ForeignKey(CompositionTemplate, on_delete=models.SET_NULL, 
                                null=True, blank=True, verbose_name='构图模板')
    
    # 项目配置
    config_json = models.TextField(blank=True, verbose_name='配置JSON')
    
    # 状态
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('generating', '生成中'),
        ('completed', '已完成'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # 结果
    result_image = models.ImageField(upload_to='composition/recombinations/', blank=True, verbose_name='生成结果')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = '重组项目'
        verbose_name_plural = '重组项目'
    
    def __str__(self):
        return self.name


class RecombinationElement(models.Model):
    """重组元素配置 - 项目中各元素的放置参数"""
    project = models.ForeignKey(RecombinationProject, on_delete=models.CASCADE, related_name='elements_config')
    
    # 引用的源结构单元
    source_element = models.ForeignKey(StructuralElement, on_delete=models.CASCADE, verbose_name='源单元')
    
    # 变换参数
    position_x = models.FloatField(verbose_name='目标位置X')
    position_y = models.FloatField(verbose_name='目标位置Y')
    scale_x = models.FloatField(default=1.0, verbose_name='X轴缩放')
    scale_y = models.FloatField(default=1.0, verbose_name='Y轴缩放')
    rotation = models.FloatField(default=0, verbose_name='旋转角度(度)')
    
    # 层级
    z_index = models.IntegerField(default=0, verbose_name='Z轴层级')
    
    # 颜色调整
    brightness_adjust = models.FloatField(default=0, verbose_name='亮度调整(-1~1)')
    saturation_adjust = models.FloatField(default=0, verbose_name='饱和度调整(-1~1)')
    opacity = models.FloatField(default=1.0, verbose_name='不透明度(0~1)')
    
    class Meta:
        verbose_name = '重组元素配置'
        verbose_name_plural = '重组元素配置'
        ordering = ['z_index', 'id']
    
    def __str__(self):
        return f"{self.project.name} - {self.source_element.name}"


class StyleTransferConfig(models.Model):
    """风格迁移配置"""
    name = models.CharField(max_length=100, verbose_name='配置名称')
    
    # 参考画作（作为风格源）
    style_reference = models.ForeignKey('Artifact', on_delete=models.SET_NULL, 
                                       null=True, blank=True, related_name='style_configs')
    
    # 风格参数
    brush_style = models.CharField(max_length=50, blank=True, verbose_name='笔法风格')
    ink_density = models.FloatField(default=0.5, verbose_name='墨色浓度')
    color_harmony = models.CharField(max_length=50, default='analogous', verbose_name='色彩调和')
    
    # 笔触纹理
    texture_intensity = models.FloatField(default=0.5, verbose_name='纹理强度')
    edge_softness = models.FloatField(default=0.3, verbose_name='边缘柔化')
    
    class Meta:
        verbose_name = '风格配置'
        verbose_name_plural = '风格配置'
    
    def __str__(self):
        return self.name
