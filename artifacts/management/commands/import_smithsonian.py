from django.core.management.base import BaseCommand
import json
import os
from artifacts.models import Artifact, Category, Exhibition
from django.utils.text import slugify

class Command(BaseCommand):
    help = '从 Smithsonian JSONL 文件导入文物数据'
    
    def add_arguments(self, parser):
        parser.add_argument('--jsonl-file', type=str, default='smithsonian_sample.txt', help='JSONL文件路径 (默认: smithsonian_sample.txt)')
        parser.add_argument('--limit', type=int, default=None, help='限制导入的记录数 (用于测试)')
        parser.add_argument('--exhibition', type=str, default='Smithsonian 特展', help='展览标题')
        parser.add_argument('--unit-code', type=str, default='', help='机构代码 (如 NMAAHC, NASM, NMAH 等)')
    
    def handle(self, *args, **options):
        jsonl_file = options['jsonl_file']
        limit = options['limit']
        exhibition_title = options['exhibition']
        unit_code = options['unit_code']
        
        if not os.path.exists(jsonl_file):
            self.stdout.write(self.style.ERROR(f'文件不存在: {jsonl_file}'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'开始导入 Smithsonian 数据从 {jsonl_file}'))
        
        # 读取JSONL文件
        data = []
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if line.strip():
                        try:
                            data.append(json.loads(line))
                            if limit and i >= limit - 1:
                                break
                        except json.JSONDecodeError as e:
                            self.stdout.write(self.style.WARNING(f'第{i+1}行: JSON解析失败 - {e}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'读取文件失败: {e}'))
            return
        
        self.stdout.write(self.style.WARNING(f'读取到 {len(data)} 条记录'))
        
        # 创建展览
        exhibition, created = Exhibition.objects.get_or_create(
            slug=slugify(exhibition_title) if exhibition_title.strip() else 'smithsonian',
            defaults={
                'title': exhibition_title if exhibition_title.strip() else 'Smithsonian',
                'description': '来自 Smithsonian 博物馆的文物收藏',
                'start_date': '1900-01-01',
                'end_date': '2099-12-31',
                'is_active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'创建新展览: {exhibition.title}'))
        
        total = len(data)
        imported = 0
        updated = 0
        skipped = 0
        errors = 0
        
        # 预获取已存在的收藏编号
        existing_numbers = set(Artifact.objects.values_list('collection_number', flat=True))
        
        for i, item in enumerate(data):
            try:
                # 提取标题
                title = item.get('title', '')
                if not title or title.strip() == '':
                    # 尝试从content中提取
                    content = item.get('content', {})
                    if isinstance(content, dict):
                        freetext = content.get('freetext', {})
                        if isinstance(freetext, dict):
                            title_list = freetext.get('title', [])
                            if title_list and isinstance(title_list, list) and len(title_list) > 0:
                                title = title_list[0].get('content', '')
                
                if not title or title.strip() == '':
                    # 使用ID作为后备
                    title = item.get('id', f'文物 {i}')
                
                # 提取描述
                description_parts = []
                content = item.get('content', {})
                if isinstance(content, dict):
                    # 从freetext.notes获取描述
                    freetext = content.get('freetext', {})
                    if isinstance(freetext, dict):
                        notes = freetext.get('notes', [])
                        if notes and isinstance(notes, list) and len(notes) > 0:
                            for note in notes:
                                if isinstance(note, dict) and 'content' in note:
                                    description_parts.append(note['content'][:500])
                    
                    # 从scopecontent获取
                    scopecontent = freetext.get('scopecontent', [])
                    if scopecontent and isinstance(scopecontent, list) and len(scopecontent) > 0:
                        for scope in scopecontent:
                            if isinstance(scope, dict) and 'content' in scope:
                                description_parts.append(scope['content'][:500])
                
                description = ' | '.join(description_parts) if description_parts else '暂无描述'
                
                # 提取分类
                category_name = 'Smithsonian'
                if unit_code:
                    category_name = f'Smithsonian-{unit_code}'
                
                # 提取类型信息
                item_type = item.get('type', '')
                if item_type:
                    category_name = f'{category_name} ({item_type})'
                
                # 获取或创建分类
                category_slug = slugify(category_name)
                if not category_slug or category_slug.strip() == '':
                    category_slug = 'smithsonian'
                
                category, created = Category.objects.get_or_create(
                    slug=category_slug,
                    defaults={'name': category_name}
                )
                if created and i % 100 == 0:
                    self.stdout.write(self.style.SUCCESS(f'创建新分类: {category_name}'))
                
                # 提取年代
                era = '未知'
                content = item.get('content', {})
                if isinstance(content, dict):
                    freetext = content.get('freetext', {})
                    if isinstance(freetext, dict):
                        date_info = freetext.get('date', [])
                        if date_info and isinstance(date_info, list) and len(date_info) > 0:
                            date_item = date_info[0]
                            if isinstance(date_item, dict) and 'content' in date_item:
                                era = date_item['content'][:100]
                
                # 颜色
                colors = ['红色', '蓝色', '黄色', '绿色', '紫色', '黑色', '白色', '棕色', '灰色']
                color = colors[i % len(colors)]
                
                # 材质
                material = ''
                if isinstance(content, dict):
                    freetext = content.get('freetext', {})
                    if isinstance(freetext, dict):
                        physical_desc = freetext.get('physicalDescription', [])
                        if physical_desc and isinstance(physical_desc, list) and len(physical_desc) > 0:
                            desc_item = physical_desc[0]
                            if isinstance(desc_item, dict) and 'content' in desc_item:
                                material = desc_item['content'][:200]
                
                # 尺寸
                dimensions = ''
                if isinstance(content, dict):
                    freetext = content.get('freetext', {})
                    if isinstance(freetext, dict):
                        # 尝试从各种字段获取尺寸
                        for key in ['dimensions', 'measurements', 'size']:
                            if key in freetext:
                                dim_item = freetext[key]
                                if isinstance(dim_item, list) and len(dim_item) > 0:
                                    dim_data = dim_item[0]
                                    if isinstance(dim_data, dict) and 'content' in dim_data:
                                        dimensions = dim_data['content'][:200]
                                        break
                
                # 收藏编号
                collection_number = item.get('id', f'Smithsonian-{i}')
                
                # 检查是否已存在
                if collection_number in existing_numbers:
                    # 更新现有记录
                    existing = Artifact.objects.filter(collection_number=collection_number).first()
                    if existing:
                        existing.name = title[:200]
                        existing.description = description[:5000]
                        existing.category = category
                        existing.era = era[:100]
                        existing.color = color[:50]
                        existing.material = material[:100]
                        existing.dimensions = dimensions[:200]
                        existing.exhibition = exhibition
                        existing.save()
                        updated += 1
                        
                        if (i + 1) % 100 == 0:
                            self.stdout.write(self.style.SUCCESS(f'第{i+1}/{total}行: 更新文物 {title[:50]}...'))
                        continue
                else:
                    existing_numbers.add(collection_number)
                
                # 创建新文物
                artifact_slug = slugify(title)
                if not artifact_slug or artifact_slug.strip() == '':
                    artifact_slug = f'smithsonian-{i}'
                else:
                    artifact_slug = f'{artifact_slug}-{i}'
                
                artifact = Artifact(
                    name=title[:200],
                    slug=artifact_slug,
                    description=description[:5000],
                    category=category,
                    era=era[:100],
                    color=color[:50],
                    material=material[:100],
                    dimensions=dimensions[:200],
                    exhibition=exhibition,
                    collection_number=collection_number[:100],
                    is_active=True
                )
                artifact.save()
                imported += 1
                
                if (i + 1) % 100 == 0:
                    self.stdout.write(self.style.SUCCESS(f'第{i+1}/{total}行: 导入文物 {title[:50]}...'))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'第{i+1}行: 导入失败 - {str(e)}'))
                errors += 1
        
        # 输出统计
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('导入完成!'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'总记录数: {total}')
        self.stdout.write(f'新导入: {imported}')
        self.stdout.write(f'更新: {updated}')
        self.stdout.write(f'跳过: {skipped}')
        self.stdout.write(f'错误: {errors}')
        
        if total > 0:
            success_rate = ((imported + updated) / total * 100)
            self.stdout.write(self.style.SUCCESS(f'成功率: {success_rate:.1f}%'))
        
        # 显示分类统计
        self.stdout.write(self.style.WARNING('\n分类统计:'))
        categories = Category.objects.all().order_by('-id')[:20]
        for cat in categories:
            count = Artifact.objects.filter(category=cat).count()
            if count > 0:
                self.stdout.write(f'  {cat.name}: {count} 件')
        
        return imported, updated, errors