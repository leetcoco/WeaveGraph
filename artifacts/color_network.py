"""
基于颜色相似度的小世界网络构建模块
用于分析中国画作之间的颜色关系
"""

import json
import numpy as np
from collections import defaultdict
from typing import List, Dict, Tuple, Set
import colorsys


class ColorNode:
    """颜色节点"""
    def __init__(self, color_hex: str, artifact_id: int = None, artifact_name: str = None):
        self.color_hex = color_hex.upper()
        self.artifact_id = artifact_id
        self.artifact_name = artifact_name
        self.rgb = self._hex_to_rgb(color_hex)
        self.hsv = self._rgb_to_hsv(self.rgb)
        
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """将十六进制颜色转换为RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _rgb_to_hsv(self, rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
        """将RGB转换为HSV"""
        r, g, b = rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0
        return colorsys.rgb_to_hsv(r, g, b)
    
    def __repr__(self):
        return f"ColorNode({self.color_hex})"


class ColorNetwork:
    """颜色小世界网络 - 使用色系聚类"""
    
    def __init__(self, color_cluster_threshold: float = 0.15):
        """
        初始化颜色网络
        
        参数:
            color_cluster_threshold: 颜色聚类阈值，小于此距离的颜色归为一类
        """
        self.nodes: Dict[str, ColorNode] = {}  # 代表性颜色 -> ColorNode
        self.edges: Dict[str, List[Tuple[str, float]]] = defaultdict(list)  # 代表性颜色 -> [(neighbor_hex, weight), ...]
        self.artifact_colors: Dict[int, List[str]] = defaultdict(list)  # artifact_id -> [代表性颜色, ...]
        self.color_clusters: Dict[str, str] = {}  # 原始颜色 -> 代表性颜色映射
        self.cluster_threshold = color_cluster_threshold
        
    def _get_representative_color(self, color_hex: str) -> str:
        """
        获取颜色的代表性颜色（色系）
        如果相似的颜色已存在，返回已有代表性颜色；否则返回自身
        """
        color_hex = color_hex.upper()
        
        # 如果已有映射，直接返回
        if color_hex in self.color_clusters:
            return self.color_clusters[color_hex]
        
        # 检查是否与已有节点相似
        new_node = ColorNode(color_hex)
        min_dist = float('inf')
        closest_rep = None
        
        for rep_hex, node in self.nodes.items():
            dist = self.calculate_color_distance(new_node, node)
            if dist < min_dist:
                min_dist = dist
                closest_rep = rep_hex
        
        # 如果距离小于阈值，归为同一色系
        if min_dist < self.cluster_threshold and closest_rep:
            self.color_clusters[color_hex] = closest_rep
            return closest_rep
        else:
            # 新建色系，自身作为代表性颜色
            self.color_clusters[color_hex] = color_hex
            if color_hex not in self.nodes:
                self.nodes[color_hex] = new_node
            return color_hex
    
    def add_artifact(self, artifact_id: int, artifact_name: str, color_palette: List[str]):
        """添加画作及其颜色调色板（自动聚类到色系）"""
        representative_colors = []
        for color_hex in color_palette:
            rep_color = self._get_representative_color(color_hex)
            representative_colors.append(rep_color)
        
        # 去重（同一画作中可能有多个颜色归到同一色系）
        unique_reps = list(dict.fromkeys(representative_colors))
        self.artifact_colors[artifact_id] = unique_reps
    
    def calculate_color_distance(self, color1: ColorNode, color2: ColorNode, 
                                 rgb_weight: float = 0.4, 
                                 hsv_weight: float = 0.6) -> float:
        """
        计算两种颜色之间的距离
        结合RGB空间欧氏距离和HSV空间感知距离
        返回: 距离值 (0-1, 越小越相似)
        """
        # RGB欧氏距离 (归一化到0-1)
        rgb_dist = np.sqrt(sum((a - b) ** 2 for a, b in zip(color1.rgb, color2.rgb))) / 441.67  # sqrt(3*255^2)
        
        # HSV感知距离
        h1, s1, v1 = color1.hsv
        h2, s2, v2 = color2.hsv
        
        # 色相距离 (考虑环形特性)
        h_dist = min(abs(h1 - h2), 1 - abs(h1 - h2))
        
        # 饱和度距离
        s_dist = abs(s1 - s2)
        
        # 明度距离
        v_dist = abs(v1 - v2)
        
        # HSV综合距离
        hsv_dist = (h_dist * 0.5 + s_dist * 0.3 + v_dist * 0.2)
        
        # 加权综合
        total_dist = rgb_dist * rgb_weight + hsv_dist * hsv_weight
        
        return min(1.0, total_dist)
    
    def build_network(self, similarity_threshold: float = 0.3, max_neighbors: int = 5):
        """
        构建小世界网络
        
        参数:
            similarity_threshold: 相似度阈值，小于此距离的颜色建立连接
            max_neighbors: 每个节点的最大邻居数
        """
        color_list = list(self.nodes.values())
        
        for i, color1 in enumerate(color_list):
            distances = []
            
            for j, color2 in enumerate(color_list):
                if i == j:
                    continue
                    
                dist = self.calculate_color_distance(color1, color2)
                
                # 只保留相似度在阈值内的颜色
                if dist < similarity_threshold:
                    distances.append((color2.color_hex, dist))
            
            # 按距离排序，取最近的max_neighbors个
            distances.sort(key=lambda x: x[1])
            top_neighbors = distances[:max_neighbors]
            
            # 建立边连接 (权重为 1 - 距离，即相似度)
            for neighbor_hex, dist in top_neighbors:
                weight = 1 - dist
                self.edges[color1.color_hex].append((neighbor_hex, weight))
                
        print(f"网络构建完成: {len(self.nodes)} 个节点, {sum(len(v) for v in self.edges.values())} 条边")
    
    def get_network_stats(self) -> Dict:
        """获取网络统计信息"""
        if not self.edges:
            return {}
            
        # 计算平均度
        degrees = [len(neighbors) for neighbors in self.edges.values()]
        avg_degree = np.mean(degrees) if degrees else 0
        
        # 计算网络密度
        n = len(self.nodes)
        max_edges = n * (n - 1) / 2 if n > 1 else 1
        actual_edges = sum(len(v) for v in self.edges.values()) / 2  # 无向图，边数除以2
        density = actual_edges / max_edges
        
        # 计算聚类系数
        clustering_coeffs = []
        for color_hex, neighbors in self.edges.items():
            if len(neighbors) < 2:
                continue
            neighbor_set = set(n[0] for n in neighbors)
            triangles = 0
            for n1, _ in neighbors:
                for n2, _ in self.edges[n1]:
                    if n2 in neighbor_set:
                        triangles += 1
            possible = len(neighbors) * (len(neighbors) - 1)
            if possible > 0:
                clustering_coeffs.append(triangles / possible)
        
        avg_clustering = np.mean(clustering_coeffs) if clustering_coeffs else 0
        
        return {
            'node_count': len(self.nodes),
            'edge_count': int(actual_edges),
            'avg_degree': round(avg_degree, 2),
            'density': round(density, 4),
            'avg_clustering_coefficient': round(avg_clustering, 4),
            'is_small_world': avg_clustering > 0.3 and density < 0.5
        }
    
    def find_similar_artifacts(self, artifact_id: int, top_k: int = 5) -> List[Tuple[int, float]]:
        """
        查找与指定画作最相似的其他画作
        基于颜色网络中的共享邻居
        """
        if artifact_id not in self.artifact_colors:
            return []
        
        target_colors = set(self.artifact_colors[artifact_id])
        similarities = []
        
        for other_id, other_colors in self.artifact_colors.items():
            if other_id == artifact_id:
                continue
            
            # 计算颜色相似度得分
            score = 0
            for color1 in target_colors:
                for color2 in other_colors:
                    if color1 == color2:
                        score += 1.0  # 相同颜色
                    else:
                        # 检查是否在邻居中
                        neighbors = dict(self.edges.get(color1, []))
                        if color2 in neighbors:
                            score += neighbors[color2] * 0.5  # 邻居颜色，加权
            
            # 归一化
            max_possible = max(len(target_colors), len(other_colors))
            normalized_score = score / max_possible if max_possible > 0 else 0
            
            if normalized_score > 0:
                similarities.append((other_id, normalized_score))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def find_similar_artifacts_all_colors_match(self, artifact_id: int, top_k: int = 5) -> List[Tuple[int, float]]:
        """
        查找与指定画作最相似的其他画作（要求所有色系都匹配）
        只有当推荐画作包含目标画作的所有色系时，才认为是相似的
        """
        if artifact_id not in self.artifact_colors:
            return []
        
        target_colors = set(self.artifact_colors[artifact_id])
        if not target_colors:
            return []
        
        similarities = []
        
        for other_id, other_colors in self.artifact_colors.items():
            if other_id == artifact_id:
                continue
            
            other_colors_set = set(other_colors)
            
            # 检查是否包含目标画作的所有色系（必须全部匹配）
            if not target_colors.issubset(other_colors_set):
                continue  # 跳过不满足所有色系匹配的画作
            
            # 计算相似度得分（基于共同色系数量的比例）
            common_colors = target_colors & other_colors_set
            extra_colors = other_colors_set - target_colors
            
            # 基础得分：所有目标色系都匹配得满分1.0
            # 额外色系越少越好（更精确匹配）
            base_score = 1.0
            penalty = len(extra_colors) * 0.1  # 每个额外色系扣0.1分
            score = max(0.5, base_score - penalty)  # 最低0.5分
            
            similarities.append((other_id, score))
        
        # 按得分排序，返回前top_k个
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def random_walk_recommendation(self, start_color: str, steps: int = 3, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        基于随机游走的颜色推荐
        """
        if start_color not in self.nodes:
            return []
        
        visit_counts = defaultdict(float)
        current_color = start_color
        
        for _ in range(steps):
            neighbors = self.edges.get(current_color, [])
            if not neighbors:
                break
            
            # 按权重随机选择下一个节点
            weights = [w for _, w in neighbors]
            total_weight = sum(weights)
            if total_weight == 0:
                break
            
            probs = [w / total_weight for w in weights]
            next_idx = np.random.choice(len(neighbors), p=probs)
            next_color, weight = neighbors[next_idx]
            
            visit_counts[next_color] += weight
            current_color = next_color
        
        # 返回访问频率最高的颜色
        recommendations = sorted(visit_counts.items(), key=lambda x: x[1], reverse=True)
        return recommendations[:top_k]
    
    def export_network_data(self) -> Dict:
        """导出网络数据用于可视化"""
        nodes_data = []
        for color_hex, node in self.nodes.items():
            nodes_data.append({
                'id': color_hex,
                'color': color_hex,
                'rgb': node.rgb,
                'artifact_id': node.artifact_id,
                'artifact_name': node.artifact_name
            })
        
        edges_data = []
        for source, targets in self.edges.items():
            for target, weight in targets:
                edges_data.append({
                    'source': source,
                    'target': target,
                    'weight': weight
                })
        
        return {
            'nodes': nodes_data,
            'edges': edges_data,
            'stats': self.get_network_stats()
        }


