from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.conf import settings
from .models import Artifact, Category, Exhibition
from django.db.models import Count, Q
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView
from django.utils import timezone
import json
import os
import re

# 加载 WikiArt 中文作品 URL 映射
def load_wikiart_url_map():
    json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'wikiart_chinese_enhanced.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return {item['name'].strip(): item['image'] for item in data}

# 全局映射字典（模块加载时一次读取）
WIKIART_URL_MAP = load_wikiart_url_map()

def home(request):
    # 数据库数据（仅显示真实文物，不显示爬虫数据）
    active_exhibitions = Exhibition.objects.filter(is_active=True).order_by('-start_date')[:6]
    latest_artifacts = Artifact.objects.filter(is_active=True).order_by('-created_at')[:8]

    # 注入 external_image
    for art in latest_artifacts:
        art.external_image = WIKIART_URL_MAP.get(art.name.strip())

    context = {
        'active_exhibitions': active_exhibitions,
        'latest_artifacts': latest_artifacts,
    }
    return render(request, 'artifacts/home.html', context)

def artifact_list(request):
    """文物列表页，支持筛选"""
    artifacts = Artifact.objects.filter(is_active=True)
    categories = Category.objects.annotate(artifact_count=Count('artifact')).all()
    exhibitions = Exhibition.objects.filter(is_active=True).all()
    
    # 获取筛选参数
    category_slug = request.GET.get('category')
    era = request.GET.get('era')
    color = request.GET.get('color')
    exhibition_slug = request.GET.get('exhibition')
    search = request.GET.get('search', '').strip()
    
    # 应用筛选
    if category_slug:
        artifacts = artifacts.filter(category__slug=category_slug)
    if era:
        artifacts = artifacts.filter(era=era)
    if color:
        artifacts = artifacts.filter(color=color)
    if exhibition_slug:
        artifacts = artifacts.filter(exhibition__slug=exhibition_slug)
    if search:
        artifacts = artifacts.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )
    
    # 分页
    paginator = Paginator(artifacts, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # 注入 external_image
    for art in page_obj.object_list:
        art.external_image = WIKIART_URL_MAP.get(art.name.strip())
    
    # 获取筛选选项
    eras = Artifact.objects.filter(is_active=True).values_list('era', flat=True).distinct().order_by('era')
    colors = Artifact.objects.filter(is_active=True).values_list('color', flat=True).distinct().order_by('color')
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'exhibitions': exhibitions,
        'eras': eras,
        'colors': colors,
        'current_category': category_slug,
        'current_era': era,
        'current_color': color,
        'current_exhibition': exhibition_slug,
        'current_search': search,
    }
    return render(request, 'artifacts/artifact_list.html', context)

def artifact_detail(request, slug):
    """文物详情页"""
    artifact = get_object_or_404(Artifact, slug=slug, is_active=True)
    # 注入外部图片 URL
    artifact.external_image = WIKIART_URL_MAP.get(artifact.name.strip())
    
    # 获取同类别的其他文物
    related_artifacts = Artifact.objects.filter(
        category=artifact.category,
        is_active=True
    ).exclude(id=artifact.id)[:4]
    
    context = {
        'artifact': artifact,
        'related_artifacts': related_artifacts,
    }
    return render(request, 'artifacts/artifact_detail.html', context)

def exhibition_detail(request, slug):
    """专题展览详情页"""
    exhibition = get_object_or_404(Exhibition, slug=slug, is_active=True)
    artifacts = Artifact.objects.filter(exhibition=exhibition, is_active=True)
    
    # 注入 external_image
    for art in artifacts:
        art.external_image = WIKIART_URL_MAP.get(art.name.strip())
    
    context = {
        'exhibition': exhibition,
        'artifacts': artifacts,
    }
    return render(request, 'artifacts/exhibition_detail.html', context)

def category_artifacts(request, slug):
    """按分类查看文物"""
    category = get_object_or_404(Category, slug=slug)
    artifacts = Artifact.objects.filter(category=category, is_active=True)

    # 分页
    paginator = Paginator(artifacts, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # 注入 external_image
    for art in page_obj.object_list:
        art.external_image = WIKIART_URL_MAP.get(art.name.strip())

    context = {
        'category': category,
        'page_obj': page_obj,
    }
    return render(request, 'artifacts/category_artifacts.html', context)


# 用户认证相关视图
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView

def user_register(request):
    """用户注册"""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = CustomUserCreationForm()

    return render(request, 'artifacts/register.html', {'form': form})

def user_login(request):
    """用户登录"""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get('next', 'home')
            return redirect(next_url)
    else:
        form = AuthenticationForm()

    return render(request, 'artifacts/login.html', {'form': form})

@login_required
def user_profile(request):
    """用户个人中心"""
    return render(request, 'artifacts/profile.html')

# ---------- 调色板导出功能 ----------
from django.http import JsonResponse, HttpResponse
from PIL import Image, ImageDraw
import io


def export_palette_json(request, slug):
    artifact = get_object_or_404(Artifact, slug=slug, is_active=True)
    data = {
        "name": artifact.name,
        "description": artifact.description,
        "palette": artifact.color_palette or []
    }
    response = JsonResponse(data, json_dumps_params={'ensure_ascii': False})
    response['Content-Disposition'] = f'attachment; filename="{slug}_palette.json"'
    return response


def export_palette_png(request, slug):
    artifact = get_object_or_404(Artifact, slug=slug, is_active=True)
    palette = artifact.color_palette or []
    if not palette:
        return HttpResponse("No palette", status=404)
    
    # 每个色块 200px 宽，100px 高
    swatch_width = 200
    swatch_height = 100
    img_width = len(palette) * swatch_width
    img_height = swatch_height
    
    img = Image.new('RGB', (img_width, img_height), color='white')
    draw = ImageDraw.Draw(img)
    
    for i, hex_color in enumerate(palette):
        # hex to RGB
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[j:j+2], 16) for j in (0, 2, 4))
        x0 = i * swatch_width
        draw.rectangle([x0, 0, x0 + swatch_width, swatch_height], fill=rgb)
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type="image/png")
    response['Content-Disposition'] = f'attachment; filename="{slug}_palette.png"'
    return response

