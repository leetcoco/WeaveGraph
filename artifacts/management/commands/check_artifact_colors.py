"""
检查画作颜色数据的管理命令
用法: python manage.py check_artifact_colors [artifact_id]
"""

from django.core.management.base import BaseCommand
from artifacts.models import Artifact
import json


class Command(BaseCommand):
    help = '检查画作的颜色数据'

    def add_arguments(self, parser):
        parser.add_argument(
            'artifact_id',
            nargs='?',
            type=int,
            help='指定画作ID进行检查'
        )

    def handle(self, *args, **options):
        artifact_id = options.get('artifact_id')
        
        if artifact_id:
            # 检查指定画作
            try:
                art = Artifact.objects.get(id=artifact_id)
                self.stdout.write(self.style.SUCCESS(f'画作ID: {art.id}'))
                self.stdout.write(f'名称: {art.name}')
                self.stdout.write(f'Slug: {art.slug}')
                self.stdout.write(f'是否激活: {art.is_active}')
                self.stdout.write(f'Color Palette: {art.color_palette}')
                
                if art.color_palette:
                    try:
                        palette = json.loads(art.color_palette) if isinstance(art.color_palette, str) else art.color_palette
                        self.stdout.write(self.style.SUCCESS(f'解析成功: {palette}'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'解析失败: {e}'))
                else:
                    self.stdout.write(self.style.WARNING('无调色板数据'))
                    
            except Artifact.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'画作ID {artifact_id} 不存在'))
        else:
            # 统计所有画作
            total = Artifact.objects.count()
            active = Artifact.objects.filter(is_active=True).count()
            with_palette = Artifact.objects.exclude(color_palette__isnull=True).exclude(color_palette='').count()
            
            self.stdout.write(self.style.SUCCESS('画作颜色数据统计'))
            self.stdout.write(f'总画作数: {total}')
            self.stdout.write(f'激活画作: {active}')
            self.stdout.write(f'有调色板: {with_palette}')
            
            # 显示一些示例
            self.stdout.write('\n有调色板的画作示例:')
            for art in Artifact.objects.exclude(color_palette__isnull=True).exclude(color_palette='')[:5]:
                try:
                    palette = json.loads(art.color_palette) if isinstance(art.color_palette, str) else art.color_palette
                    self.stdout.write(f'  ID {art.id}: {art.name} - {palette}')
                except:
                    self.stdout.write(f'  ID {art.id}: {art.name} - [解析失败]')