def build_color_network_from_artifacts(artifacts_data: List[Dict]) -> ColorNetwork:
    """
    从画作数据构建颜色网络（使用更严格的参数）
    
    参数:
        artifacts_data: 画作数据列表，每个元素包含 'id', 'name', 'color_palette'
    """
    network = ColorNetwork()
    
    for artifact in artifacts_data:
        artifact_id = artifact.get('id')
        artifact_name = artifact.get('name', '')
        color_palette = artifact.get('color_palette', [])
        
        if artifact_id and color_palette:
            network.add_artifact(artifact_id, artifact_name, color_palette)
    
    # 构建网络（使用更严格的参数减少边数）
    # similarity_threshold=0.25 只连接非常相似的颜色
    # max_neighbors=3 限制每个节点的最大连接数
    network.build_network(similarity_threshold=0.25, max_neighbors=3)
    
    return network


# 示例用法
if __name__ == '__main__':
    # 模拟数据
    test_artifacts = [
        {'id': 1, 'name': '画作A', 'color_palette': ['#8B4513', '#D2691E', '#F4A460']},
        {'id': 2, 'name': '画作B', 'color_palette': ['#CD853F', '#DEB887', '#8B4513']},
        {'id': 3, 'name': '画作C', 'color_palette': ['#2F4F4F', '#708090', '#778899']},
    ]
    
    network = build_color_network_from_artifacts(test_artifacts)
    
    # 打印统计
    stats = network.get_network_stats()
    print("网络统计:", stats)
    
    # 查找相似画作
    similar = network.find_similar_artifacts(1)
    print("与画作1相似的画作:", similar)
    
    # 导出数据
    data = network.export_network_data()
    print(f"节点数: {len(data['nodes'])}, 边数: {len(data['edges'])}")
