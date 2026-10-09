from django.core.management.base import BaseCommand
import pandas as pd
from artifacts.models import Artifact, Category, Exhibition
from django.utils.text import slugify
from django.core.files import File
import os

class Command(BaseCommand):
    help = '从Excel文件导入文物数据'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Excel文件路径')
        parser.add_argument('--image-dir', type=str, help='图片目录路径')

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        image_dir = kwargs.get('image_dir', '')

        self.stdout.write(self.style.SUCCESS(f'开始导入数据从 {file_path}'))

        try:
            # 读取Excel文件
            df = pd.read_excel(file_path)
            
            # 显示列名
            self.stdout.write(self.style.WARNING('Excel文件列名:'))
            self.stdout.write(str(df.columns.tolist()))

            # 统计
            total_rows = len(df)
            imported = 0
            skipped = 0
            errors = 0

            for index, row in df.iterrows():
                try:
                    # 获取数据 (根据实际Excel列名调整)
                    name = row.get('文物名称', row.get('名称', ''))
                    if not name:
                        self.stdout.write(self.style.WARNING(f'第{index+2}行: 缺少文物名称，跳过'))
                        skipped += 1
                        continue

                    # 获取或创建分类
                    category_name = row.get('分类', row.get('类别', '其他'))
                    category, created = Category.objects.get_or_create(
                        name=category_name,
                        defaults={'slug': slugify(category_name)}
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f'创建新分类: {category_name}'))

                    # 准备文物数据
                    artifact_data = {
                        'name': name,
                        'slug': slugify(name) + f'_{index}',
                        'description': row.get('描述', row.get('简介', '')),
                        'category': category,
                        'era': row.get('年代', '未知'),
                        'color': row.get('颜色', '未知'),
                        'material': row.get('材质', ''),
                        'dimensions': row.get('尺寸', ''),
                        'collection_number': row.get('收藏编号', row.get('编号', '')),
                    }

                    # 检查是否已存在
                    collection_number = artifact_data['collection_number']
                    if collection_number:
                        existing = Artifact.objects.filter(collection_number=collection_number).first()
                        if existing:
                            self.stdout.write(self.style.WARNING(f'第{index+2}行: 文物 {name} (编号: {collection_number}) 已存在，跳过'))
                            skipped += 1
                            continue

                    # 创建文物对象
                    artifact = Artifact(**artifact_data)

                    # 处理图片
                    image_path = row.get('图片', row.get('图片路径', ''))
                    if image_path and image_dir:
                        full_image_path = os.path.join(image_dir, image_path)
                        if os.path.exists(full_image_path):
                            with open(full_image_path, 'rb') as f:
                                artifact.image.save(os.path.basename(image_path), File(f), save=False)

                    artifact.save()
                    imported += 1
                    self.stdout.write(self.style.SUCCESS(f'第{index+2}行: 成功导入文物 {name}'))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'第{index+2}行: 导入失败 - {str(e)}'))
                    errors += 1

            # 输出统计
            self.stdout.write(self.style.SUCCESS('\n导入完成!'))
            self.stdout.write(f'总行数: {total_rows}')
            self.stdout.write(f'成功导入: {imported}')
            self.stdout.write(f'跳过: {skipped}')
            self.stdout.write(f'错误: {errors}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'读取Excel文件失败: {str(e)}'))
