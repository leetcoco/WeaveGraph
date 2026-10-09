"""
中国画结构分解与再组合系统 - 视图和API
"""
import os
import json
import time
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.conf import settings
from django.db import transaction
import threading

from .models import Artifact
from .composition_models import (
    CompositionAnalysis, StructuralElement,
    CompositionTemplate, RecombinationProject, RecombinationElement
)
from .composition_engine import ChinesePaintingAnalyzer, CompositionReconstructor

import logging
logger = logging.getLogger(__name__)


def composition_dashboard(request):
    """结构分解系统仪表盘"""
    from django.db import connection
    
    try:
        # 检查数据库表是否存在
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('artifacts_compositionanalysis', 'artifacts_compositiontemplate', 'artifacts_recombinationproject')
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            if len(existing_tables) < 3:
                # 表不存在，返回空数据
                context = {
                    'total_analyses': 0,
                    'completed_analyses': 0,
                    'total_templates': 0,
                    'total_projects': 0,
                    'recent_analyses': [],
                    'setup_required': True
                }
                return render(request, 'artifacts/composition_dashboard.html', context)
        
        # 统计信息 - 使用try-except防止查询错误
        try:
            total_analyses = CompositionAnalysis.objects.count()
        except:
            total_analyses = 0
            
        try:
            completed_analyses = CompositionAnalysis.objects.filter(status='completed').count()
        except:
            completed_analyses = 0
            
        try:
            total_templates = CompositionTemplate.objects.filter(is_active=True).count()
        except:
            total_templates = 0
            
        try:
            total_projects = RecombinationProject.objects.count()
        except:
            total_projects = 0
        
        # 最近完成的分析
        recent_analyses = []
        try:
            recent_analyses = CompositionAnalysis.objects.filter(
                status='completed'
            ).select_related('artifact').order_by('-updated_at')[:6]
        except:
            pass
        
        context = {
            'total_analyses': total_analyses,
            'completed_analyses': completed_analyses,
            'total_templates': total_templates,
            'total_projects': total_projects,
            'recent_analyses': recent_analyses,
            'setup_required': False
        }
        return render(request, 'artifacts/composition_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Composition dashboard error: {e}")
        # 如果出错，返回基本上下文
        context = {
            'total_analyses': 0,
            'completed_analyses': 0,
            'total_templates': 0,
            'total_projects': 0,
            'recent_analyses': [],
            'error_message': str(e),
            'setup_required': True
        }
        return render(request, 'artifacts/composition_dashboard.html', context)


def composition_list(request):
    """分析列表"""
    status = request.GET.get('status', '')
    
    analyses = CompositionAnalysis.objects.select_related('artifact')
    
    if status:
        analyses = analyses.filter(status=status)
    
    analyses = analyses.order_by('-created_at')
    
    context = {
        'analyses': analyses,
        'current_status': status,
    }
    return render(request, 'artifacts/composition_list.html', context)


@require_POST
def composition_analyze(request, slug):
    """开始分析画作"""
    artifact = get_object_or_404(Artifact, slug=slug)
    
    # 获取或创建分析记录
    analysis, created = CompositionAnalysis.objects.get_or_create(
        artifact=artifact,
        defaults={'status': 'pending'}
    )
    
    if not created and analysis.status == 'processing':
        return JsonResponse({'status': 'error', 'message': '分析正在进行中'})
    
    # 更新状态
    analysis.status = 'processing'
    analysis.save()
    
    # 在后台线程执行分析
    def do_analysis():
        try:
            start_time = time.time()
            
            # 获取图像路径
            if artifact.image:
                image_path = artifact.image.path
            elif artifact.external_image:
                # 下载外部图像
                import requests
                from urllib.parse import urlparse
                response = requests.get(artifact.external_image, timeout=30)
                temp_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'{slug}.jpg')
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                with open(temp_path, 'wb') as f:
                    f.write(response.content)
                image_path = temp_path
            else:
                raise ValueError('没有可用的图像')
            
            # 执行分析
            analyzer = ChinesePaintingAnalyzer(image_path)
            analyzer.load_image()
            
            # 提取线条
            edges = analyzer.extract_lines_adaptive('combined')
            
            # 分割区域
            labels = analyzer.segment_hierarchical(n_regions=25)
            
            # 提取特征和分类
            regions = analyzer.extract_region_features()
            
            # 语义分类
            for region in regions:
                semantic_type, confidence, scores = analyzer.classify_semantic_type(region)
                region['semantic_type'] = semantic_type
                region['confidence'] = confidence
            
            # 深度分析
            regions = analyzer.analyze_depth_layers(regions)
            
            # 保存可视化结果
            output_dir = os.path.join(settings.MEDIA_ROOT, 'composition', str(analysis.id))
            os.makedirs(output_dir, exist_ok=True)
            
            edge_path = os.path.join(output_dir, 'edges.png')
            analyzer.save_edge_visualization(edge_path)
            
            seg_path = os.path.join(output_dir, 'segments.png')
            analyzer.save_segmentation_visualization(seg_path)
            
            # 保存到模型
            with open(edge_path, 'rb') as f:
                analysis.edge_image.save(f'edges_{analysis.id}.png', ContentFile(f.read()))
            
            with open(seg_path, 'rb') as f:
                analysis.segmented_image.save(f'segments_{analysis.id}.png', ContentFile(f.read()))
            
            # 保存结构数据
            structure_data = {
                'image_size': {'width': analyzer.width, 'height': analyzer.height},
                'region_count': len(regions),
                'regions': regions,
            }
            analysis.set_structure_data(structure_data)
            analysis.region_count = len(regions)
            analysis.processing_time = time.time() - start_time
            analysis.status = 'completed'
            analysis.save()
            
            # 创建结构单元记录
            with transaction.atomic():
                StructuralElement.objects.filter(analysis=analysis).delete()
                
                for region in regions:
                    bbox = region['bbox']
                    bbox_str = f"{bbox[1]},{bbox[0]},{bbox[3]-bbox[1]},{bbox[2]-bbox[0]}"
                    
                    element = StructuralElement.objects.create(
                        analysis=analysis,
                        element_id=region['id'],
                        semantic_type=region.get('semantic_type', 'unknown'),
                        confidence=region.get('confidence', 0),
                        bounding_box=bbox_str,
                        center_x=region['centroid'][0],
                        center_y=region['centroid'][1],
                        area=region['area'],
                        perimeter=region['perimeter'],
                        aspect_ratio=region['aspect_ratio'],
                        compactness=region.get('solidity', 0),
                        elongation=region.get('eccentricity', 0),
                        dominant_color=','.join(map(str, region.get('mean_color', []))) if 'mean_color' in region else '',
                        depth_order=region.get('depth_order', 0),
                    )
                    
                    # 提取独立图像
                    isolated = analyzer.extract_isolated_region(region['id'])
                    if isolated is not None:
                        from PIL import Image
                        img = Image.fromarray(isolated)
                        temp_isolated = os.path.join(output_dir, f'element_{region["id"]}.png')
                        img.save(temp_isolated)
                        with open(temp_isolated, 'rb') as f:
                            element.isolated_image.save(
                                f'element_{analysis.id}_{region["id"]}.png',
                                ContentFile(f.read())
                            )
            
            logger.info(f"Analysis {analysis.id} completed successfully")
            
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}")
            analysis.status = 'failed'
            analysis.save()
    
    # 启动后台线程
    thread = threading.Thread(target=do_analysis)
    thread.daemon = True
    thread.start()
    
    return JsonResponse({
        'status': 'success',
        'message': '分析已开始',
        'analysis_id': analysis.id
    })


