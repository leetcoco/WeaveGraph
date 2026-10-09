import json
import time
import sys
import os
from pathlib import Path
from urllib.parse import unquote

import requests
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from artifacts.models import Artifact, Category, Exhibition

# Add root to sys.path to import extract_colors
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
try:
    from extract_colors import extract_palette_from_url
except ImportError:
    print("Warning: extract_colors module not found. Color extraction will be skipped.")
    def extract_palette_from_url(url, top_n=5):
        return []


class Command(BaseCommand):
    help = '从 Cleveland Museum of Art (CMA) Open Access API 抓取画作信息'

    def add_arguments(self, parser):
        parser.add_argument('-q', '--query', type=str, default='Chinese', help='搜索关键词')
        parser.add_argument('-d', '--department', type=str, default='Chinese Art', help='部门名称（如 Chinese Art）')
        parser.add_argument('-t', '--type', type=str, default='Painting', help='作品类型（如 Painting）')
        parser.add_argument('-n', '--max-items', type=int, default=100, help='最多抓取条数')
        parser.add_argument('-s', '--skip', type=int, default=0, help='跳过前 N 条记录')
        parser.add_argument('--sleep', type=float, default=0.2, help='请求间隔秒数')
        parser.add_argument('--timeout', type=float, default=30, help='请求超时秒数')
        parser.add_argument('-o', '--out', type=str, default='cma_artworks.json', help='输出 JSON 文件路径')
        parser.add_argument('-P', '--no-proxy', action='store_true', help='忽略环境变量代理')
        parser.add_argument('-I', '--import-db', action='store_true', help='将结果导入 artifacts_artifact')
        parser.add_argument('-e', '--exhibition', type=str, default='CMA 特展', help='导入时使用的展览标题')
        parser.add_argument('--extract-colors', action='store_true', help='同时提取图片颜色（会减慢速度）')

    def handle(self, *args, **options):
        query = options['query']
        department = options['department']
        artwork_type = options['type']
        max_items = options['max_items']
        skip = options['skip']
        sleep_s = options['sleep']
        timeout_s = options['timeout']
        out_path = Path(options['out'])
        no_proxy = options['no_proxy']
        import_db = options['import_db']
        exhibition_title = options['exhibition']
        extract_colors = options['extract_colors']

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'ColorNet-Crawler/1.0',
            'Accept': 'application/json',
        })
        if no_proxy:
            session.trust_env = False

        base_url = 'https://openaccess-api.clevelandart.org/api/artworks/'
        
        # CMA API supports limit/skip
        # We can fetch in batches. Max limit per request is usually 100.
        batch_size = 100
        fetched_count = 0
        all_data = []
        
        exhibition = None
        if import_db:
            exhibition, created = Exhibition.objects.get_or_create(
                slug=slugify(exhibition_title) if exhibition_title.strip() else 'cma-collection',
                defaults={
                    'title': exhibition_title,
                    'description': '来自 Cleveland Museum of Art 的文物收藏',
                    'start_date': '1900-01-01',
                    'end_date': '2099-12-31',
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'创建展览: {exhibition.title}'))

        self.stdout.write(f'开始抓取 CMA: query="{query}", department="{department}", type="{artwork_type}"')

        while fetched_count < max_items:
            current_limit = min(batch_size, max_items - fetched_count)
            params = {
                'q': query,
                'department': department,
                'type': artwork_type,
                'has_image': 1,
                'skip': skip + fetched_count,
                'limit': current_limit,
                'indent': 1,
            }
            
            try:
                resp = session.get(base_url, params=params, timeout=timeout_s)
                resp.raise_for_status()
                data = resp.json()
                
                # CMA returns { 'info': ..., 'data': [...] }
                results = data.get('data', [])
                if not results:
                    self.stdout.write(self.style.WARNING('未获取到更多数据，结束抓取'))
                    break
                
                for item in results:
                    # Extract fields
                    # item structure: https://openaccess-api.clevelandart.org/
                    
                    obj_id = item.get('id')
                    title = item.get('title', 'Untitled')
                    creation_date = item.get('creation_date', '') # Often contains dynasty info
                    culture = item.get('culture', [])
                    if isinstance(culture, list):
                        culture = ', '.join(culture)
                    
                    images = item.get('images', {})
                    image_url = ''
                    if images:
                        web_img = images.get('web', {})
                        if web_img:
                            image_url = web_img.get('url', '')
                        else:
                            print_img = images.get('print', {})
                            if print_img:
                                image_url = print_img.get('url', '')
                    
                    if not image_url:
                        continue # Skip if no image URL found (even if has_image=1 sometimes url is hidden)

                    record = {
                        'source': 'CMA',
                        'object_id': obj_id,
                        'title': title,
                        'classification': artwork_type,
                        'department': department,
                        'period': creation_date, # Use creation_date as period/dynasty
                        'culture': culture,
                        'image_url': image_url,
                        'tombstone': item.get('tombstone', ''),
                        'description': item.get('description', ''),
                    }
                    all_data.append(record)
                    
                    if import_db and exhibition:
                        # Ensure category exists
                        cat_name = item.get('type', 'Painting')
                        category, _ = Category.objects.get_or_create(name=cat_name)

                        # Generate unique slug
                        slug_candidate = slugify(title)[:180]
                        if not slug_candidate:
                            slug_candidate = f"artifact-{obj_id}"
                        unique_slug = f"{slug_candidate}-{obj_id}"

                        # Handle slug collision
                        import random
                        import string
                        from django.db.utils import IntegrityError

                        # Save to DB
                        defaults = {
                            'name': title[:200],
                            'slug': unique_slug,
                            'description': item.get('description', '') or item.get('tombstone', '') or '',
                            'external_image': image_url,
                            'is_active': True,
                            'category': category,
                            'era': creation_date[:100] if creation_date else '',
                            'material': item.get('technique', '')[:100], # CMA has technique
                        }
                        
                        # Add extra info to description if not present
                        desc_extras = []
                        if creation_date:
                            desc_extras.append(f"时期/朝代: {creation_date}")
                        if culture:
                            desc_extras.append(f"文化: {culture}")
                        
                        if desc_extras:
                            defaults['description'] = '\n'.join(desc_extras) + '\n\n' + defaults['description']
                            
                        # Extract colors if requested
                        if extract_colors and image_url:
                            try:
                                palette = extract_palette_from_url(image_url)
                                if palette:
                                    defaults['color_palette'] = json.dumps(palette, ensure_ascii=False)
                            except Exception as e:
                                self.stdout.write(self.style.WARNING(f'  [!] 颜色提取失败: {e}'))

                        # Robust save loop
                        saved = False
                        retry_count = 0
                        while not saved and retry_count < 10:
                            try:
                                art, created_art = Artifact.objects.update_or_create(
                                    collection_number=f'CMA-{obj_id}',
                                    exhibition=exhibition,
                                    defaults=defaults
                                )
                                if created_art:
                                    self.stdout.write(f'  [+] 入库: {title} ({obj_id})')
                                else:
                                    self.stdout.write(f'  [.] 更新: {title} ({obj_id})')
                                saved = True
                            except IntegrityError as e:
                                if 'slug' in str(e):
                                    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
                                    defaults['slug'] = f"{slug_candidate}-{obj_id}-{suffix}"
                                    retry_count += 1
                                else:
                                    raise e
                        
                        if not saved:
                             self.stdout.write(self.style.ERROR(f'  [!] 保存失败 (Slug 冲突): {title}'))

                fetched_count += len(results)
                self.stdout.write(f'已抓取 {fetched_count}/{max_items} 条...')
                
                if len(results) < current_limit:
                    break
                    
                time.sleep(sleep_s)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'请求失败: {e}'))
                break

        # Save to file
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        self.stdout.write(self.style.SUCCESS(f'抓取完成，共 {len(all_data)} 条，已保存至 {out_path}'))
