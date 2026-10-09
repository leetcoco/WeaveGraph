from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q
from .models import (
    PaintingElement,
    GarmentType,
    ElementNetwork,
    FashionDesign,
    NetworkMetrics
)
from artifacts.models import Artifact, Category
import uuid
from collections import defaultdict
import json
import base64
import io
import numpy as np
import cv2
from PIL import Image
from scripts.direct_mapping_v8 import create_garment_mask_v8, map_artifact_to_garment_v8, extract_garment_lines, load_image


def decode_base64_image(base64_str, size=256):
    """解码base64图像并调整为指定尺寸"""
    try:
        if base64_str.startswith('data:'):
            base64_str = base64_str.split(',')[1]
        image_data = base64.b64decode(base64_str)
        img = Image.open(io.BytesIO(image_data))
        
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        
        img = img.convert('RGB')
        img = img.resize((size, size), Image.LANCZOS)
        
        result = np.array(img)
        return cv2.cvtColor(result, cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"图像解码失败: {e}")
        return None


def detect_painting_subject(image_data):
    """
    主体检测模型 v4_final - 基于轮廓特征分类（专为优化设计）
    
    核心思路：
    1. 提取所有内容区域（小核操作，保持分离性）
    2. 用几何特征区分动物主体 vs 书法文字
       动物：面积大、紧凑(0.25~1.8)、实心(>0.3)、居中
       文字：小/极长条形(compactness<0.15)、靠边、排列成行
    3. 合并属于同一主体的多个部分（头+身在同一个框）
    """
    try:
        img = image_data.copy()
        if img.dtype != np.uint8:
            img = (img * 255).astype(np.uint8)
        
        h, w = img.shape[:2]
        if h < 4 or w < 4:
            return {'x': 0, 'y': 0, 'w': w, 'h': h, 'confidence': 0.3}
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        bg_val = int(np.percentile(gray.flatten(), 90))
        
        # 三种独立的内容检测（小核，保持分离）
        dark_mask = (gray < max(120, bg_val - 45)).astype(np.uint8) * 255
        
        edges = cv2.Canny(gray, 20, 80)
        ke3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        edge_mask = cv2.dilate(edges, ke3, iterations=2)
        
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        color_mask = (hsv[:, :, 1] > 30).astype(np.uint8) * 255
        
        # 小核合并（5x5），避免把鸟和书法连在一起
        kc5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        ko3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        content_mask = cv2.bitwise_or(dark_mask, edge_mask)
        content_mask = cv2.bitwise_or(content_mask, color_mask)
        content_mask = cv2.morphologyEx(content_mask, cv2.MORPH_CLOSE, kc5)
        content_mask = cv2.morphologyEx(content_mask, cv2.MORPH_OPEN, ko3)
        
        # ===== Stage 2: 轮廓提取与特征分析 =====
        contours, _ = cv2.findContours(
            content_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        if len(contours) == 0:
            return {'x': 0, 'y': 0, 'w': w, 'h': h, 'confidence': 0.3}
        
        margin = max(4, int(min(h, w) * 0.03))
        min_area = max(w * h * 0.006, 150)
        
        candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            
            bx, by, bw, bh = cv2.boundingRect(cnt)
            perimeter = cv2.arcLength(cnt, True)
            compactness = (4 * np.pi * area) / (perimeter ** 2 + 1e-6)
            solidity = area / (bw * bh + 1e-6)
            aspect = bw / (bh + 1e-6)
            area_ratio = area / (w * h + 1e-6)
            
            cx, cy = bx + bw / 2, by + bh / 2
            center_dist = ((cx - w/2)**2 + (cy - h/2)**2) ** 0.5
            max_dist = ((w**2 + h**2) ** 0.5) / 2
            centrality = 1 - center_dist / max_dist
            touches_edge = sum([bx<=margin, by<=margin, bx+bw>=w-margin, by+bh>=h-margin])
            
            # 动物 vs 文字判别评分
            animal_score = (
                np.log(area_ratio + 1e-6) * 10 +
                (0.22 < compactness < 1.8) * 4 +
                solidity * 5 +
                centrality * 3 +
                (touches_edge == 0) * 2 +
                (0.25 < aspect < 4) * 1.5 -
                (aspect > 7 or aspect < 0.12) * 10 -
                (compactness < 0.12) * 9 -
                (area_ratio < 0.012) * 7
            )
            
            candidates.append({
                'x': bx, 'y': by, 'w': bw, 'h': bh,
                'area': area, 'animal_score': animal_score,
                'compactness': compactness, 'solidity': solidity,
                'aspect': aspect, 'touches': touches_edge,
                'center_x': cx, 'center_y': cy
            })
        
        if not candidates:
            return {'x': 0, 'y': 0, 'w': w, 'h': h, 'confidence': 0.3}
        
        candidates.sort(key=lambda c: c['animal_score'], reverse=True)
        
        merged = [candidates[0]]
        for cand in candidates[1:]:
            mx = min(r['x'] for r in merged)
            my = min(r['y'] for r in merged)
            mw_ = max(r['x']+r['w'] for r in merged)-mx
            mh_ = max(r['y']+r['h'] for r in merged)-my
            nw = max(mx+mw_, cand['x']+cand['w'])-min(mx,cand['x'])
            nh = max(my+mh_, cand['y']+cand['h'])-min(my,cand['y'])
            er = nw*nh/max(1,mw_*mh_)
            
            cond_size = er <= 2.5
            y_ov = max(0, min(my+mh_, cand['y']+cand['h']) - max(my, cand['y']))
            x_ov = max(0, min(mx+mw_, cand['x']+cand['w']) - max(mx, cand['x']))
            has_ov = (y_ov > 0) and (x_ov > 0)
            yg = abs(cand['center_y']-(my+mh_/2))
            xg = abs(cand['center_x']-(mx+mw_/2))
            close = (yg<max(mh_,cand['h'])*0.65) or (xg<max(mw_,cand['w'])*0.65)
            if cond_size and (has_ov or close) and cand['animal_score']>(-1):
                merged.append(cand)
        
        fx=min(r['x'] for r in merged); fy=min(r['y'] for r in merged)
        fw=max(r['x']+r['w'] for r in merged)-fx; fh=max(r['y']+r['h'] for r in merged)-fy
        
        pad_t=int(fh*0.14); pad_b=int(fh*0.07); pad_l=int(fw*0.05); pad_r=int(fw*0.05)
        rx=max(0,fx-pad_l); ry=max(0,fy-pad_t)
        rw=min(w,fx+fw+pad_r)-rx; rh=min(h,fy+fh+pad_b)-ry
        
        coverage=rw*rh/(w*h)
        conf=min(0.95,coverage*1.2+0.25)
        if coverage>0.92: conf*=0.7
        
        return {'x':int(rx),'y':int(ry),'w':int(rw),'h':int(rh),
                'confidence':round(conf,3),'method':'v4_final'}
    except Exception as e:
        print('主体检测异常:',e)
        import traceback; traceback.print_exc()
        return {'x':0,'y':0,'w':256,'h':256,'confidence':0.0}


@csrf_exempt
def detect_subject(request):
    """画作主体检测API"""
    if request.method != 'POST':
        return JsonResponse({'error': '只支持POST请求'}, status=405)

    try:
        data = json.loads(request.body)
        artifact_image = data.get('artifact_image')
        
        if not artifact_image:
            return JsonResponse({'error': '缺少画作图像数据'}, status=400)
        
        img = decode_base64_image(artifact_image, size=256)
        if img is None:
            return JsonResponse({'error': '图像解码失败'}, status=400)
        
        result = detect_painting_subject(img)
        
        if bool(data.get('return_debug', False)):
            debug_img = img.copy().astype(np.uint8)
            x, y, bw, bh = result['x'], result['y'], result['w'], result['h']
            cv2.rectangle(debug_img, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
            pil_debug = Image.fromarray(debug_img)
            buf = io.BytesIO()
            pil_debug.save(buf, format='PNG')
            result['debug_image'] = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('utf-8')
        
        return JsonResponse(result)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


def normalize_external_image(url):
    """规范化外部图片URL"""
    if not url:
        return ''
    url = url.strip()
    if url.startswith('//'):
        url = 'https:' + url
    elif not url.startswith(('http://', 'https://', '/static/', '/media/')):
        # 如果不是有效的URL路径，返回空字符串
        url = ''
    return url


def get_artifacts(page=1, category_id=None):
    """获取文物列表（分页）"""
    # 查询有图片的画作（本地图片或外部图片）
    artifacts_qs = Artifact.objects.select_related('category').filter(
        Q(image__isnull=False) & ~Q(image='') | Q(external_image__isnull=False) & ~Q(external_image='')
    )
    
    # 只有当category_id不为'all'且不为空时才进行过滤
    if category_id and category_id != 'all':
        try:
            artifacts_qs = artifacts_qs.filter(category_id=int(category_id))
        except (ValueError, TypeError):
            # 如果category_id不是有效的数字，忽略过滤
            pass
    
    # 移除数量限制，显示所有画作
    artifacts_qs = artifacts_qs.order_by('-id')
    
    paginator = Paginator(artifacts_qs, 20)
    page_obj = paginator.get_page(page)
    
    artifact_list = []
    for a in page_obj:
        img_url = a.image.url if a.image else ''
        ext_url = normalize_external_image(a.external_image)
        artifact_list.append({
            'id': a.id,
            'name': a.name,
            'image': img_url or ext_url,
            'external_image': ext_url,
            'color_palette': a.color_palette if hasattr(a, 'color_palette') else [],
            'category': a.category.name if a.category else '',
        })
    
    return {
        'artifacts': artifact_list,
        'page_obj': page_obj,  # 返回整个page_obj对象
    }


def get_garments(gender='male'):
    """获取服装类型列表（按性别分组）"""
    garments_qs = GarmentType.objects.all().order_by('name')
    
    male_garments = []
    female_garments = []
    
    for g in garments_qs:
        garment_info = {
            'id': g.id,
            'name': g.name,
            'image': g.image.url if g.image else '',
            'description': g.description or '',
            'gender': g.gender,
        }
        if g.gender == 'male':
            male_garments.append(garment_info)
        elif g.gender == 'female':
            female_garments.append(garment_info)
        else:
            male_garments.append(garment_info)
            female_garments.append(garment_info)
    
    return {
        'male_garments': male_garments,
        'female_garments': female_garments,
    }


def extract_elements_from_palette(palette):
    """从调色板提取颜色元素"""
    elements = []
    if palette and isinstance(palette, list):
        for item in palette:
            if isinstance(item, str) and item.startswith('#'):
                elements.append(item.strip())
            elif isinstance(item, dict):
                color_val = item.get('color', '')
                if color_val:
                    elements.append(color_val.strip())
    return list(set(elements))[:8]


def get_artifact_colors(palette):
    """获取文物的颜色列表"""
    colors = []
    if palette and isinstance(palette, list):
        for item in palette[:8]:
            if isinstance(item, str):
                colors.append(item.strip())
            elif isinstance(item, dict):
                c = item.get('color', '')
                if c:
                    colors.append(c.strip())
    return colors


def calculate_artifact_design_score(artifact, garment_type):
    """计算文物与服装的设计匹配度"""
    score = 0.35
    
    artifact_colors = get_artifact_colors(artifact.color_palette) if hasattr(artifact, 'color_palette') else []
    if not artifact_colors and hasattr(artifact, 'color_palette'):
        artifact_colors = extract_elements_from_palette(artifact.color_palette)
    
    if artifact_colors and len(artifact_colors) >= 3:
        score += 0.25
    
    score += 0.15
    
    return min(1.0, score)


def build_element_network(artifact_id, garment_type_id):
    """构建元素网络图"""
    elements = PaintingElement.objects.filter(
        artifact_id=artifact_id
    ).select_related('element_type')[:30]
    
    network = defaultdict(lambda: defaultdict(float))
    
    existing = ElementNetwork.objects.filter(
        source__artifact_id=artifact_id,
        target__artifact_id=artifact_id
    ).first()
    
    if existing and existing.network_data:
        try:
            saved_network = json.loads(existing.network_data)
            for src, targets in saved_network.items():
                for tgt, weight in targets.items():
                    network[src][tgt] = weight
        except (json.JSONDecodeError, TypeError):
            pass
    
    if not any(network.values()):
        for i, elem in enumerate(elements):
            if i + 1 < len(elements):
                next_elem = elements[i + 1]
                src_name = elem.element_type.name if elem.element_type else f'element_{i}'
                tgt_name = next_elem.element_type.name if next_elem.element_type else f'element_{i+1}'
                network[src_name][tgt_name] = 0.7
                network[tgt_name][src_name] = 0.5
    
    return network


def random_walk_recommendations(network, start_node=None, steps=5):
    """基于随机游走的推荐算法"""
    nodes = list(network.keys())
    if not nodes:
        return []
    
    if start_node and start_node in nodes:
        current = start_node
    else:
        current = nodes[0]
    
    visited = [current]
    scores = {}
    
    for _ in range(steps):
        neighbors = network.get(current, {})
        if not neighbors:
            break
        weights = list(neighbors.values())
        total = sum(weights) or 1
        probs = [w / total for w in weights]
        
        idx = np.random.choice(len(neighbors), p=probs)
        current = list(neighbors.keys())[idx]
        
        if current not in visited:
            visited.append(current)
            scores[current] = probs[idx]
    
    recommendations = []
    for node, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]:
        recommendations.append({'node': node, 'score': round(score, 3)})
    
    return recommendations


def pagerank_recommendations(network, iterations=20, damping=0.85):
    """PageRank推荐算法"""
    nodes = list(network.keys())
    n = len(nodes)
    if n == 0:
        return []
    
    ranks = {node: 1.0 / n for node in nodes}
    out_degree = {node: len(network[node]) for node in nodes}
    
    for _ in range(iterations):
        new_ranks = {}
        for node in nodes:
            rank_sum = 0
            for other in nodes:
                if other in network and node in network[other]:
                    weight = network[other][node]
                    total_out = out_degree[other]
                    rank_sum += (ranks[other] * weight / total_out) if total_out > 0 else 0
            new_ranks[node] = (1 - damping) / n + damping * rank_sum
        
        ranks = new_ranks
    
    total = sum(ranks.values()) or 1
    recommendations = [
        {'node': node, 'score': round(rank / total, 3)}
        for node, rank in sorted(ranks.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    return recommendations


def collaborative_filtering(artifact_id, garment_type_id, k=5):
    """协同过滤推荐"""
    designs = FashionDesign.objects.filter(
        garment_type_id=garment_type_id
    )[:100]
    
    similar_items = []
    target_elements = set(PaintingElement.objects.filter(artifact_id=artifact_id).values_list('element_type__name', flat=True)[:10])
    
    for d in designs:
        d_elements = set(PaintingElement.objects.filter(artifact_id=d.artifact_id).values_list('element_type__name', flat=True)[:10])
        intersection = len(target_elements & d_elements)
        union = len(target_elements | d_elements)
        jaccard = intersection / union if union > 0 else 0
        
        if jaccard > 0.1:
            similar_items.append({
                'artifact_id': d.artifact_id,
                'similarity': round(jaccard, 3),
                'design_id': d.id,
            })
    
    similar_items.sort(key=lambda x: x['similarity'], reverse=True)
    return similar_items[:k]


def centrality_recommendations(network, k=5):
    """中心性分析推荐"""
    if not network:
        return []
    
    degrees = {node: 0 for node in network}
    betweenness = {node: 0 for node in network}
    
    for node, neighbors in network.items():
        degrees[node] = len(neighbors)
        for neighbor in neighbors:
            betweenness[neighbor] += network.get(neighbor, {}).get(node, 0)
    
    combined_scores = {
        node: degrees.get(node, 0) * 0.5 + betweenness.get(node, 0) * 0.5
        for node in degrees
    }
    
    recommendations = [
        {'node': node, 'score': round(score, 3)}
        for node, score in sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:k]
    ]
    return recommendations


@csrf_exempt
def map_v8(request):
    """V8映射API - 使用direct_mapping_v8模块"""
    if request.method != 'POST':
        return JsonResponse({'error': '只支持POST请求'}, status=405)
    
    try:
        data = json.loads(request.body)
        artifact_id = data.get('artifact_id')
        garment_type_id = data.get('garment_type_id')
        
        if not artifact_id or not garment_type_id:
            return JsonResponse({'error': '缺少参数'}, status=400)
        
        artifact = Artifact.objects.filter(id=artifact_id).first()
        garment_type = GarmentType.objects.filter(id=garment_type_id).first()
        
        if not artifact or not garment_type:
            return JsonResponse({'error': '文物或服装不存在'}, status=404)
        
        artifact_image_path = artifact.image.path if artifact.image else None
        external_image = normalize_external_image(artifact.external_image)
        garment_image_path = garment_type.image.path if garment_type.image else None
        
        if not artifact_image_path and not external_image:
            return JsonResponse({'error': '文物图片不存在'}, status=400)
        if not garment_image_path:
            return JsonResponse({'error': '服装图片不存在'}, status=400)
        
        artifact_img = load_image(artifact_image_path or external_image, size=256)
        garment_img = load_image(garment_image_path, size=256)
        
        if artifact_img is None or garment_img is None:
            return JsonResponse({'error': '图片加载失败'}, status=500)
        
        garment_mask = create_garment_mask_v8(garment_img)
        result_img = map_artifact_to_garment_v8(artifact_img, garment_img, garment_mask, 256)
        
        _, buffer = cv2.imencode('.png', result_img)
        result_base64 = 'data:image/png;base64,' + base64.b64encode(buffer).decode('utf-8')
        
        return JsonResponse({
            'result': result_base64,
            'artifact_name': artifact.name,
            'garment_name': garment_type.name,
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def recommend(request):
    """智能推荐API"""
    if request.method != 'POST':
        return JsonResponse({'error': '只支持POST请求'}, status=405)
    
    try:
        data = json.loads(request.body)
        artifact_id = data.get('artifact_id')
        garment_type_id = data.get('garment_type_id')
        
        artifact = Artifact.objects.filter(id=artifact_id).first()
        
        response_data = {
            'random_walk': [],
            'pagerank': [],
            'collaborative': [],
            'centrality': [],
            'match_score': 0,
            'recommended_artifacts': [],
        }
        
        if artifact:
            network = build_element_network(artifact_id, garment_type_id)
            
            response_data['random_walk'] = random_walk_recommendations(network)
            response_data['pagerank'] = pagerank_recommendations(network)
            response_data['collaborative'] = collaborative_filtering(artifact_id, garment_type_id)
            response_data['centrality'] = centrality_recommendations(network)
            response_data['match_score'] = round(calculate_artifact_design_score(artifact, garment_type_id), 2)
        
        garment_type = GarmentType.objects.filter(id=garment_type_id).first()
        
        recommended_ids = set()
        for rec_list in ['random_walk', 'pagerank', 'centrality']:
            for rec in response_data.get(rec_list, []):
                aid = rec.get('artifact_id') or rec.get('node', '')
                if aid and aid not in recommended_ids and aid != artifact_id:
                    recommended_ids.add(aid)
                    art = Artifact.objects.filter(id=aid).first()
                    if art:
                        img_url = art.image.url if art.image else normalize_external_image(art.external_image)
                        response_data['recommended_artifacts'].append({
                            'id': art.id,
                            'name': art.name,
                            'image': img_url,
                        })
                        
                        if len(response_data['recommended_artifacts']) >= 6:
                            break
            if len(response_data['recommended_artifacts']) >= 6:
                break
        
        return JsonResponse(response_data)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


def fashion_design(request):
    """时尚设计主页面视图"""
    if request.method == 'GET':
        page = int(request.GET.get('page', 1))
        category_id = request.GET.get('category')
        
        artifact_data = get_artifacts(page, category_id)
        garment_data = get_garments()
        
        # 只显示有画作的分类，按画作数量排序
        from django.db.models import Count
        categories = Category.objects.annotate(
            artifact_count=Count('artifact')
        ).filter(
            artifact_count__gt=0
        ).order_by('-artifact_count')
        
        context = {
            **artifact_data,
            **garment_data,
            'categories': categories,
            'current_category': category_id or 'all',
        }
        
        return render(request, 'fashion/design.html', context)
    
    elif request.method == 'POST':
        data = json.loads(request.body)
        
        artifact_id = data.get('artifact_id')
        garment_type_id = data.get('garment_type_id')
        
        artifact = Artifact.objects.filter(id=artifact_id).first()
        garment_type = GarmentType.objects.filter(id=garment_type_id).first()
        
        if not artifact or not garment_type:
            return JsonResponse({'error': '参数错误'}, status=400)
        
        painting_elements = PaintingElement.objects.filter(artifact_id=artifact_id).all()[:20]
        graph = build_element_network(artifact_id, garment_type_id)
        
        random_walk_recs = random_walk_recommendations(graph)
        pagerank_recs = pagerank_recommendations(graph)
        collaborative_recs = collaborative_filtering(artifact_id, garment_type_id)
        centrality_recs = centrality_recommendations(graph)
        
        match_score = calculate_artifact_design_score(artifact, garment_type)
        
        artifact_colors = get_artifact_colors(artifact.color_palette) if hasattr(artifact, 'color_palette') else []
        
        response_data = {
            'random_walk_recommendations': random_walk_recs,
            'pagerank_recommendations': pagerank_recs,
            'collaborative_recommendations': collaborative_recs,
            'centrality_recommendations': centrality_recs,
            'design_score': match_score,
            'artifact_colors': artifact_colors,
            'artifact': {
                'id': artifact.id,
                'name': artifact.name,
                'image': artifact.image.url if artifact.image else normalize_external_image(artifact.external_image),
                'external_image': normalize_external_image(artifact.external_image),
                'color_palette': artifact_colors,
                'category': artifact.category.name if artifact.category else '',
            },
            'garment_type': {
                'id': garment_type.id,
                'name': garment_type.name,
                'image': garment_type.image.url if garment_type.image else '',
                'gender': garment_type.gender,
            },
            'painting_elements': [
                {
                    'id': pe.id,
                    'type': pe.element_type.name if pe.element_type else 'unknown',
                    'position_x': pe.position_x if hasattr(pe, 'position_x') else 0,
                    'position_y': pe.position_y if hasattr(pe, 'position_y') else 0,
                    'dominant_color': pe.dominant_color if hasattr(pe, 'dominant_color') else '#000000',
                } for pe in painting_elements
            ],
            'network_metrics': {
                'nodes': len(graph),
                'edges': sum(len(targets) for targets in graph.values()),
                'density': round(sum(len(t) for t in graph.values()) / (len(graph)**2 + 1e-6), 3),
            },
        }
        
        return JsonResponse(response_data)


def get_element_detail(element_id):
    """获取绘画元素详情"""
    try:
        element = PaintingElement.objects.get(id=element_id)
        networks = ElementNetwork.objects.filter(
            source=element, target__artifact_id=element.artifact_id
        ).all() | ElementNetwork.objects.filter(
            target=element, source__artifact_id=element.artifact_id
        ).all()
        
        connections = []
        for net in networks:
            connections.append({
                'source': net.source.element_type.name if net.source else str(net.source_id),
                'target': net.target.element_type.name if net.target else str(net.target_id),
                'weight': net.weight,
            })
        
        related_elements = PaintingElement.objects.filter(
            artifact_id=element.artifact_id
        ).exclude(id=element_id).all()[:10]
        
        return {
            'element': {
                'id': element.id,
                'type': element.element_type.name,
                'position': {'x': element.position_x, 'y': element.position_y},
                'color': element.dominant_color,
            },
            'connections': connections,
            'related': [{'id': re.id, 'type': re.element_type.name} for re in related_elements],
        }
    
    except PaintingElement.DoesNotExist:
        return {'error': '元素不存在'}


def save_design(request):
    """保存设计方案"""
    if request.method != 'POST':
        return JsonResponse({'error': '只支持POST请求'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        design = FashionDesign.objects.create(
            artifact_id=data.get('artifact_id'),
            garment_type_id=data.get('garment_type_id'),
            front_image=data.get('front_image'),
            back_image=data.get('back_image'),
            three_d_model_url=data.get('three_d_model'),
            user=request.user if request.user.is_authenticated else None,
        )
        
        return JsonResponse({
            'success': True,
            'design_id': design.id,
            'message': '设计方案已保存',
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def export_design(design_id, format_type='png'):
    """导出设计方案"""
    try:
        design = FashionDesign.objects.get(id=design_id)
        
        if format_type == 'json':
            data = {
                'id': design.id,
                'artifact_id': design.artifact_id,
                'garment_type_id': design.garment_type_id,
                'front_image': design.front_image,
                'back_image': design.back_image,
                'created_at': design.created_at.isoformat(),
            }
            return JsonResponse(data, content_type='application/json')
        
        elif format_type == 'png':
            from django.http import HttpResponse
            
            if design.front_image:
                if design.front_image.startswith('data:'):
                    img_data = base64.b64decode(design.front_image.split(',')[1])
                    return HttpResponse(img_data, content_type='image/png')
            
            return JsonResponse({'error': '无预览图'})
    
    except FashionDesign.DoesNotExist:
        return JsonResponse({'error': '设计方案不存在'}, status=404)


@csrf_exempt
def analyze_design_network(request):
    """分析设计网络图"""
    if request.method != 'POST':
        return JsonResponse({'error': '只支持POST请求'}, status=405)
    
    try:
        data = json.loads(request.body)
        artifact_id = data.get('artifact_id')
        
        elements_qs = PaintingElement.objects.filter(artifact_id=artifact_id).select_related('element_type').all()[:50]
        
        nodes_data = []
        for pe in elements_qs:
            nodes_data.append({
                'id': pe.id,
                'type_name': pe.element_type.name if pe.element_type else f'element_{pe.id}',
                'position_x': pe.position_x,
                'position_y': pe.position_y,
                'color': pe.dominant_color or '#333333',
            })
        
        edges_qs = ElementNetwork.objects.filter(source__artifact_id=artifact_id, target__artifact_id=artifact_id)[:100]
        edges_data = []
        for edge in edges_qs:
            edges_data.append({
                'source': edge.source.element_type.name if edge.source else str(edge.source_id),
                'target': edge.target.element_type.name if edge.target else str(edge.target_id),
                'weight': round(edge.weight, 2),
            })
        
        # 如果没有边数据，生成默认的
        if not edges_data and len(nodes_data) > 1:
            for i in range(len(nodes_data) - 1):
                edges_data.append({
                    'source': nodes_data[i]['type_name'],
                    'target': nodes_data[i+1]['type_name'],
                    'weight': 0.7,
                })
        
        metrics = NetworkMetrics.objects.filter(artifact__id=artifact_id).first()
        
        response = {
            'nodes': nodes_data,
            'edges': edges_data,
            'metrics': {
                'total_nodes': len(nodes_data),
                'total_edges': len(edges_data),
                'density': round(len(edges_data) / max(len(nodes_data)**2 * 0.5, 1), 3) if nodes_data else 0,
                'avg_weight': round(sum(e.get('weight',0) for e in edges_data)/max(len(edges_data),1),2) if edges_data else 0,
            } if metrics else {},
        }
        
        return JsonResponse(response)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def generate_design(request):
    """生成设计方案"""
    if request.method != 'POST':
        return JsonResponse({'error': '只支持POST请求'}, status=405)
    
    try:
        data = json.loads(request.body)
        artifact_id = data.get('artifact_id')
        garment_type_id = data.get('garment_type_id')
        
        artifact = Artifact.objects.filter(id=artifact_id).first()
        garment_type = GarmentType.objects.filter(id=garment_type_id).first()
        
        if not artifact or not garment_type:
            return JsonResponse({'error': '参数错误'}, status=400)
        
        design = FashionDesign.objects.create(
            artifact=artifact,
            garment_type=garment_type,
            user=request.user if request.user.is_authenticated else None,
        )
        
        return JsonResponse({
            'success': True,
            'design_id': design.id,
            'message': '设计已保存',
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def download_file(request, filename):
    """下载文件"""
    from django.http import HttpResponse
    from django.conf import settings
    
    file_path = settings.MEDIA_ROOT / filename
    
    if not file_path.exists():
        return JsonResponse({'error': '文件不存在'}, status=404)
    
    with open(file_path, 'rb') as f:
        content = f.read()
    
    content_type = 'image/png' if filename.endswith('.png') else 'application/octet-stream'
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