def composition_detail(request, analysis_id):
    """分析详情页"""
    analysis = get_object_or_404(CompositionAnalysis, id=analysis_id)
    elements = analysis.elements.all()
    
    # 统计语义类型
    semantic_stats = {}
    for elem in elements:
        t = elem.semantic_type
        semantic_stats[t] = semantic_stats.get(t, 0) + 1
    
    context = {
        'analysis': analysis,
        'elements': elements,
        'semantic_stats': semantic_stats,
        'structure_data': analysis.structure_data,
    }
    return render(request, 'artifacts/composition_detail.html', context)


def composition_elements(request, analysis_id):
    """结构单元列表"""
    analysis = get_object_or_404(CompositionAnalysis, id=analysis_id)
    
    # 筛选
    semantic_type = request.GET.get('type', '')
    depth = request.GET.get('depth', '')
    
    elements = analysis.elements.all()
    
    if semantic_type:
        elements = elements.filter(semantic_type=semantic_type)
    if depth:
        elements = elements.filter(depth_order=int(depth))
    
    context = {
        'analysis': analysis,
        'elements': elements,
        'semantic_types': StructuralElement.SEMANTIC_TYPES,
        'current_type': semantic_type,
        'current_depth': depth,
    }
    return render(request, 'artifacts/composition_elements.html', context)


