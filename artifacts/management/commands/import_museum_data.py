from django.core.management.base import BaseCommand
import pandas as pd
from artifacts.models import Artifact, Category, Exhibition
from django.utils.text import slugify
import os


class Command(BaseCommand):
    help = '从标准格式的Excel文件导入博物馆文物数据'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Excel文件路径')
        parser.add_argument('--source', type=str, help='数据来源标识 (如 MoMA, Smithsonian, Cooper Hewitt)')
        parser.add_argument('--batch-size', type=int, default=100, help='批量处理大小')

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        source = kwargs.get('source', '')
        batch_size = kwargs.get('batch_size', 100)

        self.stdout.write(self.style.SUCCESS(f'开始导入博物馆数据从 {file_path}'))

        try:
            # 读取Excel文件
            df = pd.read_excel(file_path)
            self.stdout.write(self.style.WARNING(f'读取到 {len(df)} 条记录'))
            self.stdout.write(self.style.WARNING('Excel文件列名:'))
            self.stdout.write(str(df.columns.tolist()))

            # 统计
            total_rows = len(df)
            imported = 0
            updated = 0
            skipped = 0
            errors = 0

            # 创建展览（如果提供了来源）
            exhibition = None
            if source:
                exhibition_title = f'{source} 特展'
                exhibition, created = Exhibition.objects.get_or_create(
                    slug=slugify(exhibition_title),
                    defaults={
                        'title': exhibition_title,
                        'description': f'来自 {source} 的文物收藏',
                        'start_date': '1900-01-01',
                        'end_date': '2099-12-31',
                        'is_active': True
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'创建新展览: {exhibition_title}'))

            for index, row in df.iterrows():
                try:
                    # 获取数据（使用标准字段名）
                    name = row.get('文物名称', '')
                    if not name or pd.isna(name):
                        self.stdout.write(self.style.WARNING(f'第{index+2}行: 缺少文物名称，跳过'))
                        skipped += 1
                        continue

                    category_name = row.get('分类', '其他')
                    description = row.get('描述', '')
                    era = row.get('年代', '未知')
                    color = row.get('颜色', '未知')
                    material = row.get('材质', '')
                    dimensions = row.get('尺寸', '')
                    collection_number = row.get('收藏编号', '')
                    data_source = row.get('来源', source)

                    # 获取或创建分类
                    category, created = Category.objects.get_or_create(
                        name=category_name,
                        defaults={'slug': slugify(category_name)}
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f'创建新分类: {category_name}'))

                    # 检查是否已存在（通过收藏编号）
                    artifact = None
                    if collection_number and pd.notna(collection_number):
                        existing = Artifact.objects.filter(collection_number=str(collection_number)).first()
                        if existing:
                            # 更新现有记录
                            existing.name = name
                            existing.description = str(description)[:5000] if pd.notna(description) else ''
                            existing.category = category
                            existing.era = str(era)[:100] if pd.notna(era) else '未知'
                            existing.color = str(color)[:50] if pd.notna(color) else '未知'
                            existing.material = str(material)[:100] if pd.notna(material) else ''
                            existing.dimensions = str(dimensions)[:200] if pd.notna(dimensions) else ''
                            existing.exhibition = exhibition
                            existing.save()
                            updated += 1

                            if (index + 1) % batch_size == 0:
                                self.stdout.write(self.style.SUCCESS(f'第{index+2}行: 更新文物 {name}'))
                            continue

                    # 创建新文物
                    artifact = Artifact(
                        name=str(name)[:200],
                        slug=slugify(name) + f'_{index}',
                        description=str(description)[:5000] if pd.notna(description) else '',
                        category=category,
                        era=str(era)[:100] if pd.notna(era) else '未知',
                        color=str(color)[:50] if pd.notna(color) else '未知',
                        material=str(material)[:100] if pd.notna(material) else '',
                        dimensions=str(dimensions)[:200] if pd.notna(dimensions) else '',
                        collection_number=str(collection_number)[:100] if pd.notna(collection_number) else '',
                        exhibition=exhibition,
                        is_active=True
                    )

                    artifact.save()
                    imported += 1

                    if (index + 1) % batch_size == 0:
                        self.stdout.write(self.style.SUCCESS(f'第{index+2}行: 成功导入文物 {name}'))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'第{index+2}行: 导入失败 - {str(e)}'))
                    errors += 1

            # 输出统计
            self.stdout.write(self.style.SUCCESS('\n' + '='*60))
            self.stdout.write(self.style.SUCCESS('导入完成!'))
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(f'总记录数: {total_rows}')
            self.stdout.write(f'新导入: {imported}')
            self.stdout.write(f'更新: {updated}')
            self.stdout.write(f'跳过: {skipped}')
            self.stdout.write(f'错误: {errors}')
            self.stdout.write(f'成功率: {((imported + updated) / total_rows * 100):.1f}%')

            # 显示分类统计
            self.stdout.write(self.style.WARNING('\n分类统计:'))
            category_stats = Category.objects.all().order_by('-id')[:10]
            for cat in category_stats:
                count = Artifact.objects.filter(category=cat).count()
                self.stdout.write(f'  {cat.name}: {count} 件')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'读取Excel文件失败: {str(e)}'))
            import traceback
            self.stdout.write(traceback.format_exc())
