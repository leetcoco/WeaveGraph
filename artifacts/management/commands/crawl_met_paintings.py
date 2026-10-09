import json
import time
from pathlib import Path
from urllib.parse import unquote

import requests
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from artifacts.models import Artifact, Category, Exhibition


class Command(BaseCommand):
    help = '从 Met Museum Open Access API 抓取画作信息（含朝代/时期/风格等），可选入库'

    def add_arguments(self, parser):
        parser.add_argument('-q', '--query', type=str, default='chinese-painting', help='搜索关键词')
        parser.add_argument('-d', '--department-id', type=int, default=6, help='部门ID（默认 6=Asian Art）')
        parser.add_argument('-n', '--max-items', type=int, default=200, help='最多抓取条数')
        parser.add_argument('-t', '--start', type=int, default=0, help='从第 N 条 objectID 开始抓取')
        parser.add_argument('-f', '--flush-every', type=int, default=0, help='每 N 条写一次输出文件')
        parser.add_argument('-s', '--sleep', type=float, default=0.15, help='请求间隔秒数')
        parser.add_argument('--timeout', type=float, default=30, help='请求超时秒数')
        parser.add_argument('--retries', type=int, default=2, help='失败重试次数')
        parser.add_argument('--retry-sleep', type=float, default=0.5, help='重试间隔秒数')
        parser.add_argument('--public-domain', action='store_true', help='仅检索公开领域（更容易拿到图片 URL）')
        parser.add_argument('-o', '--out', type=str, default='met_paintings_meta.json', help='输出 JSON 文件路径')
        parser.add_argument('-P', '--no-proxy', action='store_true', help='忽略环境变量代理（避免本地无代理时报错）')
        parser.add_argument('-p', '--only-painting', action='store_true', help='仅保留分类/类型为绘画的对象')
        parser.add_argument('-c', '--culture', type=str, default='', help='仅保留 culture 包含该字符串（如 China）')
        parser.add_argument('-k', '--classification', type=str, default='', help='仅保留 classification 包含该字符串（如 Paintings）')
        parser.add_argument('-r', '--period', type=str, default='', help='仅保留 period 包含该字符串（如 Tang）')
        parser.add_argument('-I', '--import-db', action='store_true', help='将结果导入 artifacts_artifact（使用 external_image）')
        parser.add_argument('-e', '--exhibition', type=str, default='Met 特展', help='导入时使用的展览标题')
        parser.add_argument('--dry-run', action='store_true', help='不发起网络请求，仅校验参数与写出空结果')

    def handle(self, *args, **options):
        query = unquote((options.get('query') or '').strip())
        department_id = options['department_id']
        max_items = max(0, int(options['max_items']))
        start_index = max(0, int(options.get('start') or 0))
        flush_every = max(0, int(options.get('flush_every') or 0))
        sleep_s = max(0.0, float(options['sleep']))
        timeout_s = max(0.1, float(options.get('timeout') or 30))
        retries = max(0, int(options.get('retries') or 0))
        retry_sleep_s = max(0.0, float(options.get('retry_sleep') or 0))
        out_path = Path(options['out'])
        no_proxy = bool(options['no_proxy'])
        only_painting = bool(options['only_painting'])
        public_domain_only = bool(options.get('public_domain'))
        culture_filter = (options.get('culture') or '').strip()
        classification_filter = (options.get('classification') or '').strip()
        period_filter = (options.get('period') or '').strip()
        import_db = bool(options['import_db'])
        exhibition_title = options['exhibition']
        dry_run = bool(options['dry_run'])

        if dry_run:
            out_path.write_text('[]', encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(f'已写出空结果: {out_path}'))
            return

        session = requests.Session()
        session.headers.update(
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
                'Accept': 'application/json',
            }
        )
        if no_proxy:
            session.trust_env = False

        search_url = 'https://collectionapi.metmuseum.org/public/collection/v1/search'
        object_url = 'https://collectionapi.metmuseum.org/public/collection/v1/objects/'

        params = {'q': query, 'hasImages': 'true'}
        if department_id:
            params['departmentId'] = str(department_id)
        if public_domain_only:
            params['isPublicDomain'] = 'true'

        self.stdout.write(f'搜索 Met: query="{query}", departmentId={department_id}')
        def get_json(url, params_value=None):
            last_err = None
            for attempt in range(retries + 1):
                try:
                    resp = session.get(url, params=params_value, timeout=timeout_s)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    last_err = e
                    if attempt < retries and retry_sleep_s:
                        time.sleep(retry_sleep_s)
            raise last_err

        search_data = get_json(search_url, params)

        object_ids = search_data.get('objectIDs') or []
        total = int(search_data.get('total') or 0)
        self.stdout.write(self.style.WARNING(f'搜索命中: total={total}, objectIDs={len(object_ids)}'))

        if start_index:
            object_ids = object_ids[start_index:]
        if max_items:
            object_ids = object_ids[:max_items]
        results = []

        imported = 0
        updated = 0
        skipped = 0
        errors = 0

        exhibition = None
        if import_db:
            ex_slug = slugify(exhibition_title) if exhibition_title and exhibition_title.strip() else 'met'
            exhibition, _ = Exhibition.objects.get_or_create(
                slug=ex_slug,
                defaults={
                    'title': exhibition_title if exhibition_title and exhibition_title.strip() else 'Met',
                    'description': '来自 Met Museum Open Access API 的画作与文物数据',
                    'start_date': '1900-01-01',
                    'end_date': '2099-12-31',
                    'is_active': True,
                },
            )

        existing_numbers = set()
        if import_db:
            existing_numbers = set(Artifact.objects.values_list('collection_number', flat=True))

        interrupted = False
        try:
            for idx, oid in enumerate(object_ids, 1):
                try:
                    obj = get_json(object_url + str(oid))

                    title = (obj.get('title') or '').strip() or f'Untitled {oid}'
                    primary_image = (obj.get('primaryImage') or '').strip()
                    primary_image_small = (obj.get('primaryImageSmall') or '').strip()
                    additional_images = obj.get('additionalImages') or []
                    additional_image = ''
                    if isinstance(additional_images, list) and additional_images:
                        first_additional = additional_images[0]
                        if isinstance(first_additional, str):
                            additional_image = first_additional.strip()
                    if not primary_image and not primary_image_small and not additional_image:
                        skipped += 1
                        continue

                    classification = (obj.get('classification') or '').strip()
                    object_name = (obj.get('objectName') or '').strip()
                    if only_painting:
                        hay = f'{classification} {object_name}'.lower()
                        if 'paint' not in hay and 'painting' not in hay and 'paintings' not in hay:
                            skipped += 1
                            continue
                    if classification_filter and classification_filter.lower() not in classification.lower():
                        skipped += 1
                        continue

                    artist = (obj.get('artistDisplayName') or '').strip()
                    artist_bio = (obj.get('artistDisplayBio') or '').strip()
                    object_date = (obj.get('objectDate') or '').strip()
                    dynasty = (obj.get('dynasty') or '').strip()
                    period = (obj.get('period') or '').strip()
                    style = (obj.get('style') or '').strip()
                    culture = (obj.get('culture') or '').strip()
                    if culture_filter and culture_filter.lower() not in culture.lower():
                        skipped += 1
                        continue
                    if period_filter and period_filter.lower() not in period.lower():
                        skipped += 1
                        continue
                    medium = (obj.get('medium') or '').strip()
                    dimensions = (obj.get('dimensions') or '').strip()
                    department = (obj.get('department') or '').strip()
                    credit_line = (obj.get('creditLine') or '').strip()
                    repository = (obj.get('repository') or '').strip()
                    object_url_value = (obj.get('objectURL') or '').strip()

                    tags = obj.get('tags') or []
                    tag_names = []
                    if isinstance(tags, list):
                        for t in tags:
                            if isinstance(t, dict) and t.get('term'):
                                tag_names.append(str(t['term']))

                    era_value = dynasty or period or object_date or '未知'
                    image_url = primary_image or primary_image_small or additional_image

                    description_parts = []
                    if artist:
                        description_parts.append(f'艺术家: {artist}')
                    if artist_bio:
                        description_parts.append(f'艺术家信息: {artist_bio}')
                    if object_date:
                        description_parts.append(f'年代: {object_date}')
                    if dynasty:
                        description_parts.append(f'朝代: {dynasty}')
                    if period:
                        description_parts.append(f'时期: {period}')
                    if style:
                        description_parts.append(f'风格: {style}')
                    if culture:
                        description_parts.append(f'文化: {culture}')
                    if medium:
                        description_parts.append(f'材质: {medium}')
                    if classification:
                        description_parts.append(f'分类: {classification}')
                    if tag_names:
                        description_parts.append('主题: ' + ', '.join(tag_names[:20]))
                    if repository:
                        description_parts.append(f'馆藏: {repository}')
                    if credit_line:
                        description_parts.append(f'来源: {credit_line}')
                    if object_url_value:
                        description_parts.append(f'链接: {object_url_value}')
                    description = ' | '.join(description_parts) if description_parts else '暂无描述'

                    record = {
                        'source': 'MetMuseum',
                        'object_id': int(obj.get('objectID') or oid),
                        'title': title,
                        'artist': artist,
                        'artist_bio': artist_bio,
                        'object_date': object_date,
                        'dynasty': dynasty,
                        'period': period,
                        'style': style,
                        'culture': culture,
                        'medium': medium,
                        'dimensions': dimensions,
                        'classification': classification,
                        'object_name': object_name,
                        'department': department,
                        'tags': tag_names,
                        'repository': repository,
                        'credit_line': credit_line,
                        'object_url': object_url_value,
                        'image_url': image_url,
                        'era': era_value,
                        'description': description,
                    }
                    results.append(record)

                    if import_db:
                        collection_number = f'MET-{record["object_id"]}'
                        # Use a unified category for all Met artifacts to avoid fragmentation
                        category_name = '大都会艺术博物馆'
                        category_slug = 'met-museum-general'
                        category, _ = Category.objects.get_or_create(
                            slug=category_slug,
                            defaults={'name': category_name},
                        )

                        if collection_number in existing_numbers:
                            existing = Artifact.objects.filter(collection_number=collection_number).first()
                            if existing:
                                existing.name = title[:200]
                                existing.description = description[:5000]
                                existing.category = category
                                existing.era = era_value[:100]
                                existing.color = '多色'
                                existing.material = medium[:100]
                                existing.dimensions = dimensions[:200]
                                existing.external_image = image_url[:500]
                                existing.exhibition = exhibition
                                existing.save()
                                updated += 1
                        else:
                            existing_numbers.add(collection_number)
                            slug_base = slugify(f'{title}-{collection_number}') or f'met-{record["object_id"]}'
                            Artifact.objects.create(
                                name=title[:200],
                                slug=slug_base[:200],
                                description=description[:5000],
                                category=category,
                                era=era_value[:100],
                                color='多色',
                                material=medium[:100],
                                dimensions=dimensions[:200],
                                collection_number=collection_number[:100],
                                external_image=image_url[:500],
                                exhibition=exhibition,
                                is_active=True,
                            )
                            imported += 1

                    if idx % 20 == 0:
                        self.stdout.write(f'进度: {idx}/{len(object_ids)} (保留 {len(results)} 条)')
                    if flush_every and idx % flush_every == 0:
                        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

                except Exception as e:
                    errors += 1
                    if idx <= 5 or idx % 50 == 0:
                        self.stdout.write(self.style.WARNING(f'第{idx}条抓取失败: {e}'))
                finally:
                    if sleep_s:
                        time.sleep(sleep_s)
        except KeyboardInterrupt:
            interrupted = True

        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'已保存: {out_path} (共 {len(results)} 条)'))
        if interrupted:
            self.stdout.write(self.style.WARNING('抓取被中断，已保存当前进度'))

        if import_db:
            self.stdout.write(self.style.SUCCESS('入库统计:'))
            self.stdout.write(f'  新增: {imported}')
            self.stdout.write(f'  更新: {updated}')
            self.stdout.write(f'  跳过: {skipped}')
            self.stdout.write(f'  错误: {errors}')