def composition_editor(request, analysis_id):
    """结构重组编辑器"""
    analysis = get_object_or_404(CompositionAnalysis, id=analysis_id)
    elements = analysis.elements.all()
    templates = CompositionTemplate.objects.filter(is_active=True)
    
    context = {
        'analysis': analysis,
        'elements': elements,
        'templates': templates,
        'canvas_width': 1024,
        'canvas_height': 768,
    }
    return render(request, 'artifacts/composition_editor.html', context)


@require_POST
def composition_generate(request):
    """生成重组构图"""
    data = json.loads(request.body)
    
    analysis_id = data.get('analysis_id')
    template_id = data.get('template_id')
    element_configs = data.get('elements', [])
    canvas_size = data.get('canvas_size', {'width': 1024, 'height': 768})
    
    analysis = get_object_or_404(CompositionAnalysis, id=analysis_id)
    template = None
    if template_id:
        template = get_object_or_404(CompositionTemplate, id=template_id)
    
    # 创建项目
    project = RecombinationProject.objects.create(
        name=f"重组项目 {analysis.artifact.name}",
        source_analysis=analysis,
        template=template,
        status='generating',
        config_json=json.dumps(data)
    )
    
    # 使用构图重组器
    reconstructor = CompositionReconstructor(
        width=canvas_size['width'],
        height=canvas_size['height']
    )
    reconstructor.create_canvas(bg_color=(250, 248, 245, 255))  # 宣纸色
    
    # 按z_index排序元素
    element_configs.sort(key=lambda x: x.get('z_index', 0))
    
    for config in element_configs:
        element_id = config.get('element_id')
        element = get_object_or_404(StructuralElement, id=element_id)
        
        if element.isolated_image:
            # 加载元素图像
            img_path = element.isolated_image.path
            elem_img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
            
            if elem_img is not None:
                reconstructor.place_element(
                    elem_img,
                    position=(config['x'], config['y']),
                    scale=config.get('scale', 1.0),
                    rotation=config.get('rotation', 0),
                    z_index=config.get('z_index', 0)
                )
        
        # 保存配置
        RecombinationElement.objects.create(
            project=project,
            source_element=element,
            position_x=config['x'],
            position_y=config['y'],
            scale_x=config.get('scale', 1.0),
            scale_y=config.get('scale', 1.0),
            rotation=config.get('rotation', 0),
            z_index=config.get('z_index', 0),
            opacity=config.get('opacity', 1.0)
        )
    
    # 保存结果
    output_dir = os.path.join(settings.MEDIA_ROOT, 'composition', 'recombinations')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'project_{project.id}.png')
    
    reconstructor.save_result(output_path)
    
    with open(output_path, 'rb') as f:
        project.result_image.save(f'result_{project.id}.png', ContentFile(f.read()))
    
    project.status = 'completed'
    project.save()
    
    return JsonResponse({
        'status': 'success',
        'project_id': project.id,
        'result_url': project.result_image.url if project.result_image else None
    })


def template_list(request):
    """构图模板列表"""
    templates = CompositionTemplate.objects.filter(is_active=True)
    
    context = {
        'templates': templates,
    }
    return render(request, 'artifacts/template_list.html', context)


def template_detail(request, template_id):
    """模板详情"""
    template = get_object_or_404(CompositionTemplate, id=template_id)
    
    context = {
        'template': template,
        'rules': template.rules,
    }
    return render(request, 'artifacts/template_detail.html', context)


# API接口