# ---------- 全局色彩统计 ----------
from collections import Counter


def color_stats(request):
    # 统计所有颜色出现次数
    color_counter = Counter()
    for art in Artifact.objects.filter(is_active=True, color_palette__isnull=False):
        for c in art.color_palette:
            color_counter[c] += 1
    
    # 取前 50 种高频颜色
    most_common = color_counter.most_common(50)
    
    # 转换为列表 dict 方便模板使用
    palette_data = [{'color': col, 'count': cnt} for col, cnt in most_common]
    
    context = {
        'palette_data': palette_data,
        'total_colors': len(color_counter),
        'total_artifacts': Artifact.objects.filter(is_active=True).count()
    }
    return render(request, 'artifacts/color_stats.html', context)


# ---------- 复杂网络分析功能 ----------
# 注：网络分析功能已移除
import tempfile
import urllib.request
import logging

logger = logging.getLogger(__name__)


def network_analysis(request, slug):
    """网络分析页面（功能已移除）"""
    artifact = get_object_or_404(Artifact, slug=slug, is_active=True)
    artifact.external_image = WIKIART_URL_MAP.get(artifact.name.strip())
    
    context = {
        'artifact': artifact,
        'error_message': '网络分析功能已暂时移除'
    }
    return render(request, 'artifacts/network_analysis.html', context)


def analyze_network(request, slug):
    """执行网络分析API"""
    artifact = get_object_or_404(Artifact, slug=slug, is_active=True)
    
    # 获取检测方法参数（默认使用grounding_dino精确检测）
    detector_method = request.GET.get('method', 'grounding_dino')
    
    # 获取图像路径
    image_path = None
    temp_file = None
    
    try:
        # 优先使用本地图像
        if artifact.image and hasattr(artifact.image, 'path') and os.path.exists(artifact.image.path):
            image_path = artifact.image.path
        elif artifact.external_image:
            # 下载外部图像
            logger.info(f"Downloading external image: {artifact.external_image}")
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                try:
                    urllib.request.urlretrieve(artifact.external_image, tmp.name)
                    image_path = tmp.name
                    temp_file = tmp.name
                except Exception as e:
                    logger.error(f"Failed to download image: {e}")
                    return JsonResponse({'error': f'图像下载失败: {str(e)}'}, status=400)
        else:
            return JsonResponse({'error': '未找到可用图像'}, status=400)
        
        # 执行分析
        logger.info(f"Starting analysis with method: {detector_method}")
        result = analyze_painting_network(image_path, detector_method=detector_method)
        
        # 添加画作信息
        result['artifact_name'] = artifact.name
        result['artifact_slug'] = artifact.slug
        result['artifact_era'] = artifact.era
        result['artifact_material'] = artifact.material
        
        # 添加分析摘要
        result['summary'] = _generate_analysis_summary(result)
        
        return JsonResponse(result, json_dumps_params={'ensure_ascii': False})
        
    except Exception as e:
        logger.exception(f"Network analysis failed: {e}")
        return JsonResponse({'error': str(e)}, status=500)
    finally:
        # 清理临时文件
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except:
                pass


def _generate_analysis_summary(result: dict) -> dict:
    """生成分析摘要"""
    metrics = result.get('metrics', {})
    
    summary = {
        'total_elements': metrics.get('node_count', 0),
        'total_relations': metrics.get('edge_count', 0),
        'network_density': f"{metrics.get('density', 0):.3f}",
        'is_connected': metrics.get('is_connected', False),
        'clustering': f"{metrics.get('clustering_coefficient', 0):.3f}",
        'small_world': None,
        'communities': 0,
        'top_elements': [],
    }
    
    # 小世界特征
    sw = metrics.get('small_world', {})
    if sw.get('is_small_world'):
        summary['small_world'] = {
            'status': True,
            'sigma': f"{sw.get('sigma', 0):.2f}",
            'interpretation': sw.get('interpretation', '')
        }
    
    # 社区数量
    summary['communities'] = metrics.get('communities', {}).get('count', 0)
    
    # 主要元素
    elem_dist = metrics.get('element_distribution', {})
    sorted_elements = sorted(elem_dist.items(), key=lambda x: x[1], reverse=True)[:5]
    
    element_names = {
        'mountain': '山', 'tree': '树', 'water': '水', 'sky': '天',
        'cloud': '云', 'building': '建筑', 'bridge': '桥', 'boat': '船',
        'person': '人物', 'bird': '鸟', 'rock': '石', 'path': '路'
    }
    
    summary['top_elements'] = [
        {'type': t, 'name': element_names.get(t, t), 'count': c}
        for t, c in sorted_elements
    ]
    
    return summary




