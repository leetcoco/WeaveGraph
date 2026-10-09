"""
中国画结构分解与再组合系统 - 核心图像处理引擎
使用OpenCV和scikit-image实现工业级图像处理
"""
import cv2
import numpy as np
from PIL import Image
import json
import os
from scipy import ndimage
from skimage import morphology, segmentation, measure, feature
from skimage.filters import threshold_multiotsu, sobel
from skimage.segmentation import watershed, slic
from skimage.color import rgb2lab, rgb2gray
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ChinesePaintingAnalyzer:
    """中国画分析器 - 线条提取与区域分割"""
    
    def __init__(self, image_path):
        self.image_path = image_path
        self.original = None
        self.gray = None
        self.edges = None
        self.labels = None
        self.height = 0
        self.width = 0
        
    def load_image(self):
        """加载图像"""
        self.original = cv2.imread(self.image_path)
        if self.original is None:
            raise ValueError(f"无法加载图像: {self.image_path}")
        
        # 转换RGB格式
        self.original = cv2.cvtColor(self.original, cv2.COLOR_BGR2RGB)
        self.gray = cv2.cvtColor(self.original, cv2.COLOR_RGB2GRAY)
        self.height, self.width = self.gray.shape
        return self
    
    def extract_lines_adaptive(self, method='combined'):
        """
        自适应线条提取 - 针对中国画的特殊优化
        
        方法选项:
        - 'canny': 标准Canny边缘检测
        - 'sobel': Sobel梯度算子
        - 'morphological': 形态学边缘
        - 'combined': 组合方法（推荐）
        """
        if self.gray is None:
            self.load_image()
        
        if method == 'canny':
            # 自适应阈值Canny
            median = np.median(self.gray)
            lower = int(max(0, 0.33 * median))
            upper = int(min(255, 1.33 * median))
            self.edges = cv2.Canny(self.gray, lower, upper)
            
        elif method == 'sobel':
            # Sobel梯度
            sobelx = cv2.Sobel(self.gray, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(self.gray, cv2.CV_64F, 0, 1, ksize=3)
            magnitude = np.sqrt(sobelx**2 + sobely**2)
            self.edges = (magnitude > np.percentile(magnitude, 90)).astype(np.uint8) * 255
            
        elif method == 'morphological':
            # 形态学边缘（适合提取轮廓线）
            kernel = np.ones((3, 3), np.uint8)
            dilation = cv2.dilate(self.gray, kernel, iterations=1)
            erosion = cv2.erode(self.gray, kernel, iterations=1)
            self.edges = dilation - erosion
            _, self.edges = cv2.threshold(self.edges, 30, 255, cv2.THRESH_BINARY)
            
        elif method == 'combined':
            # 组合方法：针对中国画的优化
            # 1. 首先进行轻微模糊去噪
            blurred = cv2.GaussianBlur(self.gray, (3, 3), 0)
            
            # 2. Canny边缘检测
            median = np.median(blurred)
            lower = int(max(0, 0.33 * median))
            upper = int(min(255, 1.33 * median))
            canny_edges = cv2.Canny(blurred, lower, upper)
            
            # 3. 自适应阈值提取淡墨线条
            adaptive_thresh = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            # 4. 组合边缘
            self.edges = cv2.bitwise_or(canny_edges, adaptive_thresh)
            
            # 5. 细化线条（骨架化）
            kernel = np.ones((2, 2), np.uint8)
            self.edges = cv2.morphologyEx(self.edges, cv2.MORPH_CLOSE, kernel)
        
        return self.edges
    
    def detect_closed_regions(self, min_area=100, max_area=None):
        """
        封闭区域检测
        基于边缘检测和形态学操作提取封闭区域
        """
        if self.edges is None:
            self.extract_lines_adaptive()
        
        # 闭合边缘
        kernel = np.ones((5, 5), np.uint8)
        closed_edges = cv2.morphologyEx(self.edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        
        # 填充封闭区域
        filled = closed_edges.copy()
        h, w = filled.shape
        mask = np.zeros((h+2, w+2), np.uint8)
        
        # 从边界开始填充，找到背景区域
        cv2.floodFill(filled, mask, (0, 0), 255)
        filled_inv = cv2.bitwise_not(filled)
        
        # 组合得到封闭区域
        regions = cv2.bitwise_or(closed_edges, filled_inv)
        
        # 查找轮廓
        contours, _ = cv2.findContours(regions, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 过滤区域
        valid_contours = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            if max_area and area > max_area:
                continue
            valid_contours.append(cnt)
        
        return valid_contours
    
    def segment_watershed(self, n_markers=50):
        """
        分水岭算法分割 - 适用于山水画的自然区域分割
        """
        if self.gray is None:
            self.load_image()
        
        # 距离变换
        _, thresh = cv2.threshold(self.gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # 去噪
        kernel = np.ones((3, 3), np.uint8)
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
        
        # 确定背景
        sure_bg = cv2.dilate(opening, kernel, iterations=3)
        
        # 距离变换找前景
        dist_transform = cv2.distanceTransform(opening, cv2.DIST_L2, 5)
        _, sure_fg = cv2.threshold(dist_transform, 0.3 * dist_transform.max(), 255, 0)
        sure_fg = np.uint8(sure_fg)
        
        # 未知区域
        unknown = cv2.subtract(sure_bg, sure_fg)
        
        # 标记
        _, markers = cv2.connectedComponents(sure_fg)
        markers = markers + 1
        markers[unknown == 255] = 0
        
        # 分水岭
        img_for_watershed = self.original.copy()
        markers = cv2.watershed(img_for_watershed, markers)
        
        self.labels = markers
        return markers
    
    def segment_slic(self, n_segments=100, compactness=10):
        """
        SLIC超像素分割 - 产生更均匀的区域
        """
        if self.original is None:
            self.load_image()
        
        # SLIC分割
        segments = slic(self.original, n_segments=n_segments, 
                       compactness=compactness, start_label=1)
        
        self.labels = segments
        return segments
    
    def segment_hierarchical(self, n_regions=20):
        """
        层次化分割 - 适用于中国画的语义区域提取
        结合多种方法得到更准确的语义区域
        """
        if self.original is None:
            self.load_image()
        
        # 1. 颜色量化简化
        Z = self.original.reshape((-1, 3))
        Z = np.float32(Z)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels_color, centers = cv2.kmeans(Z, 16, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        
        # 2. 边缘检测
        if self.edges is None:
            self.extract_lines_adaptive()
        
        # 3. 基于边缘的分水岭
        edges_inv = 255 - self.edges
        distance = ndimage.distance_transform_edt(edges_inv)
        
        # 找到峰值作为区域中心
        from skimage.feature import peak_local_max
        local_max = peak_local_max(distance, min_distance=20, 
                                   exclude_border=False)
        
        # 创建标记
        markers = np.zeros(distance.shape, dtype=int)
        for i, (row, col) in enumerate(local_max):
            markers[row, col] = i + 1
        
        # 分水岭分割
        self.labels = watershed(-distance, markers, mask=(self.edges < 128))
        
        # 合并小区域
        self.labels = self._merge_small_regions(self.labels, min_size=500)
        
        return self.labels
    
    def _merge_small_regions(self, labels, min_size=500):
        """合并小区域到相邻的大区域"""
        unique_labels = np.unique(labels)
        merged = labels.copy()
        
        for label in unique_labels:
            if label == 0:  # 背景
                continue
            mask = (labels == label)
            if np.sum(mask) < min_size:
                # 找到最大的相邻区域
                dilated = ndimage.binary_dilation(mask)
                neighbors = labels[dilated & ~mask]
                neighbors = neighbors[neighbors != 0]
                if len(neighbors) > 0:
                    # 合并到最常见的邻居
                    unique, counts = np.unique(neighbors, return_counts=True)
                    merged[mask] = unique[np.argmax(counts)]
        
        # 重新编号
        new_labels = np.zeros_like(merged)
        for i, old_label in enumerate(np.unique(merged)[1:], 1):
            new_labels[merged == old_label] = i
        
        return new_labels
    
    def extract_region_features(self, labels=None):
        """
        提取每个区域的几何和颜色特征
        """
        if labels is None:
            labels = self.labels
        if labels is None:
            labels = self.segment_hierarchical()
        
        regions = []
        props = measure.regionprops(labels, intensity_image=self.gray)
        
        for prop in props:
            region = {
                'id': prop.label,
                'area': prop.area,
                'perimeter': prop.perimeter,
                'bbox': prop.bbox,  # (min_row, min_col, max_row, max_col)
                'centroid': (prop.centroid[1], prop.centroid[0]),  # (x, y)
                'eccentricity': prop.eccentricity,
                'solidity': prop.solidity,
                'extent': prop.extent,
                'major_axis_length': prop.major_axis_length,
                'minor_axis_length': prop.minor_axis_length,
                'orientation': prop.orientation,
                'mean_intensity': prop.mean_intensity,
            }
            
            # 计算长宽比
            minr, minc, maxr, maxc = prop.bbox
            region['aspect_ratio'] = (maxc - minc) / max(1, maxr - minr)
            
            # 提取颜色特征
            mask = (labels == prop.label)
            region_pixels = self.original[mask]
            if len(region_pixels) > 0:
                region['mean_color'] = np.mean(region_pixels, axis=0).tolist()
                region['color_std'] = np.std(region_pixels, axis=0).tolist()
                
                # 计算颜色直方图
                hist = self._compute_color_histogram(region_pixels)
                region['color_histogram'] = hist
            
            regions.append(region)
        
        return regions
    
    def _compute_color_histogram(self, pixels, bins=8):
        """计算简化颜色直方图"""
        # 量化到bins
        pixels_quantized = (pixels // (256 // bins)).astype(int)
        
        # 计算直方图
        hist = np.zeros((bins, bins, bins))
        for p in pixels_quantized:
            hist[p[0], p[1], p[2]] += 1
        
        # 归一化
        hist = hist / len(pixels)
        return hist.tolist()
    
    def classify_semantic_type(self, region):
        """
        基于规则的语义分类
        根据几何和颜色特征推断语义类型
        """
        features = {
            'area': region['area'],
            'aspect_ratio': region['aspect_ratio'],
            'solidity': region.get('solidity', 0),
            'extent': region.get('extent', 0),
            'eccentricity': region.get('eccentricity', 0),
        }
        
        # 颜色分析（RGB）
        if 'mean_color' in region:
            r, g, b = region['mean_color']
            brightness = (r + g + b) / 3
            features['brightness'] = brightness
            
            # 判断蓝绿色调（水体）
            is_blue_green = (b > r + 10) and (g > r + 5)
            # 判断土黄色调（山体/土地）
            is_earth = (r > 100) and (g > 80) and (b < 80)
            # 判断灰色调（云雾/远景）
            is_gray = abs(int(r) - int(g)) < 20 and abs(int(g) - int(b)) < 20 and brightness > 100
            
            features['is_blue_green'] = is_blue_green
            features['is_earth'] = is_earth
            features['is_gray'] = is_gray
        
        # 基于规则的分类
        scores = defaultdict(float)
        
        # 山体：大面积、土黄/灰色、不规则形状
        if features['area'] > 10000:
            scores['mountain'] += 0.3
        if features.get('is_earth'):
            scores['mountain'] += 0.4
        if features['solidity'] < 0.8:
            scores['mountain'] += 0.2
        
        # 水体：蓝绿色调、横向延展、中等面积
        if features.get('is_blue_green'):
            scores['water'] += 0.5
        if features['aspect_ratio'] > 2:
            scores['water'] += 0.2
        
        # 树木：纵向、细长、深色调
        if features['aspect_ratio'] < 0.5 and features['area'] < 50000:
            scores['tree'] += 0.3
        if features.get('brightness', 128) < 80:
            scores['tree'] += 0.2
        
        # 云雾：浅色、大面积、低饱和度
        if features.get('is_gray') and features.get('brightness', 0) > 180:
            scores['cloud'] += 0.5
        if features['area'] > 5000:
            scores['cloud'] += 0.2
        
        # 天空：上方位置、浅蓝/灰白
        centroid_y = region['centroid'][1]
        if centroid_y < self.height * 0.3:
            scores['sky'] += 0.3
            if features.get('is_blue_green') or features.get('is_gray'):
                scores['sky'] += 0.3
        
        # 选择最高分
        if scores:
            best_type = max(scores, key=scores.get)
            confidence = scores[best_type]
        else:
            best_type = 'unknown'
            confidence = 0
        
        return best_type, confidence, dict(scores)
    
    def analyze_depth_layers(self, regions):
        """
        分析深度层次 - 三远法空间层次
        """
        # 按Y坐标分组（中国画通常从上到下是远到近）
        height = self.height
        
        for region in regions:
            cy = region['centroid'][1]
            
            # 划分三层
            if cy < height * 0.35:
                region['depth_layer'] = 'far'  # 远景
                region['depth_order'] = 2
            elif cy < height * 0.65:
                region['depth_layer'] = 'middle'  # 中景
                region['depth_order'] = 1
            else:
                region['depth_layer'] = 'near'  # 近景
                region['depth_order'] = 0
        
        # 根据语义类型调整
        for region in regions:
            semantic = region.get('semantic_type', 'unknown')
            
            # 山体通常在远景
            if semantic == 'mountain' and region['depth_layer'] == 'near':
                if region['area'] > 30000:  # 大山体可能是主峰
                    region['depth_layer'] = 'middle'
                    region['depth_order'] = 1
            
            # 树木在近中景
            if semantic == 'tree':
                if region['depth_layer'] == 'far':
                    region['depth_layer'] = 'middle'
                    region['depth_order'] = 1
        
        return regions
    
    def save_edge_visualization(self, output_path):
        """保存线条可视化结果"""
        if self.edges is None:
            self.extract_lines_adaptive()
        
        # 创建彩色边缘图
        edge_color = np.zeros_like(self.original)
        edge_color[self.edges > 0] = [139, 90, 43]  # 褐色，模拟墨色
        
        # 与原图混合
        result = cv2.addWeighted(self.original, 0.3, edge_color, 0.7, 0)
        
        Image.fromarray(result).save(output_path)
        return output_path
    
    def save_segmentation_visualization(self, output_path):
        """保存分割可视化结果"""
        if self.labels is None:
            self.segment_hierarchical()
        
        # 创建彩色标签图
        from skimage.color import label2rgb
        colored = label2rgb(self.labels, self.original, alpha=0.6, bg_label=0)
        colored = (colored * 255).astype(np.uint8)
        
        Image.fromarray(colored).save(output_path)
        return output_path
    
    def get_region_mask(self, region_id):
        """获取指定区域的掩码"""
        if self.labels is None:
            return None
        return (self.labels == region_id).astype(np.uint8) * 255
    
    def extract_isolated_region(self, region_id, with_alpha=True):
        """提取独立区域图像"""
        mask = self.get_region_mask(region_id)
        if mask is None:
            return None
        
        if with_alpha:
            # 创建带透明通道的图像
            result = np.zeros((self.height, self.width, 4), dtype=np.uint8)
            result[:, :, :3] = self.original
            result[:, :, 3] = mask
        else:
            # 背景为白色
            result = self.original.copy()
            result[mask == 0] = [255, 255, 255]
        
        return result


class CompositionReconstructor:
    """构图重组器 - 基于传统美学规则的图像重组"""
    
    def __init__(self, width=1024, height=768):
        self.width = width
        self.height = height
        self.canvas = None
        self.elements = []
        
    def create_canvas(self, bg_color=(255, 255, 255, 255)):
        """创建画布"""
        self.canvas = np.full((self.height, self.width, 4), bg_color, dtype=np.uint8)
        return self
    
    def apply_three_distances(self, elements_by_depth):
        """
        应用三远法布局
        
        elements_by_depth: {
            'high': [...],  # 高远 - 仰视，山峰在上方
            'level': [...], # 平远 - 平视，横向展开
            'deep': [...]   # 深远 - 俯视，纵深层次
        }
        """
        layout = {}
        
        # 高远布局 - 主峰在上方中央
        if 'high' in elements_by_depth:
            high_elements = elements_by_depth['high']
            for i, elem in enumerate(high_elements):
                # 高远：纵向排列，主峰居中
                x = self.width * 0.3 + (i % 2) * self.width * 0.3
                y = self.height * 0.1 + (i // 2) * self.height * 0.15
                scale = 0.8 - i * 0.1
                layout[elem['id']] = {
                    'x': x, 'y': y,
                    'scale': scale,
                    'z_index': 10 + i
                }
        
        # 平远布局 - 横向分布
        if 'level' in elements_by_depth:
            level_elements = elements_by_depth['level']
            n = len(level_elements)
            for i, elem in enumerate(level_elements):
                x = self.width * (0.1 + 0.8 * i / max(1, n - 1))
                y = self.height * 0.5
                scale = 0.6
                layout[elem['id']] = {
                    'x': x, 'y': y,
                    'scale': scale,
                    'z_index': 5 + i
                }
        
        # 深远布局 - 纵深层次
        if 'deep' in elements_by_depth:
            deep_elements = elements_by_depth['deep']
            for i, elem in enumerate(deep_elements):
                # 深远：S形递进
                x = self.width * (0.2 + 0.6 * (i / max(1, len(deep_elements) - 1))**2)
                y = self.height * (0.4 + 0.4 * i / max(1, len(deep_elements)))
                scale = 0.5 + 0.3 * (1 - i / max(1, len(deep_elements)))
                layout[elem['id']] = {
                    'x': x, 'y': y,
                    'scale': scale,
                    'z_index': i
                }
        
        return layout
    
    def apply_golden_ratio(self, elements, focus_point=None):
        """
        应用黄金分割构图
        """
        phi = 1.618
        
        if focus_point is None:
            # 默认焦点在黄金分割点
            focus_point = (self.width / phi, self.height / phi)
        
        layout = {}
        
        # 按重要性排序元素
        sorted_elements = sorted(elements, 
                                key=lambda e: e.get('area', 0), 
                                reverse=True)
        
        # 主元素放在焦点
        if sorted_elements:
            main_elem = sorted_elements[0]
            layout[main_elem['id']] = {
                'x': focus_point[0] - main_elem.get('width', 100) / 2,
                'y': focus_point[1] - main_elem.get('height', 100) / 2,
                'scale': 1.0,
                'z_index': 10
            }
        
        # 其他元素按黄金螺旋分布
        angle = 0
        for i, elem in enumerate(sorted_elements[1:], 1):
            radius = 50 * (phi ** (i * 0.5))
            angle += 2.39996  # 黄金角
            
            x = focus_point[0] + radius * np.cos(angle)
            y = focus_point[1] + radius * np.sin(angle)
            
            layout[elem['id']] = {
                'x': x, 'y': y,
                'scale': max(0.3, 1.0 - i * 0.15),
                'z_index': 10 - i
            }
        
        return layout
    
    def apply_rule_of_thirds(self, elements):
        """
        应用三分法则
        """
        # 三分线位置
        h_lines = [self.height / 3, 2 * self.height / 3]
        v_lines = [self.width / 3, 2 * self.width / 3]
        
        # 交叉点（视觉焦点）
        focal_points = [
            (v_lines[0], h_lines[0]),
            (v_lines[1], h_lines[0]),
            (v_lines[0], h_lines[1]),
            (v_lines[1], h_lines[1])
        ]
        
        layout = {}
        
        # 排序元素
        sorted_elements = sorted(elements, 
                                key=lambda e: e.get('importance', 0),
                                reverse=True)
        
        # 分配元素到焦点
        for i, elem in enumerate(sorted_elements):
            if i < 4:
                # 重要元素放在交叉点
                fp = focal_points[i]
                layout[elem['id']] = {
                    'x': fp[0] - elem.get('width', 100) / 2,
                    'y': fp[1] - elem.get('height', 100) / 2,
                    'scale': 0.8,
                    'z_index': 10 - i
                }
            else:
                # 其他元素均匀分布
                row = (i - 4) // 3
                col = (i - 4) % 3
                x = self.width * (0.15 + 0.35 * col)
                y = self.height * (0.15 + 0.35 * row)
                layout[elem['id']] = {
                    'x': x, 'y': y,
                    'scale': 0.5,
                    'z_index': 1
                }
        
        return layout
    
    def place_element(self, element_image, position, scale=1.0, rotation=0, z_index=0):
        """
        放置元素到画布
        """
        if self.canvas is None:
            self.create_canvas()
        
        # 缩放
        h, w = element_image.shape[:2]
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = cv2.resize(element_image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        
        # 旋转
        if rotation != 0:
            center = (new_w // 2, new_h // 2)
            M = cv2.getRotationMatrix2D(center, rotation, 1.0)
            resized = cv2.warpAffine(resized, M, (new_w, new_h), 
                                    borderMode=cv2.BORDER_CONSTANT,
                                    borderValue=(0, 0, 0, 0))
        
        # 计算放置位置
        x, y = int(position[0]), int(position[1])
        
        # 边界检查
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(self.width, x + new_w)
        y2 = min(self.height, y + new_h)
        
        # 裁剪源图像
        src_x1 = max(0, -x)
        src_y1 = max(0, -y)
        src_x2 = src_x1 + (x2 - x1)
        src_y2 = src_y1 + (y2 - y1)
        
        # Alpha混合
        if resized.shape[2] == 4:
            src_rgba = resized[src_y1:src_y2, src_x1:src_x2]
            src_rgb = src_rgba[:, :, :3]
            src_alpha = src_rgba[:, :, 3:4].astype(float) / 255.0
            
            dst_rgb = self.canvas[y1:y2, x1:x2, :3]
            dst_alpha = self.canvas[y1:y2, x1:x2, 3:4].astype(float) / 255.0
            
            # 混合公式
            out_alpha = src_alpha + dst_alpha * (1 - src_alpha)
            out_rgb = (src_rgb * src_alpha + dst_rgb * dst_alpha * (1 - src_alpha)) / np.maximum(out_alpha, 0.001)
            
            self.canvas[y1:y2, x1:x2, :3] = out_rgb.astype(np.uint8)
            self.canvas[y1:y2, x1:x2, 3] = (out_alpha * 255).astype(np.uint8)
        else:
            self.canvas[y1:y2, x1:x2] = resized[src_y1:src_y2, src_x1:src_x2]
        
        self.elements.append({
            'position': (x, y),
            'scale': scale,
            'rotation': rotation,
            'z_index': z_index
        })
        
        return self
    
    def save_result(self, output_path):
        """保存结果图像"""
        if self.canvas is None:
            return None
        
        # 转换到PIL并保存
        img = Image.fromarray(self.canvas)
        img.save(output_path, quality=95)
        return output_path


# 便捷函数
def analyze_painting(image_path, output_dir):
    """
    完整的画作分析流程
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 初始化分析器
    analyzer = ChinesePaintingAnalyzer(image_path)
    analyzer.load_image()
    
    # 提取线条
    edges = analyzer.extract_lines_adaptive('combined')
    edge_path = os.path.join(output_dir, 'edges.png')
    analyzer.save_edge_visualization(edge_path)
    
    # 分割区域
    labels = analyzer.segment_hierarchical(n_regions=25)
    seg_path = os.path.join(output_dir, 'segments.png')
    analyzer.save_segmentation_visualization(seg_path)
    
    # 提取特征
    regions = analyzer.extract_region_features()
    
    # 语义分类
    for region in regions:
        semantic_type, confidence, scores = analyzer.classify_semantic_type(region)
        region['semantic_type'] = semantic_type
        region['confidence'] = confidence
        region['semantic_scores'] = scores
    
    # 深度分析
    regions = analyzer.analyze_depth_layers(regions)
    
    # 保存结果
    result = {
        'image_size': {'width': analyzer.width, 'height': analyzer.height},
        'region_count': len(regions),
        'regions': regions,
        'edge_image': edge_path,
        'segmentation_image': seg_path,
    }
    
    # 保存JSON
    json_path = os.path.join(output_dir, 'analysis.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return result