@require_GET
def api_analysis_status(request, analysis_id):
    """获取分析状态"""
    analysis = get_object_or_404(CompositionAnalysis, id=analysis_id)
    
    return JsonResponse({
        'id': analysis.id,
        'status': analysis.status,
        'region_count': analysis.region_count,
        'processing_time': analysis.processing_time,
        'created_at': analysis.created_at.isoformat(),
        'updated_at': analysis.updated_at.isoformat(),
    })


@require_GET
def api_analysis_regions(request, analysis_id):
    """获取分析的区域数据"""
    analysis = get_object_or_404(CompositionAnalysis, id=analysis_id)
    
    regions = []
    for elem in analysis.elements.all():
        regions.append({
            'id': elem.id,
            'element_id': elem.element_id,
            'semantic_type': elem.semantic_type,
            'semantic_type_display': elem.get_semantic_type_display(),
            'confidence': elem.confidence,
            'bbox': elem.bounding_box,
            'center': [elem.center_x, elem.center_y],
            'area': elem.area,
            'depth_order': elem.depth_order,
            'isolated_image_url': elem.isolated_image.url if elem.isolated_image else None,
        })
    
    return JsonResponse({
        'analysis_id': analysis.id,
        'image_size': analysis.structure_data.get('image_size', {}) if analysis.structure_data else {},
        'regions': regions,
    })


@require_GET
def api_template_layout(request, template_id):
    """获取模板的布局规则"""
    template = get_object_or_404(CompositionTemplate, id=template_id)
    
    # 根据模板类型生成布局建议
    canvas_width = int(request.GET.get('width', 1024))
    canvas_height = int(request.GET.get('height', 768))
    
    if template.template_type == 'three_distances':
        # 三远法布局
        layout = {
            'type': 'three_distances',
            'description': '高远、平远、深远三种空间表现',
            'regions': {
                'high': {
                    'name': '高远区',
                    'y_range': [0, canvas_height * 0.35],
                    'description': '仰视山峰，主峰巍峨'
                },
                'level': {
                    'name': '平远区', 
                    'y_range': [canvas_height * 0.35, canvas_height * 0.65],
                    'description': '平视展开，层次分明'
                },
                'deep': {
                    'name': '深远区',
                    'y_range': [canvas_height * 0.65, canvas_height],
                    'description': '俯视纵深，近大远小'
                }
            }
        }
    elif template.template_type == 'golden_ratio':
        phi = 1.618
        layout = {
            'type': 'golden_ratio',
            'description': '黄金分割构图',
            'focal_points': [
                [canvas_width / phi, canvas_height / phi],
                [canvas_width - canvas_width / phi, canvas_height / phi],
                [canvas_width / phi, canvas_height - canvas_height / phi],
                [canvas_width - canvas_width / phi, canvas_height - canvas_height / phi],
            ]
        }
    elif template.template_type == 'rule_thirds':
        layout = {
            'type': 'rule_thirds',
            'description': '三分法则构图',
            'grid_lines': {
                'horizontal': [canvas_height / 3, 2 * canvas_height / 3],
                'vertical': [canvas_width / 3, 2 * canvas_width / 3]
            },
            'focal_points': [
                [canvas_width / 3, canvas_height / 3],
                [2 * canvas_width / 3, canvas_height / 3],
                [canvas_width / 3, 2 * canvas_height / 3],
                [2 * canvas_width / 3, 2 * canvas_height / 3],
            ]
        }
    else:
        layout = template.rules
    
    return JsonResponse({
        'template_id': template.id,
        'template_type': template.template_type,
        'template_type_display': template.get_template_type_display(),
        'layout': layout,
    })


