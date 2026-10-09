"""
构建颜色小世界网络的管理命令
用法: python manage.py build_color_network
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from artifacts.models import Artifact
from artifacts.color_network import build_color_network_from_artifacts
import json


class Command(BaseCommand):
    help = '基于画作颜色构建小世界网络'

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.35,
            help='颜色相似度阈值 (默认: 0.35)'
        )
        parser.add_argument(
            '--max-neighbors',
            type=int,
            default=5,
            help='每个节点的最大邻居数 (默认: 5)'
        )
        parser.add_argument(
            '--output',
            type=str,
            default='color_network.json',
            help='输出文件路径 (默认: color_network.json)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('开始构建颜色小世界网络...'))
        
        # 获取所有画作
        artifacts = Artifact.objects.filter(is_active=True).exclude(color_palette__isnull=True)
        total = artifacts.count()
        
        self.stdout.write(f'找到 {total} 幅画作')
        
        if total == 0:
            self.stdout.write(self.style.WARNING('没有找到带有调色板的画作'))
            return
        
        # 准备数据
        artifacts_data = []
        for artifact in artifacts:
            try:
                color_palette = json.loads(artifact.color_palette) if isinstance(artifact.color_palette, str) else artifact.color_palette
                if color_palette:
                    artifacts_data.append({
                        'id': artifact.id,
                        'name': artifact.name,
                        'color_palette': color_palette
                    })
            except:
                continue
        
        self.stdout.write(f'成功解析 {len(artifacts_data)} 幅画作的调色板')
        
        # 构建网络
        network = build_color_network_from_artifacts(artifacts_data)
        
        # 获取统计信息
        stats = network.get_network_stats()
        
        self.stdout.write(self.style.SUCCESS('\n网络构建完成！'))
        self.stdout.write(f'节点数: {stats["node_count"]}')
        self.stdout.write(f'边数: {stats["edge_count"]}')
        self.stdout.write(f'平均度: {stats["avg_degree"]}')
        self.stdout.write(f'网络密度: {stats["density"]}')
        self.stdout.write(f'平均聚类系数: {stats["avg_clustering_coefficient"]}')
        self.stdout.write(f'是否小世界网络: {stats["is_small_world"]}')
        
        # 导出网络数据
        network_data = network.export_network_data()
        output_path = options['output']
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(network_data, f, ensure_ascii=False, indent=2)
        
        self.stdout.write(self.style.SUCCESS(f'\n网络数据已保存到: {output_path}'))
        
        # 示例：查找相似画作
        self.stdout.write('\n示例 - 查找相似画作:')
        for artifact_id in list(network.artifact_colors.keys())[:3]:
            similar = network.find_similar_artifacts(artifact_id, top_k=3)
            if similar:
                artifact_name = network.nodes[network.artifact_colors[artifact_id][0]].artifact_name
                self.stdout.write(f'  {artifact_name}:')
                for sim_id, score in similar:
                    sim_colors = network.artifact_colors[sim_id]
                    sim_name = network.nodes[sim_colors[0]].artifact_name if sim_colors else 'Unknown'
                    self.stdout.write(f'    - {sim_name} (相似度: {score:.2f})')
