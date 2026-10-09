from django.core.management.base import BaseCommand
import csv
import os
from artifacts.models import Artifact, Category, Exhibition
from django.utils.text import slugify

class Command(BaseCommand):
    help = '从 MoMA Artists.csv 文件直接导入艺术家数据'
    
    def add_arguments(self, parser):
        parser.add_argument('--csv-file', type=str, default='Artists.csv', help='CSV文件路径 (默认: Artists.csv)')
        parser.add_argument('--limit', type=int, default=None, help='限制导入的记录数 (用于测试)')
        parser.add_argument('--exhibition', type=str, default='MoMA 艺术家特展', help='展览标题')
    
    def handle(self, *args, **options):
        csv_file = options['csv_file']
        limit = options['limit']
        exhibition_title = options['exhibition']
        
        if not os.path.exists(csv_file):
            self.stdout.write(self.style.ERROR(f'文件不存在: {csv_file}'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'开始导入 MoMA 艺术家数据从 {csv_file}'))
        
        # 读取CSV文件
        rows = []
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                rows.append(row)
                if limit and i >= limit - 1:
                    break
        
        self.stdout.write(self.style.WARNING(f'读取到 {len(rows)} 条记录'))
        
        # 创建展览
        exhibition, created = Exhibition.objects.get_or_create(
            slug=slugify(exhibition_title) if exhibition_title.strip() else 'moma-artists',
            defaults={
                'title': exhibition_title if exhibition_title.strip() else 'MoMA Artists',
                'description': '来自 MoMA 的艺术家收藏',
                'start_date': '1900-01-01',
                'end_date': '2099-12-31',
                'is_active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'创建新展览: {exhibition.title}'))
        
        total = len(rows)
        imported = 0
        updated = 0
        skipped = 0
        errors = 0
        
        # 预获取已存在的收藏编号
        existing_numbers = set(Artifact.objects.values_list('collection_number', flat=True))
        
        for i, row in enumerate(rows):
            try:
                # 提取字段
                display_name = row.get('DisplayName', f'艺术家 {row.get("ConstituentID", i)}')
                nationality = row.get('Nationality', '')
                gender = row.get('Gender', '')
                artist_bio = row.get('ArtistBio', '')
                begin_date_str = row.get('BeginDate', '')
                end_date_str = row.get('EndDate', '')
                
                if not display_name or display_name.strip() == '':
                    self.stdout.write(self.style.WARNING(f'第{i+1}行: 缺少艺术家姓名，跳过'))
                    skipped += 1
                    continue
                
                # 转换日期
                try:
                    begin_date = int(begin_date_str) if begin_date_str.strip() else 0
                except:
                    begin_date = 0
                    
                try:
                    end_date = int(end_date_str) if end_date_str.strip() else 0
                except:
                    end_date = 0
                
                # 构建描述
                description_parts = []
                if artist_bio and artist_bio.strip():
                    description_parts.append(f"生平: {artist_bio[:500]}")
                if nationality and nationality.strip():
                    description_parts.append(f"国籍: {nationality}")
                if gender and gender.strip():
                    description_parts.append(f"性别: {gender}")
                
                if begin_date != 0:
                    era_info = f"{begin_date}"
                    if end_date != 0:
                        era_info += f"-{end_date}"
                    else:
                        era_info += "-至今"
                    description_parts.append(f"年代: {era_info}")
                
                description = ' | '.join(description_parts) if description_parts else '暂无描述'
                
                # 确定分类
                category_name = '国际艺术'
                if nationality:
                    nationality_lower = nationality.lower()
                    if 'american' in nationality_lower:
                        category_name = '美国艺术'
                    elif 'french' in nationality_lower:
                        category_name = '法国艺术'
                    elif 'german' in nationality_lower:
                        category_name = '德国艺术'
                    elif 'british' in nationality_lower:
                        category_name = '英国艺术'
                    elif 'japanese' in nationality_lower:
                        category_name = '日本艺术'
                    elif 'chinese' in nationality_lower:
                        category_name = '中国艺术'
                    elif 'spanish' in nationality_lower:
                        category_name = '西班牙艺术'
                    elif 'italian' in nationality_lower:
                        category_name = '意大利艺术'
                    elif 'dutch' in nationality_lower:
                        category_name = '荷兰艺术'
                    elif 'russian' in nationality_lower:
                        category_name = '俄罗斯艺术'
                    elif 'danish' in nationality_lower:
                        category_name = '丹麦艺术'
                
                # 确保分类名称有效
                if not category_name or category_name.strip() == '':
                    category_name = '国际艺术'
                
                # 获取或创建分类
                category_slug = slugify(category_name)
                if not category_slug or category_slug.strip() == '':
                    category_slug = 'international-art'
                
                category, created = Category.objects.get_or_create(
                    slug=category_slug,
                    defaults={'name': category_name}
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'创建新分类: {category_name}'))
                
                # 确定年代分类
                era = '未知'
                if begin_date != 0:
                    if begin_date < 1900:
                        era = '19世纪及之前'
                    elif begin_date < 1950:
                        era = '20世纪前半期'
                    else:
                        era = '现代当代'
                
                # 颜色
                colors = ['红色', '蓝色', '黄色', '绿色', '紫色', '黑色', '白色', '棕色', '灰色']
                color = colors[i % len(colors)]
                
                # 收藏编号
                constituent_id = row.get('ConstituentID', '')
                collection_number = f'MoMA-{constituent_id if constituent_id else i}'
                
                # 检查是否已存在
                if collection_number in existing_numbers:
                    # 更新现有记录
                    existing = Artifact.objects.filter(collection_number=collection_number).first()
                    if existing:
                        existing.name = display_name[:200]
                        existing.description = description[:5000]
                        existing.category = category
                        existing.era = era[:100]
                        existing.color = color[:50]
                        existing.material = '艺术作品'
                        existing.exhibition = exhibition
                        existing.save()
                        updated += 1
                        
                        if (i + 1) % 100 == 0:
                            self.stdout.write(self.style.SUCCESS(f'第{i+1}/{total}行: 更新艺术家 {display_name[:50]}...'))
                        continue
                else:
                    existing_numbers.add(collection_number)
                
                # 创建新文物
                artifact_slug = slugify(display_name)
                if not artifact_slug or artifact_slug.strip() == '':
                    artifact_slug = f'artist-{i}'
                else:
                    artifact_slug = f'{artifact_slug}-{i}'
                
                artifact = Artifact(
                    name=display_name[:200],
                    slug=artifact_slug,
                    description=description[:5000],
                    category=category,
                    era=era[:100],
                    color=color[:50],
                    material='艺术作品',
                    dimensions='',
                    exhibition=exhibition,
                    collection_number=collection_number[:100],
                    is_active=True
                )
                artifact.save()
                imported += 1
                
                if (i + 1) % 100 == 0:
                    self.stdout.write(self.style.SUCCESS(f'第{i+1}/{total}行: 导入艺术家 {display_name[:50]}...'))
                    
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