@require_POST
def api_auto_layout(request):
    """自动布局API"""
    data = json.loads(request.body)
    
    analysis_id = data.get('analysis_id')
    template_type = data.get('template_type', 'three_distances')
    
    analysis = get_object_or_404(CompositionAnalysis, id=analysis_id)
    elements = list(analysis.elements.all())
    
    canvas_width = data.get('canvas_width', 1024)
    canvas_height = data.get('canvas_height', 768)
    
    # 创建重组器
    reconstructor = CompositionReconstructor(canvas_width, canvas_height)
    
    # 准备元素数据
    element_data = []
    for elem in elements:
        element_data.append({
            'id': elem.id,
            'semantic_type': elem.semantic_type,
            'area': elem.area,
            'depth_order': elem.depth_order,
            'aspect_ratio': elem.aspect_ratio,
        })
    
    # 应用布局算法
    if template_type == 'three_distances':
        # 按深度分组
        by_depth = {'high': [], 'level': [], 'deep': []}
        for elem in element_data:
            if elem['depth_order'] == 2:
                by_depth['high'].append(elem)
            elif elem['depth_order'] == 1:
                by_depth['level'].append(elem)
            else:
                by_depth['deep'].append(elem)
        
        layout = reconstructor.apply_three_distances(by_depth)
        
    elif template_type == 'golden_ratio':
        layout = reconstructor.apply_golden_ratio(element_data)
        
    elif template_type == 'rule_thirds':
        # 设置重要性
        for elem in element_data:
            if elem['semantic_type'] == 'mountain':
                elem['importance'] = 10
            elif elem['semantic_type'] in ['water', 'tree']:
                elem['importance'] = 5
            else:
                elem['importance'] = 1
        
        layout = reconstructor.apply_rule_of_thirds(element_data)
    else:
        # 默认均匀分布
        layout = {}
        n = len(element_data)
        cols = int(n ** 0.5) + 1
        for i, elem in enumerate(element_data):
            row = i // cols
            col = i % cols
            layout[elem['id']] = {
                'x': canvas_width * (0.1 + 0.8 * col / cols),
                'y': canvas_height * (0.1 + 0.8 * row / (n // cols + 1)),
                'scale': 0.5,
                'z_index': elem['depth_order']
            }
    
    return JsonResponse({
        'status': 'success',
        'template_type': template_type,
        'layout': layout,
        'element_count': len(element_data),
    })


# 初始化默认模板
def init_default_templates():
    """初始化默认构图模板"""
    default_templates = [
        {
            'name': '三远法构图',
            'template_type': 'three_distances',
            'description': '源自郭熙《林泉高致》，高远、平远、深远三种空间表现方法',
            'dynasty_reference': '宋代',
            'artist_reference': '郭熙',
            'rules': {
                'high_distance': {
                    'y_range': [0, 0.35],
                    'elements': ['mountain'],
                    'description': '自山下而仰山巅'
                },
                'level_distance': {
                    'y_range': [0.35, 0.65],
                    'elements': ['water', 'ground'],
                    'description': '自近山而望远山'
                },
                'deep_distance': {
                    'y_range': [0.65, 1.0],
                    'elements': ['tree', 'rock', 'figure'],
                    'description': '自山前而窥山后'
                }
            }
        },
        {
            'name': '黄金分割构图',
            'template_type': 'golden_ratio',
            'description': '基于黄金比例φ=1.618的经典美学构图',
            'rules': {
                'phi': 1.618,
                'spiral': True,
                'focus_weight': 'fibonacci'
            }
        },
        {
            'name': '三分法则',
            'template_type': 'rule_thirds',
            'description': '将画面分成九宫格，重要元素放在交叉点上',
            'rules': {
                'grid': [3, 3],
                'focal_points': 'intersections'
            }
        },
        {
            'name': '对称构图',
            'template_type': 'symmetric',
            'description': '左右或上下对称，体现庄重与平衡',
            'rules': {
                'axis': 'vertical',
                'balance': 'mirror'
            }
        },
        {
            'name': 'S形构图',
            'template_type': 's_curve',
            'description': '蜿蜒S形引导视线，增加画面动感',
            'rules': {
                'curve_type': 'sigmoid',
                'flow_direction': 'left_to_right'
            }
        },
    ]
    
    for template_data in default_templates:
        CompositionTemplate.objects.get_or_create(
            name=template_data['name'],
            defaults={
                'template_type': template_data['template_type'],
                'description': template_data['description'],
                'rules_json': json.dumps(template_data.get('rules', {}), ensure_ascii=False),
                'dynasty_reference': template_data.get('dynasty_reference', ''),
                'artist_reference': template_data.get('artist_reference', ''),
                'is_active': True
            }
        )
