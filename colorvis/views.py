from django.shortcuts import render
from artifacts.models import Artifact, Category, Exhibition
from collections import defaultdict, Counter
from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from io import BytesIO
import random
import json
import os
import ast
import colorsys
import math
import time
import re

_COLORVIS_CACHE = {}
_COLORVIS_CACHE_TTL_SEC = 600

def colornetvis(request):
    """
    ColorNetVis: 交互式颜色网络分析可视化
    展示颜色之间的关联网络
    """
    def get_dynasty_label(v):
        value = (v or "").strip()
        if not value:
            return "未知"
        lower = value.lower()
        if "qing" in lower:
            return "清代"
        if "ming" in lower:
            return "明代"
        if "yuan" in lower:
            return "元代"
        if "northern song" in lower:
            return "北宋"
        if "southern song" in lower:
            return "南宋"
        if "song" in lower:
            return "宋代"
        if "tang" in lower:
            return "唐代"
        if "han" in lower:
            return "汉代"
        if "jin dynasty" in lower:
            return "金代"
        if "liao" in lower:
            return "辽"
        if "sui" in lower:
            return "隋"
        chinese_pairs = [
            ("南宋", "南宋"),
            ("北宋", "北宋"),
            ("五代", "五代"),
            ("秦", "秦"),
            ("汉", "汉代"),
            ("唐", "唐代"),
            ("宋", "宋代"),
            ("元", "元代"),
            ("明", "明代"),
            ("清", "清代"),
            ("晋", "晋"),
            ("隋", "隋"),
            ("辽", "辽"),
            ("金", "金代"),
        ]
        for key, label in chinese_pairs:
            if key in value:
                return label
        years = re.findall(r"\d{3,4}", value)
        for y in years:
            try:
                year = int(y)
            except Exception:
                continue
            if 1644 <= year <= 1911:
                return "清代"
            if 1368 <= year <= 1644:
                return "明代"
            if 1271 <= year <= 1368:
                return "元代"
            if 960 <= year <= 1279:
                return "宋代"
            if 618 <= year <= 907:
                return "唐代"
        if years:
            try:
                first = int(years[0])
                if first <= 1911:
                    return "古代"
                return "近现代"
            except Exception:
                pass
        return "未知"

    def build_dynasty_options():
        from artifacts.models import Artifact as ArtifactModel
        labels = Counter()
        for a in ArtifactModel.objects.filter(is_active=True).only("id", "era").iterator():
            label = get_dynasty_label(a.era)
            if label:
                labels[label] += 1
        order = {
            "先秦": 1,
            "秦": 2,
            "汉代": 3,
            "魏晋": 4,
            "南北朝": 5,
            "隋": 6,
            "唐代": 7,
            "五代": 8,
            "北宋": 9,
            "南宋": 10,
            "宋代": 11,
            "辽": 12,
            "金代": 13,
            "元代": 14,
            "明代": 15,
            "清代": 16,
            "近现代": 17,
        }
        items = [label for label, cnt in labels.items() if cnt > 0]
        items = [x for x in items if x != "未知"]
        items.sort(key=lambda x: (order.get(x, 999), x))
        return items

    def apply_era_filter(qs, selected_era):
        token = (selected_era or "").strip()
        if not token:
            return qs, None
        mapping = {
            "清代": ["qing", "清"],
            "明代": ["ming", "明"],
            "元代": ["yuan", "元"],
            "北宋": ["northern song", "北宋"],
            "南宋": ["southern song", "南宋"],
            "宋代": ["song", "宋"],
            "唐代": ["tang", "唐"],
            "汉代": ["han", "汉"],
            "金代": ["jin dynasty", "金"],
        }
        keys = mapping.get(token)
        if not keys:
            new_qs = qs.filter(era__icontains=token)
        else:
            cond = Q()
            for k in keys:
                cond |= Q(era__icontains=k)
            new_qs = qs.filter(cond)
        if new_qs.exists():
            return new_qs, token
        return qs, None

    # 获取筛选参数（支持多选）
    category_ids = request.GET.getlist('category')
    era = request.GET.get('era')
    exhibition_id = request.GET.get('exhibition')
    exact_mode = str(request.GET.get('exact') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    paper_param = request.GET.get('paper')
    raw_paper_mode = None if paper_param is None else str(paper_param).strip().lower()
    paper_mode = True if raw_paper_mode is None else (raw_paper_mode in {'1', 'true', 'yes', 'on'})
    fill_missing_palette = str(request.GET.get('fill_missing') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    try:
        de_threshold = float(str(request.GET.get('de') or '7').strip())
    except Exception:
        de_threshold = 7.0
    if not math.isfinite(de_threshold):
        de_threshold = 7.0
    de_threshold = max(0.0, min(30.0, de_threshold))
    try:
        min_pct = float(str(request.GET.get('min_pct') or '3').strip())
    except Exception:
        min_pct = 3.0
    if not math.isfinite(min_pct):
        min_pct = 3.0
    min_pct = max(0.0, min(50.0, min_pct))
    
    def parse_palette(value):
        if not value:
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            try:
                parsed = json.loads(s)
            except Exception:
                try:
                    parsed = ast.literal_eval(s)
                except Exception:
                    return None
            return parsed if isinstance(parsed, list) else None
        return None

    def normalize_hex(value):
        if not value or not isinstance(value, str):
            return None
        s = value.strip()
        if not s:
            return None
        if s.startswith("#"):
            s = s[1:]
        if len(s) != 6:
            return None
        try:
            int(s, 16)
        except Exception:
            return None
        return f"#{s.lower()}"

    def normalize_rgb_triplet(value):
        if not isinstance(value, (tuple, list)) or len(value) != 3:
            return None
        try:
            r, g, b = value
            rf = float(r)
            gf = float(g)
            bf = float(b)
        except Exception:
            return None
        if 0.0 <= rf <= 1.0 and 0.0 <= gf <= 1.0 and 0.0 <= bf <= 1.0:
            rf *= 255.0
            gf *= 255.0
            bf *= 255.0
        r = int(round(rf))
        g = int(round(gf))
        b = int(round(bf))
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        return f"#{r:02x}{g:02x}{b:02x}"

    def normalize_hsv_triplet(value):
        if not isinstance(value, (tuple, list)) or len(value) != 3:
            return None
        try:
            h, s, v = value
            h = float(h)
            s = float(s)
            v = float(v)
        except Exception:
            return None

        if 0 <= h <= 1.0 and 0 <= s <= 1.0 and 0 <= v <= 1.0:
            hh = h
            ss = s
            vv = v
        else:
            hh = (h % 360.0) / 360.0 if h != 360.0 else 0.0
            if 0 <= s <= 100 and 0 <= v <= 100:
                ss = s / 100.0
                vv = v / 100.0
            elif 0 <= s <= 255 and 0 <= v <= 255:
                ss = s / 255.0
                vv = v / 255.0
            else:
                return None

        if not (0.0 <= hh <= 1.0 and 0.0 <= ss <= 1.0 and 0.0 <= vv <= 1.0):
            return None

        r, g, b = colorsys.hsv_to_rgb(hh, ss, vv)
        return normalize_rgb_triplet((r * 255.0, g * 255.0, b * 255.0))

    def normalize_color_item(item):
        if isinstance(item, str):
            return normalize_hex(item)

        if isinstance(item, dict):
            if 'hex' in item:
                return normalize_hex(item.get('hex'))
            if 'rgb' in item:
                return normalize_hex(normalize_rgb_triplet(item.get('rgb')) or "")
            if 'hsv' in item:
                return normalize_hex(normalize_hsv_triplet(item.get('hsv')) or "")
            return None

        if isinstance(item, (tuple, list)) and len(item) == 3:
            return normalize_hex(normalize_rgb_triplet(item) or "")

        return None

    def extract_palette_from_image(image_path, top_n=5):
        img = Image.open(image_path).convert("RGB")
        img.thumbnail((100, 100))
        pixels = list(img.getdata())
        if not pixels:
            return []
        quantized = [(r // 64 * 64, g // 64 * 64, b // 64 * 64) for r, g, b in pixels]
        counts = Counter(quantized)
        top_items = counts.most_common(max(1, int(top_n)))
        result = []
        for (r, g, b), _ in top_items:
            hx = f"#{r:02x}{g:02x}{b:02x}"
            normalized = normalize_hex(hx)
            if normalized and normalized not in result:
                result.append(normalized)
        return result

    def get_local_image_path(artifact):
        if artifact.image:
            try:
                p = artifact.image.path
                return p if p and os.path.exists(p) else None
            except Exception:
                pass
            try:
                rel = getattr(artifact.image, "name", None) or str(artifact.image)
                rel = str(rel).lstrip("/").replace("\\", "/")
                if rel:
                    p = os.path.join(settings.BASE_DIR, "static", rel.replace("/", os.sep))
                    return p if os.path.exists(p) else None
            except Exception:
                pass
        url = (artifact.external_image or "").strip()
        if not url:
            return None
        url = url.replace("\\", "/")
        if url.startswith("http"):
            return None
        rel = url.lstrip("/")
        if rel.startswith("static/"):
            return os.path.join(settings.BASE_DIR, rel)
        return None

    artifacts_base_qs = Artifact.objects.filter(is_active=True).filter(
        Q(external_image__gt="") | Q(image__gt="")
    )

    resolved_category_ids = []
    unresolved_category_tokens = []
    for raw in category_ids:
        if raw is None:
            continue
        token = str(raw).strip()
        if not token:
            continue
        try:
            resolved_category_ids.append(int(token))
            continue
        except Exception:
            unresolved_category_tokens.append(token)

    if unresolved_category_tokens:
        resolved_category_ids.extend(
            list(
                Category.objects.filter(
                    Q(name__in=unresolved_category_tokens) | Q(slug__in=unresolved_category_tokens)
                ).values_list("id", flat=True)
            )
        )

    if resolved_category_ids:
        artifacts_base_qs = artifacts_base_qs.filter(category_id__in=resolved_category_ids)
    if era:
        artifacts_base_qs, filtered_era = apply_era_filter(artifacts_base_qs, era)
        if not filtered_era:
            era = None
        else:
            era = filtered_era
    if exhibition_id:
        try:
            ex_id = int(exhibition_id)
        except Exception:
            ex_id = None
        if ex_id and Exhibition.objects.filter(id=ex_id, is_active=True).exists():
            artifacts_base_qs = artifacts_base_qs.filter(exhibition_id=ex_id)
        else:
            exhibition_id = None

    artifacts_base_qs = artifacts_base_qs.order_by("id")
    
    # 获取筛选选项
    categories = Category.objects.filter(
        Q(name__icontains='博物馆') | Q(name__startswith='WikiArt')
    ).order_by('name')
    eras = build_dynasty_options()
    exhibitions = Exhibition.objects.filter(is_active=True).all()
    
    total_artifacts = artifacts_base_qs.count()

    cache_key_payload = {
        "categories": sorted({str(x).strip() for x in category_ids if str(x).strip()}),
        "era": str(era or "").strip(),
        "exhibition": str(exhibition_id or "").strip(),
        "exact": bool(exact_mode),
        "paper": bool(paper_mode),
        "de": float(de_threshold),
        "min_pct": float(min_pct),
        "fill_missing": bool(fill_missing_palette),
    }
    cache_key = json.dumps(cache_key_payload, sort_keys=True, ensure_ascii=False)
    now_ts = time.time()
    cache_item = _COLORVIS_CACHE.get(cache_key)
    if cache_item and cache_item.get("expires_at", 0) > now_ts:
        cached_context = dict(cache_item.get("context") or {})
        cached_context.update(
            {
                "categories": categories,
                "eras": eras,
                "exhibitions": exhibitions,
                "selected_category_list": category_ids,
                "selected_era": era,
                "selected_exhibition": exhibition_id,
                "selected_exact": exact_mode,
                "selected_paper": paper_mode,
                "selected_de": de_threshold,
                "selected_min_pct": min_pct,
            }
        )
        response = render(request, 'colorvis/colornetvis.html', cached_context)
        response['Cache-Control'] = 'no-store, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    artifacts = (
        artifacts_base_qs.select_related("category", "exhibition")
        .only("id", "color_palette", "material", "era", "image", "external_image", "category_id", "exhibition_id")
        .iterator()
    )

    # 构建颜色共现矩阵
    color_cooccurrence = defaultdict(lambda: defaultdict(int))
    color_freq = Counter()

    color_attributes = defaultdict(lambda: {
        'categories': Counter(),
        'materials': Counter(),
        'eras': Counter()
    })

    computed_missing = 0
    compute_missing_limit = 200 if fill_missing_palette else 0
    palette_item_count = 0
    invalid_color_item_count = 0
    artifacts_with_valid_palette = 0

    for artifact in artifacts:
        palette = parse_palette(artifact.color_palette)
        if (not palette or not isinstance(palette, list)) and computed_missing < compute_missing_limit:
            local_path = get_local_image_path(artifact)
            if local_path and os.path.exists(local_path):
                try:
                    palette = extract_palette_from_image(local_path, top_n=5)
                    computed_missing += 1
                except Exception:
                    palette = None
        if palette and isinstance(palette, list):
            default_pct = 100.0 / len(palette) if len(palette) > 0 else 0.0
            color_list = []
            significant_colors = []
            for item in palette:
                palette_item_count += 1
                normalized = normalize_color_item(item)
                if normalized:
                    color_list.append(normalized)
                    pct = None
                    if isinstance(item, dict):
                        pct = item.get('percentage')
                        if pct is None:
                            pct = item.get('percent')
                        if pct is None:
                            pct = item.get('ratio')
                    try:
                        pct = float(pct) if pct is not None else float(default_pct)
                    except Exception:
                        pct = float(default_pct)
                    if math.isfinite(pct) and pct >= min_pct:
                        significant_colors.append(normalized)
                else:
                    invalid_color_item_count += 1
            if color_list:
                artifacts_with_valid_palette += 1
            
            # 更新颜色频率
            significant_unique = list(dict.fromkeys(significant_colors))
            for color in significant_unique:
                color_freq[color] += 1
            
            # 更新颜色对共现（无向图）
            for i in range(len(significant_unique)):
                for j in range(i + 1, len(significant_unique)):
                    c1 = significant_unique[i]
                    c2 = significant_unique[j]
                    if c1 != c2:
                        color_cooccurrence[c1][c2] += 1
                        color_cooccurrence[c2][c1] += 1

            for color in set(significant_unique):
                category_name = artifact.category.name if getattr(artifact, "category", None) else "未知"
                material_name = artifact.material if artifact.material else "未知"
                era_value = getattr(artifact, "era_display", None) or (artifact.era if artifact.era else "未知")
                color_attributes[color]['categories'][category_name] += 1
                color_attributes[color]['materials'][material_name] += 1
                color_attributes[color]['eras'][era_value] += 1
    
    def hex_to_rgb_tuple(hex_color):
        s = normalize_hex(hex_color)
        if not s:
            return None
        return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16))

    def rgb_to_lab(rgb):
        r, g, b = rgb
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))

        def to_linear(c):
            c = c / 255.0
            if c <= 0.04045:
                return c / 12.92
            return ((c + 0.055) / 1.055) ** 2.4

        rl = to_linear(r)
        gl = to_linear(g)
        bl = to_linear(b)

        x = (0.4124564 * rl + 0.3575761 * gl + 0.1804375 * bl) * 100.0
        y = (0.2126729 * rl + 0.7151522 * gl + 0.0721750 * bl) * 100.0
        z = (0.0193339 * rl + 0.1191920 * gl + 0.9503041 * bl) * 100.0

        xn, yn, zn = 95.047, 100.0, 108.883
        x /= xn
        y /= yn
        z /= zn

        delta = 6.0 / 29.0
        delta3 = delta ** 3
        inv3delta2 = 1.0 / (3.0 * (delta ** 2))

        def f(t):
            if t > delta3:
                return t ** (1.0 / 3.0)
            return t * inv3delta2 + 4.0 / 29.0

        fx = f(x)
        fy = f(y)
        fz = f(z)

        l = 116.0 * fy - 16.0
        a = 500.0 * (fx - fy)
        bb = 200.0 * (fy - fz)
        return (l, a, bb)

    def delta_e_ciede2000(lab1, lab2):
        l1, a1, b1 = lab1
        l2, a2, b2 = lab2

        c1 = math.sqrt(a1 * a1 + b1 * b1)
        c2 = math.sqrt(a2 * a2 + b2 * b2)
        c_bar = (c1 + c2) / 2.0

        c_bar7 = c_bar ** 7
        g = 0.5 * (1.0 - math.sqrt(c_bar7 / (c_bar7 + (25.0 ** 7))) if c_bar > 0 else 0.0)

        a1p = (1.0 + g) * a1
        a2p = (1.0 + g) * a2
        c1p = math.sqrt(a1p * a1p + b1 * b1)
        c2p = math.sqrt(a2p * a2p + b2 * b2)

        def hp(ap, b):
            if ap == 0 and b == 0:
                return 0.0
            h = math.degrees(math.atan2(b, ap))
            if h < 0:
                h += 360.0
            return h

        h1p = hp(a1p, b1)
        h2p = hp(a2p, b2)

        dlp = l2 - l1
        dcp = c2p - c1p

        if c1p * c2p == 0:
            dhp = 0.0
        else:
            dhp = h2p - h1p
            if dhp > 180.0:
                dhp -= 360.0
            elif dhp < -180.0:
                dhp += 360.0

        dhp_rad = math.radians(dhp / 2.0)
        dhp_sin = math.sin(dhp_rad)
        dhp_val = 2.0 * math.sqrt(c1p * c2p) * dhp_sin

        l_bar_p = (l1 + l2) / 2.0
        c_bar_p = (c1p + c2p) / 2.0

        if c1p * c2p == 0:
            h_bar_p = h1p + h2p
        else:
            hsum = h1p + h2p
            hdiff = abs(h1p - h2p)
            if hdiff > 180.0:
                if hsum < 360.0:
                    h_bar_p = (hsum + 360.0) / 2.0
                else:
                    h_bar_p = (hsum - 360.0) / 2.0
            else:
                h_bar_p = hsum / 2.0

        t = (
            1.0
            - 0.17 * math.cos(math.radians(h_bar_p - 30.0))
            + 0.24 * math.cos(math.radians(2.0 * h_bar_p))
            + 0.32 * math.cos(math.radians(3.0 * h_bar_p + 6.0))
            - 0.20 * math.cos(math.radians(4.0 * h_bar_p - 63.0))
        )

        dtheta = 30.0 * math.exp(-(((h_bar_p - 275.0) / 25.0) ** 2))
        rc = 2.0 * math.sqrt((c_bar_p ** 7) / ((c_bar_p ** 7) + (25.0 ** 7))) if c_bar_p > 0 else 0.0

        sl = 1.0 + (0.015 * ((l_bar_p - 50.0) ** 2)) / math.sqrt(20.0 + ((l_bar_p - 50.0) ** 2))
        sc = 1.0 + 0.045 * c_bar_p
        sh = 1.0 + 0.015 * c_bar_p * t
        rt = -math.sin(math.radians(2.0 * dtheta)) * rc

        dl = dlp / sl
        dc = dcp / sc
        dh = dhp_val / sh

        return math.sqrt(dl * dl + dc * dc + dh * dh + rt * dc * dh)

    def build_color_merge_mapping(rgb_tolerance=3):
        rgb_by_color = {}
        for color in color_freq.keys():
            rgb = hex_to_rgb_tuple(color)
            if rgb is not None:
                rgb_by_color[color] = rgb

        bucket_size = max(1, rgb_tolerance + 1)
        buckets = defaultdict(list)
        for color, (r, g, b) in rgb_by_color.items():
            buckets[(r // bucket_size, g // bucket_size, b // bucket_size)].append(color)

        color_to_rep = {}
        unassigned = set(rgb_by_color.keys())
        ordered = [c for c, _ in color_freq.most_common() if c in rgb_by_color]

        for rep in ordered:
            if rep not in unassigned:
                continue
            rep_rgb = rgb_by_color[rep]
            key = (rep_rgb[0] // bucket_size, rep_rgb[1] // bucket_size, rep_rgb[2] // bucket_size)

            color_to_rep[rep] = rep
            unassigned.remove(rep)

            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for cand in buckets.get((key[0] + dx, key[1] + dy, key[2] + dz), []):
                            if cand not in unassigned:
                                continue
                            cr, cg, cb = rgb_by_color[cand]
                            if max(abs(cr - rep_rgb[0]), abs(cg - rep_rgb[1]), abs(cb - rep_rgb[2])) <= rgb_tolerance:
                                color_to_rep[cand] = rep
                                unassigned.remove(cand)

        for color in color_freq.keys():
            if color not in color_to_rep:
                color_to_rep[color] = color

        return color_to_rep

    def build_color_merge_mapping_de(de_threshold_value=7.0):
        if de_threshold_value <= 0:
            return {c: c for c in color_freq.keys()}

        lab_by_color = {}
        for color in color_freq.keys():
            rgb = hex_to_rgb_tuple(color)
            if rgb is None:
                continue
            lab_by_color[color] = rgb_to_lab(rgb)

        cell = max(0.1, float(de_threshold_value))
        buckets = defaultdict(list)
        for color, (l, a, bb) in lab_by_color.items():
            buckets[(int(l // cell), int(a // cell), int(bb // cell))].append(color)

        ordered = [c for c, _ in sorted(color_freq.items(), key=lambda kv: (-kv[1], kv[0])) if c in lab_by_color]

        color_to_rep = {}
        unassigned = set(lab_by_color.keys())

        for rep in ordered:
            if rep not in unassigned:
                continue
            rep_lab = lab_by_color[rep]
            l, a, bb = rep_lab
            key = (int(l // cell), int(a // cell), int(bb // cell))

            color_to_rep[rep] = rep
            unassigned.remove(rep)

            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for cand in buckets.get((key[0] + dx, key[1] + dy, key[2] + dz), []):
                            if cand not in unassigned:
                                continue
                            if delta_e_ciede2000(rep_lab, lab_by_color[cand]) <= de_threshold_value:
                                color_to_rep[cand] = rep
                                unassigned.remove(cand)

        for color in color_freq.keys():
            if color not in color_to_rep:
                color_to_rep[color] = color

        return color_to_rep

    if paper_mode:
        color_to_rep = build_color_merge_mapping_de(de_threshold_value=0.0 if exact_mode else de_threshold)
    else:
        color_to_rep = build_color_merge_mapping(rgb_tolerance=0 if exact_mode else 7)

    merged_freq = Counter()
    merged_attributes = defaultdict(lambda: {'categories': Counter(), 'materials': Counter(), 'eras': Counter()})
    for color, count in color_freq.items():
        rep = color_to_rep.get(color, color)
        merged_freq[rep] += count
        if color in color_attributes:
            merged_attributes[rep]['categories'].update(color_attributes[color]['categories'])
            merged_attributes[rep]['materials'].update(color_attributes[color]['materials'])
            merged_attributes[rep]['eras'].update(color_attributes[color]['eras'])

    top_reps = [c for c, _ in merged_freq.most_common()]
    rep_set = set(top_reps)

    nodes = [
        {'id': c, 'color': c, 'frequency': int(merged_freq.get(c, 0)), 'group': 1}
        for c in top_reps
    ]

    merged_edges = defaultdict(int)
    for c1, neighbors in color_cooccurrence.items():
        r1 = color_to_rep.get(c1, c1)
        if r1 not in rep_set:
            continue
        for c2, weight in neighbors.items():
            if c1 >= c2:
                continue
            r2 = color_to_rep.get(c2, c2)
            if r2 not in rep_set or r1 == r2 or weight <= 0:
                continue
            a, b = (r1, r2) if r1 < r2 else (r2, r1)
            merged_edges[(a, b)] += int(weight)

    links = [
        {'source': a, 'target': b, 'value': w}
        for (a, b), w in merged_edges.items()
        if w > 0
    ]
    
    # 准备上下文数据
    network_data = {
        'nodes': nodes,
        'links': links
    }

    # 构建Sankey图数据（颜色属性分布视图）
    sankey_nodes = []
    sankey_links = []
    node_index = {}

    # 获取Top 20颜色
    top_20_colors = merged_freq.most_common(20)

    # 添加颜色节点（Layer 0）
    for color, count in top_20_colors:
        sankey_nodes.append({'name': color, 'layer': 0, 'color': color})
        node_index[f"color:{color}"] = len(sankey_nodes) - 1

    # 添加题材节点（Layer 1）
    all_categories = set()
    for color, count in top_20_colors:
        for cat in merged_attributes[color]['categories']:
            all_categories.add(cat)
    for cat in sorted(all_categories)[:15]:
        sankey_nodes.append({'name': f"题材:{cat}", 'layer': 1})
        node_index[f"category:{cat}"] = len(sankey_nodes) - 1

    # 添加设色手法节点（Layer 2）
    all_materials = set()
    for color, count in top_20_colors:
        for mat in merged_attributes[color]['materials']:
            all_materials.add(mat)
    for mat in sorted(all_materials)[:10]:
        sankey_nodes.append({'name': f"手法:{mat}", 'layer': 2})
        node_index[f"material:{mat}"] = len(sankey_nodes) - 1

    # 添加朝代节点（Layer 3）
    all_eras = set()
    for color, count in top_20_colors:
        for era in merged_attributes[color]['eras']:
            all_eras.add(era)
    for era in sorted(all_eras)[:10]:
        sankey_nodes.append({'name': f"朝代:{era}", 'layer': 3})
        node_index[f"era:{era}"] = len(sankey_nodes) - 1

    # 创建连接
    for color, count in top_20_colors:
        color_idx = node_index[f"color:{color}"]

        # 颜色 -> 题材
        for cat, cat_count in merged_attributes[color]['categories'].items():
            cat_idx = node_index.get(f"category:{cat}")
            if cat_idx is not None:
                sankey_links.append({
                    'source': color_idx,
                    'target': cat_idx,
                    'value': cat_count,
                    'color': color
                })

        # 题材 -> 手法（通过颜色关联）
        for cat, cat_count in merged_attributes[color]['categories'].items():
            cat_idx = node_index.get(f"category:{cat}")
            for mat, mat_count in merged_attributes[color]['materials'].items():
                mat_idx = node_index.get(f"material:{mat}")
                if cat_idx is not None and mat_idx is not None:
                    sankey_links.append({
                        'source': cat_idx,
                        'target': mat_idx,
                        'value': min(cat_count, mat_count),
                        'color': color
                    })

        # 手法 -> 朝代
        for mat, mat_count in merged_attributes[color]['materials'].items():
            mat_idx = node_index.get(f"material:{mat}")
            for era, era_count in merged_attributes[color]['eras'].items():
                era_idx = node_index.get(f"era:{era}")
                if mat_idx is not None and era_idx is not None:
                    sankey_links.append({
                        'source': mat_idx,
                        'target': era_idx,
                        'value': min(mat_count, era_count),
                        'color': color
                    })

    sankey_data = {
        'nodes': sankey_nodes,
        'links': sankey_links
    }

    # 计算统计信息（与当前网络图节点范围一致）
    total_colors = len(nodes)
    total_links = len(links)
    if total_colors > 0:
        node_degrees = {node['id']: 0 for node in nodes}
        for link in links:
            source_id = link['source']
            target_id = link['target']
            if source_id in node_degrees:
                node_degrees[source_id] += 1
            if target_id in node_degrees:
                node_degrees[target_id] += 1
        avg_degree = sum(node_degrees.values()) / total_colors
    else:
        avg_degree = 0
    
    context = {
        'network_data_json': json.dumps(network_data),
        'sankey_data_json': json.dumps(sankey_data),
        'total_colors': total_colors,
        'total_artifacts': artifacts_with_valid_palette,
        'total_links': total_links,
        'avg_degree': avg_degree,
        'top_colors': merged_freq.most_common(10),
        'categories': categories,
        'eras': eras,
        'exhibitions': exhibitions,
        'selected_category_list': category_ids,
        'selected_era': era,
        'selected_exhibition': exhibition_id,
        'selected_exact': exact_mode,
        'selected_paper': paper_mode,
        'selected_de': de_threshold,
        'selected_min_pct': min_pct,
        'palette_item_count': palette_item_count,
        'invalid_color_item_count': invalid_color_item_count,
        'computed_missing_palette_count': computed_missing,
    }
    
    response = render(request, 'colorvis/colornetvis.html', context)
    response['Cache-Control'] = 'no-store, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    _COLORVIS_CACHE[cache_key] = {"expires_at": now_ts + _COLORVIS_CACHE_TTL_SEC, "context": dict(context)}
    return response

def colorspace_png(request):
    space = str(request.GET.get("space") or "rgb").strip().lower()
    if space not in {"rgb", "hsv"}:
        space = "rgb"

    try:
        width = int(request.GET.get("w") or 1100)
        height = int(request.GET.get("h") or 780)
    except Exception:
        width, height = 1100, 780
    width = max(480, min(2200, width))
    height = max(360, min(1800, height))

    try:
        point_count = int(request.GET.get("n") or 18000)
    except Exception:
        point_count = 18000
    point_count = max(1500, min(60000, point_count))

    try:
        seed = int(request.GET.get("seed") or 7)
    except Exception:
        seed = 7

    rng = random.Random(seed)
    image = Image.new("RGB", (width, height), (255, 255, 255))
    overlay = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    base = ImageDraw.Draw(image, "RGB")

    center_x = width / 2.0
    center_y = height / 2.0
    base_scale = min(width, height) * 0.36
    camera = 3.2

    rotation_x = 0.7
    rotation_y = -0.6

    def rotate_point(p):
        x0, y0, z0 = p
        cy = math.cos(rotation_y)
        sy = math.sin(rotation_y)
        x1 = x0 * cy + z0 * sy
        z1 = -x0 * sy + z0 * cy

        cx = math.cos(rotation_x)
        sx = math.sin(rotation_x)
        y2 = y0 * cx - z1 * sx
        z2 = y0 * sx + z1 * cx
        return x1, y2, z2

    def project(p):
        rx, ry, rz = rotate_point(p)
        denom = camera - rz
        sx = center_x + (rx * base_scale) / denom
        sy = center_y - (ry * base_scale) / denom
        return sx, sy, rz

    corners = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 1.0),
        (1.0, 1.0, 1.0),
        (0.0, 1.0, 1.0),
    ]
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]

    projected_corners = [project(c) for c in corners]
    for a, b in edges:
        x1, y1, _ = projected_corners[a]
        x2, y2, _ = projected_corners[b]
        base.line((x1, y1, x2, y2), fill=(190, 190, 190), width=1)

    origin = project((0.0, 0.0, 0.0))
    x_max = project((1.0, 0.0, 0.0))
    y_max = project((0.0, 1.0, 0.0))
    z_max = project((0.0, 0.0, 1.0))
    base.line((origin[0], origin[1], x_max[0], x_max[1]), fill=(90, 90, 90), width=3)
    base.line((origin[0], origin[1], y_max[0], y_max[1]), fill=(90, 90, 90), width=3)
    base.line((origin[0], origin[1], z_max[0], z_max[1]), fill=(90, 90, 90), width=3)

    try:
        font = ImageFont.truetype("arial.ttf", 16)
        small_font = ImageFont.truetype("arial.ttf", 13)
    except Exception:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    axis_labels = ("R", "G", "B") if space == "rgb" else ("H", "S", "V")
    base.text((x_max[0] + 10, x_max[1] - 8), axis_labels[0], fill=(40, 40, 40), font=font)
    base.text((y_max[0] + 10, y_max[1] - 8), axis_labels[1], fill=(40, 40, 40), font=font)
    base.text((z_max[0] + 10, z_max[1] - 8), axis_labels[2], fill=(40, 40, 40), font=font)

    if space == "rgb":
        axis_meta = (0, 128, 255)
        mapping_text = "RGB: 原点(0,0,0)，X=R(0-255), Y=G(0-255), Z=B(0-255)"
    else:
        axis_meta = (0, 180, 360)
        mapping_text = "HSV: 原点(0,0,0)，X=H(0-360°), Y=S(0-100), Z=V(0-100)"

    base.text((16, 18), mapping_text, fill=(50, 50, 50), font=small_font)

    def draw_tick_labels():
        if space == "rgb":
            xm = project((0.5, 0.0, 0.0))
            ym = project((0.0, 0.5, 0.0))
            zm = project((0.0, 0.0, 0.5))
            base.text((origin[0] - 10, origin[1] + 12), "0", fill=(60, 60, 60), font=small_font)
            base.text((xm[0] - 10, xm[1] + 12), str(axis_meta[1]), fill=(60, 60, 60), font=small_font)
            base.text((x_max[0] + 4, x_max[1] + 10), str(axis_meta[2]), fill=(60, 60, 60), font=small_font)
            base.text((ym[0] - 10, ym[1] + 12), str(axis_meta[1]), fill=(60, 60, 60), font=small_font)
            base.text((y_max[0] + 4, y_max[1] + 10), str(axis_meta[2]), fill=(60, 60, 60), font=small_font)
            base.text((zm[0] - 10, zm[1] + 12), str(axis_meta[1]), fill=(60, 60, 60), font=small_font)
            base.text((z_max[0] + 4, z_max[1] + 10), str(axis_meta[2]), fill=(60, 60, 60), font=small_font)
            return

        x_mid = project((0.5, 0.0, 0.0))
        y_mid = project((0.0, 0.5, 0.0))
        z_mid = project((0.0, 0.0, 0.5))
        base.text((origin[0] - 10, origin[1] + 12), "0", fill=(60, 60, 60), font=small_font)
        base.text((x_mid[0] - 10, x_mid[1] + 12), str(axis_meta[1]), fill=(60, 60, 60), font=small_font)
        base.text((x_max[0] + 4, x_max[1] + 10), str(axis_meta[2]), fill=(60, 60, 60), font=small_font)
        base.text((y_mid[0] - 10, y_mid[1] + 12), "50", fill=(60, 60, 60), font=small_font)
        base.text((y_max[0] + 4, y_max[1] + 10), "100", fill=(60, 60, 60), font=small_font)
        base.text((z_mid[0] - 10, z_mid[1] + 12), "50", fill=(60, 60, 60), font=small_font)
        base.text((z_max[0] + 4, z_max[1] + 10), "100", fill=(60, 60, 60), font=small_font)

    draw_tick_labels()

    points = []
    if space == "rgb":
        for _ in range(point_count):
            r = rng.random()
            g = rng.random()
            b = rng.random()
            sx, sy, depth = project((r, g, b))
            points.append((depth, sx, sy, int(r * 255), int(g * 255), int(b * 255)))
    else:
        for _ in range(point_count):
            h = rng.random()
            s = rng.random()
            v = rng.random()
            rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
            sx, sy, depth = project((h, s, v))
            points.append((depth, sx, sy, int(rr * 255), int(gg * 255), int(bb * 255)))

    points.sort(key=lambda t: t[0])
    r_base = 2
    alpha = 185
    for _, sx, sy, r, g, b in points:
        x0 = int(round(sx - r_base))
        y0 = int(round(sy - r_base))
        x1 = int(round(sx + r_base))
        y1 = int(round(sy + r_base))
        if x1 < 0 or y1 < 0 or x0 >= width or y0 >= height:
            continue
        draw.ellipse((x0, y0, x1, y1), fill=(r, g, b, alpha))

    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    out.seek(0)

    resp = HttpResponse(out.getvalue(), content_type="image/png")
    resp["Content-Disposition"] = 'inline; filename="image.png"'
    resp["Cache-Control"] = "no-store, max-age=0"
    resp["Pragma"] = "no-cache"
    resp["Expires"] = "0"
    return resp
