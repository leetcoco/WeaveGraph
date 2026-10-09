"""
基于复杂网络的中国山水画构图分析视图
用于分析单个画作的构图结构
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import colorsys


class VisualElement:
    """视觉元素基类"""
    def __init__(self, x: float, y: float, width: float, height: float, 
                 color: Tuple[int, int, int], element_type: str):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.center_x = x + width / 2
        self.center_y = y + height / 2
        self.color = color
        self.color_hex = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}".upper()
        self.type = element_type
        self.hsv = colorsys.rgb_to_hsv(color[0]/255, color[1]/255, color[2]/255)
    
    def to_dict(self) -> Dict:
        return {
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'center_x': self.center_x,
            'center_y': self.center_y,
            'color': self.color,
            'color_hex': self.color_hex,
            'type': self.type,
            'hsv': self.hsv
        }


class PaintingNetworkAnalyzer:
    """
    基于复杂网络的画作构图分析器
    将画作划分为网格，提取颜色节点和空间关系，构建构图网络
    """
    
    def __init__(self, image_path: str, grid_size: int = 8):
        """
        初始化分析器
        
        参数:
            image_path: 图片路径
            grid_size: 网格划分大小 (grid_size x grid_size)
        """
        self.image_path = image_path
        self.grid_size = grid_size
        self.image = None
        self.grid_colors = []  # 二维颜色网格
        self.nodes = []  # 颜色节点
        self.edges = []  # 网络边
        self.elements = []  # 视觉元素
        self.visual_flow = {}  # 视觉流信息
        
        # 加载图片
        self._load_image()
    
    def _load_image(self):
        """加载并预处理图片"""
        try:
            self.image = Image.open(self.image_path)
            # 转换为RGB
            if self.image.mode != 'RGB':
                self.image = self.image.convert('RGB')
            self.image = self.image.resize((256, 256), Image.Resampling.LANCZOS)
        except Exception as e:
            raise ValueError(f"无法加载图片: {e}")
    
    def _extract_grid_colors(self):
        """提取网格颜色"""
        self.grid_colors = []
        img_array = np.array(self.image)
        h, w = img_array.shape[:2]
        cell_h, cell_w = h / self.grid_size, w / self.grid_size
        
        for i in range(self.grid_size):
            row = []
            for j in range(self.grid_size):
                # 获取网格区域
                y1, y2 = int(i * cell_h), int((i + 1) * cell_h)
                x1, x2 = int(j * cell_w), int((j + 1) * cell_w)
                region = img_array[y1:y2, x1:x2]
                
                # 计算平均颜色
                avg_color = region.mean(axis=(0, 1)).astype(int)
                row.append(tuple(avg_color))
            self.grid_colors.append(row)
        
        # 根据颜色相似性聚类，创建视觉元素
        self._extract_visual_elements()
    
    def _extract_visual_elements(self):
        """提取视觉元素"""
        elements_by_type = defaultdict(list)
        
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                color = self.grid_colors[i][j]
                
                # 根据HSV确定元素类型
                r, g, b = color
                h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                
                # 判断元素类型
                if v < 0.2:
                    elem_type = '山石/阴影'
                elif s < 0.15:
                    if v > 0.85:
                        elem_type = '云/留白'
                    else:
                        elem_type = '雾气'
                elif h < 0.08 or h > 0.92:  # 红色范围
                    if s > 0.5:
                        elem_type = '朱砂/印章'
                    else:
                        elem_type = '赭石'
                elif 0.08 <= h < 0.16:  # 黄色范围
                    elem_type = '金/秋叶'
                elif 0.16 <= h < 0.33:  # 绿色范围
                    elem_type = '树木/苔藓'
                elif 0.33 <= h < 0.56:  # 青色范围
                    elem_type = '水/云'
                elif 0.56 <= h < 0.78:  # 蓝色范围
                    elem_type = '远山/天空'
                else:
                    elem_type = '综合元素'
                
                # 创建元素
                cell_size = 256 / self.grid_size
                elem = VisualElement(
                    x=j * cell_size,
                    y=i * cell_size,
                    width=cell_size,
                    height=cell_size,
                    color=color,
                    element_type=elem_type
                )
                self.elements.append(elem)
                elements_by_type[elem_type].append(elem)
        
        return elements_by_type
    
    def _build_network(self):
        """构建构图网络"""
        # 颜色相似度阈值
        similarity_threshold = 0.15
        
        for i, elem1 in enumerate(self.elements):
            for j, elem2 in enumerate(self.elements):
                if i >= j:
                    continue
                
                # 计算颜色距离
                dist = self._color_distance(elem1, elem2)
                
                # 计算空间距离
                spatial_dist = np.sqrt(
                    (elem1.center_x - elem2.center_x)**2 + 
                    (elem1.center_y - elem2.center_y)**2
                ) / (256 * np.sqrt(2))  # 归一化
                
                # 综合相似度
                if dist < similarity_threshold and spatial_dist < 0.5:
                    weight = 1 - dist
                    self.edges.append({
                        'source': i,
                        'target': j,
                        'weight': weight,
                        'spatial_dist': spatial_dist
                    })
    
    def _color_distance(self, elem1: VisualElement, elem2: VisualElement) -> float:
        """计算两个元素的颜色距离"""
        # RGB距离
        rgb_dist = np.sqrt(sum((a - b)**2 for a, b in zip(elem1.color, elem2.color))) / 441.67
        
        # HSV距离
        h1, s1, v1 = elem1.hsv
        h2, s2, v2 = elem2.hsv
        h_dist = min(abs(h1 - h2), 1 - abs(h1 - h2))
        s_dist = abs(s1 - s2)
        v_dist = abs(v1 - v2)
        hsv_dist = h_dist * 0.5 + s_dist * 0.3 + v_dist * 0.2
        
        return min(1.0, rgb_dist * 0.4 + hsv_dist * 0.6)
    
    def _calculate_stability(self) -> Dict:
        """计算构图稳定性"""
        n = len(self.elements)
        num_edges = len(self.edges)
        
        # 计算连通性
        if n > 0:
            # 简单计算：有多少元素与至少一个其他元素相连
            connected_nodes = set()
            for edge in self.edges:
                connected_nodes.add(edge['source'])
                connected_nodes.add(edge['target'])
            connectivity = len(connected_nodes) / n
        else:
            connectivity = 0
        
        # 计算边密度
        max_edges = n * (n - 1) / 2 if n > 1 else 1
        edge_density = num_edges / max_edges if max_edges > 0 else 0
        
        # 计算聚类系数
        clustering_coef = self._calculate_clustering_coefficient()
        
        # 检测色彩社群
        num_communities = self._detect_communities()
        
        # 计算中心性平衡
        centrality_balance = self._calculate_centrality_balance()
        
        # 计算视觉流平衡
        flow_balance = self._calculate_flow_balance()
        
        # 色彩和谐性
        color_harmony = self._calculate_color_harmony()
        
        # 综合稳定性评分
        stability_score = (
            connectivity * 0.25 +
            edge_density * 0.15 +
            clustering_coef * 0.15 +
            centrality_balance * 0.15 +
            flow_balance * 0.15 +
            color_harmony * 0.15
        ) * 100
        
        # 稳定性等级
        if stability_score >= 80:
            stability_level = '非常稳定'
        elif stability_score >= 60:
            stability_level = '稳定'
        elif stability_score >= 40:
            stability_level = '一般'
        else:
            stability_level = '不稳定'
        
        return {
            'stability_score': round(stability_score, 1),
            'stability_level': stability_level,
            'num_nodes': n,
            'num_edges': num_edges,
            'is_connected': connectivity > 0.5,
            'connectivity_score': round(connectivity * 100, 1),
            'edge_density': round(edge_density * 100, 1),
            'clustering_coefficient': round(clustering_coef, 4),
            'num_communities': num_communities,
            'centrality_balance': round(centrality_balance * 100, 1),
            'flow_balance': round(flow_balance * 100, 1),
            'color_harmony': round(color_harmony * 100, 1)
        }
    
    def _calculate_clustering_coefficient(self) -> float:
        """计算聚类系数"""
        if len(self.edges) < 3:
            return 0.0
        
        # 构建邻接表
        adj = defaultdict(set)
        for edge in self.edges:
            adj[edge['source']].add(edge['target'])
            adj[edge['target']].add(edge['source'])
        
        clustering_sum = 0.0
        for node in adj:
            neighbors = adj[node]
            k = len(neighbors)
            if k < 2:
                continue
            
            # 计算三角形数量
            triangles = 0
            for n1 in neighbors:
                for n2 in neighbors:
                    if n1 < n2 and n2 in adj[n1]:
                        triangles += 1
            possible = k * (k - 1)
            if possible > 0:
                clustering_sum += triangles / possible
        
        return clustering_sum / len(adj) if len(adj) > 0 else 0.0
    
    def _detect_communities(self) -> int:
        """检测色彩社群数量"""
        # 简单方法：按主色调聚类
        color_groups = defaultdict(list)
        for elem in self.elements:
            h, s, v = elem.hsv
            # 简化聚类：按色相分段
            if s < 0.15:  # 无彩色
                group = 'gray'
            elif v < 0.2:  # 暗色
                group = 'dark'
            elif h < 0.1 or h > 0.9:
                group = 'red'
            elif 0.1 <= h < 0.25:
                group = 'orange'
            elif 0.25 <= h < 0.4:
                group = 'green'
            elif 0.4 <= h < 0.6:
                group = 'cyan_blue'
            else:
                group = 'purple'
            color_groups[group].append(elem)
        
        return len([g for g, elems in color_groups.items() if len(elems) > 2])
    
    def _calculate_centrality_balance(self) -> float:
        """计算中心性平衡"""
        # 计算每个网格位置的重要性
        center_x, center_y = 128, 128  # 图片中心
        importance = []
        
        for elem in self.elements:
            dist_from_center = np.sqrt(
                (elem.center_x - center_x)**2 + 
                (elem.center_y - center_y)**2
            ) / 181  # 归一化因子
        
        # 平衡性：边缘和中心元素的比例
        center_elements = sum(1 for e in self.elements if 
                              np.sqrt((e.center_x-128)**2 + (e.center_y-128)**2) < 64)
        edge_elements = len(self.elements) - center_elements
        
        if len(self.elements) > 0:
            balance = 1 - abs(center_elements - edge_elements) / len(self.elements)
        else:
            balance = 0
        
        return balance
    
    def _calculate_flow_balance(self) -> float:
        """计算视觉流平衡"""
        # 左右平衡
        left_elements = [e for e in self.elements if e.center_x < 128]
        right_elements = [e for e in self.elements if e.center_x >= 128]
        
        # 上下平衡
        top_elements = [e for e in self.elements if e.center_y < 128]
        bottom_elements = [e for e in self.elements if e.center_y >= 128]
        
        lr_balance = 1 - abs(len(left_elements) - len(right_elements)) / max(len(self.elements), 1)
        tb_balance = 1 - abs(len(top_elements) - len(bottom_elements)) / max(len(self.elements), 1)
        
        return (lr_balance + tb_balance) / 2
    
    def _calculate_color_harmony(self) -> float:
        """计算色彩和谐性"""
        # 检查是否存在互补色或邻近色搭配
        hues = [e.hsv[0] for e in self.elements if e.hsv[1] > 0.15]
        
        if len(hues) < 2:
            return 0.5
        
        # 检查色相分布
        hue_variance = np.std(hues)
        
        # 低方差表示色彩协调
        harmony = 1 - min(1.0, hue_variance * 2)
        
        return harmony
    
    def _analyze_visual_flow(self) -> Dict:
        """分析视觉流"""
        # 寻找视觉焦点
        # 简化：选择对比度最高或位置独特的区域作为关键视点
        key_viewpoint = 0  # 默认中心位置
        
        max_contrast = 0
        for i, elem in enumerate(self.elements):
            # 简化的对比度计算
            h, s, v = elem.hsv
            contrast = s * (1 - abs(v - 0.5))
            if contrast > max_contrast:
                max_contrast = contrast
                key_viewpoint = i
        
        # 计算视觉路径
        paths = self._trace_visual_paths()
        
        return {
            'key_viewpoint': key_viewpoint,
            'paths': paths
        }
    
    def _trace_visual_paths(self) -> List[List[int]]:
        """追踪视觉路径"""
        # 简化：从左上到右下的对角线扫描
        paths = []
        for i in range(self.grid_size):
            path = []
            for j in range(self.grid_size):
                elem_idx = i * self.grid_size + j
                path.append(elem_idx)
            paths.append(path)
        return paths
    
    def generate_comprehensive_report(self) -> Dict:
        """
        生成综合分析报告
        """
        # 执行分析
        self._extract_grid_colors()
        self._build_network()
        stability = self._calculate_stability()
        self.visual_flow = self._analyze_visual_flow()
        
        # 构建报告
        report = {
            'image_path': self.image_path,
            'stability': stability,
            'elements': [elem.to_dict() for elem in self.elements],
            'visual_flow': self.visual_flow,
            'network_stats': {
                'nodes': len(self.elements),
                'edges': len(self.edges)
            }
        }
        
        return report


def analyze_artifact_network(artifact) -> Optional[Dict]:
    """
    分析指定文物图片的网络结构
    
    参数:
        artifact: Artifact模型实例
    
    返回:
        分析报告字典，失败返回None
    """
    # 获取图片路径
    if artifact.image:
        image_path = artifact.image.path
    else:
        return None
    
    if not os.path.exists(image_path):
        return None
    
    try:
        analyzer = PaintingNetworkAnalyzer(image_path)
        report = analyzer.generate_comprehensive_report()
        return report
    except Exception as e:
        print(f"分析失败: {e}")
        return None
