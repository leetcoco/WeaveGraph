from django.core.management.base import BaseCommand
import pandas as pd
from artifacts.models import Artifact, Category, Exhibition
from django.utils import timezone

class Command(BaseCommand):
    help = '导出文物数据到Excel文件'

    def add_arguments(self, parser):
        parser.add_argument('output_path', type=str, help='输出Excel文件路径')
        parser.add_argument('--include-images', action='store_true', help='是否包含图片路径')

    def handle(self, *args, **kwargs):
        output_path = kwargs['output_path']
        include_images = kwargs.get('include_images', False)

        self.stdout.write(self.style.SUCCESS(f'开始导出数据到 {output_path}'))

        try:
            # 获取所有文物数据
            artifacts = Artifact.objects.all().select_related('category', 'exhibition')

            # 准备数据
            data = []
            for artifact in artifacts:
                row = {
                    '文物名称': artifact.name,
                    '分类': artifact.category.name if artifact.category else '',
                    '年代': artifact.era,
                    '颜色': artifact.color,
                    '材质': artifact.material,
                    '尺寸': artifact.dimensions,
                    '收藏编号': artifact.collection_number,
                    '描述': artifact.description,
                    '所属展览': artifact.exhibition.title if artifact.exhibition else '',
                    '创建时间': artifact.created_at.strftime('%Y-%m-%d %H:%M:%S') if artifact.created_at else '',
                    '更新时间': artifact.updated_at.strftime('%Y-%m-%d %H:%M:%S') if artifact.updated_at else '',
                }
                
                if include_images:
                    row['图片路径'] = artifact.image.name if artifact.image else ''
                    row['缩略图路径'] = artifact.image_thumbnail.name if artifact.image_thumbnail else ''
                
                data.append(row)

            # 创建DataFrame
            df = pd.DataFrame(data)

            # 保存到Excel
            df.to_excel(output_path, index=False, engine='openpyxl')

            # 输出统计
            self.stdout.write(self.style.SUCCESS('\n导出完成!'))
            self.stdout.write(f'总文物数: {len(artifacts)}')
            self.stdout.write(f'输出文件: {output_path}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'导出失败: {str(e)}'))
