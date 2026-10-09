import os
from pathlib import Path
import sys

import cv2
import matplotlib.pyplot as plt
import numpy as np


BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


STYLE_MASK_MODE = {
    "交领短袄（汉）.png": "tight",
    "宋褙子（男）.png": "tight",
    "常见服装素描图 (1).png": "tight",
    "常见服装素描图 (2).png": "tight",
    "常见服装素描图.png": "tight",
    "旗袍.png": "loose",
    "常见服装素描图 (3).png": "loose",
}
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from direct_mapping_v5 import (  # noqa: E402
    create_garment_mask_v5,
    extract_artifact_subject_v5,
    extract_garment_lines,
    load_image,
)
from graph_multi_paintings_test import _fill_vneck_with_silhouette  # noqa: E402


def pick_demo_painting():
    painting_dir = BASE_DIR / "static" / "paintings"
    painting_files = []
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        painting_files.extend(painting_dir.glob(f"**/{ext}"))
    painting_files = sorted(painting_files)
    if not painting_files:
        raise RuntimeError(f"No painting file found in: {painting_dir}")
    return painting_files[0]


def list_all_garments():
    garment_dir = BASE_DIR / "static" / "downloads"
    garment_files = sorted(garment_dir.glob("*.png"))
    if not garment_files:
        raise RuntimeError(f"No garment file found in: {garment_dir}")
    return garment_files


def _keep_medium_components(binary_u8, min_area):
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary_u8, connectivity=8)
    out = np.zeros_like(binary_u8)
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            out[labels == i] = 255
    return out


def _template_silhouette_mask(garment_img):
    h, w = garment_img.shape[:2]
    gray = cv2.cvtColor((np.clip(garment_img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)

    # 基于模板线条提取主体笔画
    stroke = (gray < 245).astype(np.uint8) * 255
    stroke = cv2.morphologyEx(stroke, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    stroke = cv2.dilate(stroke, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(stroke, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return np.zeros((h, w), dtype=np.uint8)

    cx = w // 2
    areas = [cv2.contourArea(c) for c in contours]
    max_area = max(areas) if areas else 0.0

    out = np.zeros((h, w), dtype=np.uint8)
    picked = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        x, y, ww, hh = cv2.boundingRect(cnt)
        center_cross = (x < int(0.78 * w)) and (x + ww > int(0.22 * w))
        tall_enough = hh > int(0.18 * h)
        near_center_x = abs((x + ww / 2.0) - cx) < 0.34 * w
        if area >= max_area * 0.05 and center_cross and tall_enough and near_center_x:
            cv2.drawContours(out, [cnt], -1, 255, -1)
            picked += 1

    if picked == 0:
        main = max(contours, key=cv2.contourArea)
        cv2.drawContours(out, [main], -1, 255, -1)

    out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=1)
    return out


def _scanline_fill_from_stroke(garment_img):
    h, w = garment_img.shape[:2]
    gray = cv2.cvtColor((np.clip(garment_img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    stroke = (gray < 245).astype(np.uint8)
    stroke = cv2.morphologyEx((stroke * 255).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    stroke = (stroke > 0).astype(np.uint8)

    filled = np.zeros((h, w), dtype=np.uint8)
    for y in range(h):
        xs = np.where(stroke[y] > 0)[0]
        if xs.size < 2:
            continue
        x0 = int(np.percentile(xs, 8))
        x1 = int(np.percentile(xs, 92))
        if x1 - x0 < int(0.10 * w):
            continue
        filled[y, x0:x1 + 1] = 255

    # 强平滑：消除行扫描产生的阶梯/锯齿
    filled = cv2.GaussianBlur(filled.astype(np.float32), (11, 11), sigmaX=2.5)
    filled = (filled > 127).astype(np.uint8) * 255
    filled = cv2.morphologyEx(filled, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=1)
    filled = cv2.morphologyEx(filled, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    return filled


def _keep_center_body_component(mask_u8):
    h, w = mask_u8.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    if n <= 1:
        return mask_u8

    cx, cy = w // 2, h // 2
    if labels[cy, cx] > 0:
        keep_id = int(labels[cy, cx])
    else:
        keep_id = 1
        best_score = -1.0
        for i in range(1, n):
            area = float(stats[i, cv2.CC_STAT_AREA])
            x = int(stats[i, cv2.CC_STAT_LEFT])
            y = int(stats[i, cv2.CC_STAT_TOP])
            ww = int(stats[i, cv2.CC_STAT_WIDTH])
            hh = int(stats[i, cv2.CC_STAT_HEIGHT])
            center_cross = (x <= cx <= x + ww) and (y <= cy <= y + hh)
            near_center = abs((x + ww / 2.0) - cx) < 0.25 * w
            score = area * (1.6 if center_cross else 1.0) * (1.2 if near_center else 1.0)
            if score > best_score:
                best_score = score
                keep_id = i

    out = np.zeros_like(mask_u8)
    out[labels == keep_id] = 255
    out = cv2.morphologyEx(out, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    return out


def _fill_central_gap(mask_u8, h, w):
    """填充mask中每行的中央2段间隙（V领/开襟等通用处理）。"""
    scan_bot = int(h * 0.60)
    center_lo = int(w * 0.18)
    center_hi = int(w * 0.82)
    max_gap = int(w * 0.48)

    filled = mask_u8.copy()
    n_filled = 0
    for y in range(scan_bot):
        cols = np.where(filled[y, :] > 0)[0]
        if len(cols) < 4:
            continue
        segs = []
        s = cols[0]; p = cols[0]
        for c in cols[1:]:
            if c - p > 6:
                segs.append((int(s), int(p)))
                s = c; p = c
            else:
                p = c
        segs.append((int(s), int(p)))
        if len(segs) != 2:
            continue
        gap_lo = segs[0][1] + 1
        gap_hi = segs[1][0]
        gap_c = (gap_lo + gap_hi) // 2
        gap_w = gap_hi - gap_lo
        if center_lo <= gap_c <= center_hi and 3 <= gap_w <= max_gap:
            filled[y, gap_lo:gap_hi] = 255
            n_filled += 1

    if n_filled > 10:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        filled = cv2.morphologyEx(filled, cv2.MORPH_CLOSE, k, iterations=1)
    return filled


def _prune_thin_bridges(mask_u8):
    opened = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8), iterations=1)
    opened = _keep_center_body_component(opened)
    if np.count_nonzero(opened) == 0:
        return mask_u8

    restored = cv2.dilate(opened, np.ones((3, 3), np.uint8), iterations=1)
    pruned = cv2.bitwise_and(mask_u8, restored)
    if np.count_nonzero(pruned) < 0.55 * np.count_nonzero(mask_u8):
        return mask_u8
    return pruned


def create_garment_space_mask_graph(garment_img, garment_name=None):
    h, w = garment_img.shape[:2]
    base_mask = (create_garment_mask_v5(garment_img).squeeze() > 0.1).astype(np.uint8) * 255
    mode = STYLE_MASK_MODE.get(garment_name, "normal")
    silhouette = _template_silhouette_mask(garment_img)
    if np.count_nonzero(silhouette) == 0:
        silhouette = base_mask.copy()

    if mode == "loose":
        # 防挖空：用 base 与外轮廓并集
        mask = cv2.bitwise_or(base_mask, silhouette)
        # 若仍然偏空，用模板线稿按行填充得到实心服装区域
        area_base = float(np.count_nonzero(base_mask))
        area_mask = float(np.count_nonzero(mask))
        if area_base <= 1 or area_mask < 1.10 * area_base:
            rowfill = _scanline_fill_from_stroke(garment_img)
            mask = cv2.bitwise_or(mask, rowfill)
    elif mode == "tight":
        # 防外溢：用 base 与外轮廓交集
        mask = cv2.bitwise_and(base_mask, silhouette)
    else:
        mask = cv2.bitwise_and(base_mask, silhouette)

    # 填补内部空洞（防“衣服里被挖空”）
    inv = cv2.bitwise_not(mask)
    ff = inv.copy()
    flood = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, flood, (0, 0), 255)
    holes = cv2.bitwise_not(ff)
    mask = cv2.bitwise_or(mask, holes)

    # 若仍偏小，按base_mask做保守回补
    area_base = float(np.count_nonzero(base_mask))
    area_now = float(np.count_nonzero(mask))
    if area_now < 0.90 * area_base and mode != "tight":
        recover = cv2.morphologyEx(base_mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)
        mask = cv2.bitwise_or(mask, recover)
        if mode != "loose":
            mask = cv2.bitwise_and(mask, base_mask)

    # 强约束：仅保留服装中心主体连通域，切掉服装外杂区
    mask = _keep_center_body_component(mask)

    # V领缺口修复：对顶部开裂V领（如素描图3）填充胸口空白区域
    mask = _fill_vneck_with_silhouette(mask, mask)

    # 通用中央缺口填充：扫描每行，填充位于图像中央区域的2段间隙
    # 处理V领、开襟等所有"左右分段+中间空白"的情况
    mask = _fill_central_gap(mask, h, w)

    if mode != "loose":
        mask = _prune_thin_bridges(mask)

    if mode == "tight":
        # tight款额外去散点，避免模板外区域被算入
        mask = cv2.erode(mask, np.ones((3, 3), np.uint8), iterations=1)
        mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
        mask = cv2.bitwise_and(mask, base_mask)

    # ===== 胸部+底部镂空恢复：仅loose模式(V领洪水填充泄漏), tight模式保留原设计 =====
    if mode == "loose" and np.count_nonzero(mask) > h * w * 0.005:
        top_third = np.count_nonzero(mask[:h//3,:]) / max(h//3*w,1)
        bot_two_third = np.count_nonzero(mask[h//3:,:]) / max((h-h//3)*w,1)
        last3_empty = sum(1 for y in range(h-3,h) if np.count_nonzero(mask[y,:])<3)
        bottom_missing = last3_empty>=2
        underfilled = (top_third>0.02 and bot_two_third<top_third*0.60) or bottom_missing
        if not underfilled:
            for y in range(h//3,h):
                nz=np.where(mask[y,:]>0)[0]
                if len(nz)>=2 and (nz[-1]-nz[0])-len(nz)>15:
                    underfilled=True; break
        if underfilled:
            filled=mask.copy()
            for y in range(h//3,h):
                m_cols=np.where(mask[y,:]>0)[0]
                if len(m_cols)<2: continue
                l,r=m_cols[0],m_cols[-1]
                if r-l<3: continue
                filled[y,l:r+1]=255
            mask=filled

    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)
    # 强羽化：消除mask边缘的锯齿/马赛克
    soft = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (7, 7), sigmaX=2.0)
    soft = np.clip(soft, 0.0, 1.0)
    return soft[:, :, np.newaxis].astype(np.float32), (mask > 0).astype(np.uint8)


def template_line_alpha(garment_img, mask_binary):
    alpha = extract_garment_lines(garment_img).squeeze().astype(np.float32)
    alpha = cv2.GaussianBlur(alpha, (0, 0), sigmaX=0.5)
    alpha = alpha * mask_binary.astype(np.float32)
    return np.clip(alpha, 0.0, 1.0)[:, :, np.newaxis]


def dense_subject_warp(subject_img, mask_binary, view="front"):
    h, w = mask_binary.shape
    out = np.ones((h, w, 3), dtype=np.float32) * 0.97

    ys, xs = np.where(mask_binary > 0)
    if len(xs) == 0:
        return out

    min_x, max_x = float(xs.min()), float(xs.max())
    min_y, max_y = float(ys.min()), float(ys.max())
    box_w = max(1.0, max_x - min_x)
    box_h = max(1.0, max_y - min_y)

    sh, sw, _ = subject_img.shape
    grid_x, grid_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))

    u = np.clip((grid_x - min_x) / box_w, 0.0, 1.0)
    v = np.clip((grid_y - min_y) / box_h, 0.0, 1.0)

    shoulder_t = np.clip(v / 0.30, 0.0, 1.0)
    shoulder_scale = 0.68 + 0.32 * shoulder_t
    u = np.clip(0.5 + (u - 0.5) * shoulder_scale, 0.0, 1.0)

    if view == "back":
        u = 1.0 - u

    map_x = (u * (sw - 1)).astype(np.float32)
    map_y = ((0.04 + 0.92 * v) * (sh - 1)).astype(np.float32)
    warped = cv2.remap(subject_img.astype(np.float32), map_x, map_y, interpolation=cv2.INTER_LINEAR)

    keep = mask_binary > 0
    out[keep] = warped[keep]
    return np.clip(out, 0, 1)


def pool_dense_to_graph(dense_img, mask_binary, rows=32, cols=24):
    h, w = mask_binary.shape
    cell_h = max(1, h // rows)
    cell_w = max(1, w // cols)

    nodes = np.zeros((rows, cols, 3), dtype=np.float32)
    valid = np.zeros((rows, cols), dtype=np.uint8)

    for r in range(rows):
        y0 = r * cell_h
        y1 = h if r == rows - 1 else min(h, (r + 1) * cell_h)
        for c in range(cols):
            x0 = c * cell_w
            x1 = w if c == cols - 1 else min(w, (c + 1) * cell_w)
            m = mask_binary[y0:y1, x0:x1] > 0
            if np.mean(m) < 0.04:
                continue
            patch = dense_img[y0:y1, x0:x1]
            nodes[r, c] = patch[m].mean(axis=0)
            valid[r, c] = 1

    return nodes, valid


def dual_view_graph_propagation(front_seed, back_seed, valid, steps=50):
    front = front_seed.copy()
    back = back_seed.copy()

    if np.any(valid):
        g_front = front_seed[valid > 0].mean(axis=0)
        g_back = back_seed[valid > 0].mean(axis=0)
        global_mean = 0.5 * (g_front + g_back)
    else:
        global_mean = np.array([0.95, 0.95, 0.95], dtype=np.float32)

    rows, cols, _ = front.shape

    for _ in range(steps):
        new_front = front.copy()
        new_back = back.copy()

        for r in range(rows):
            for c in range(cols):
                if valid[r, c] == 0:
                    continue

                neigh_f = []
                neigh_b = []
                for dr, dc, w in (
                    (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
                    (-1, -1, 0.65), (-1, 1, 0.65), (1, -1, 0.65), (1, 1, 0.65),
                ):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < rows and 0 <= cc < cols and valid[rr, cc] == 1:
                        neigh_f.append((front[rr, cc], w))
                        neigh_b.append((back[rr, cc], w))

                if neigh_f:
                    sum_w = float(sum(w for _, w in neigh_f))
                    f_avg = np.zeros(3, dtype=np.float32)
                    b_avg = np.zeros(3, dtype=np.float32)
                    for val, ww in neigh_f:
                        f_avg += val * (ww / sum_w)
                    for val, ww in neigh_b:
                        b_avg += val * (ww / sum_w)
                else:
                    f_avg = front[r, c]
                    b_avg = back[r, c]

                mirror_c = cols - 1 - c
                cross_from_back = back[r, mirror_c]
                cross_from_front = front[r, mirror_c]

                new_front[r, c] = (
                    0.62 * front_seed[r, c]
                    + 0.24 * f_avg
                    + 0.10 * cross_from_back
                    + 0.04 * global_mean
                )
                new_back[r, c] = (
                    0.62 * back_seed[r, c]
                    + 0.24 * b_avg
                    + 0.10 * cross_from_front
                    + 0.04 * global_mean
                )

        front = new_front
        back = new_back

    return front, back


def rasterize_graph(nodes, valid, seed_dense, mask_soft, mask_binary):
    h, w = mask_binary.shape

    dense_graph = np.zeros((h, w, 3), dtype=np.float32)
    for ch in range(3):
        dense_graph[:, :, ch] = cv2.resize(nodes[:, :, ch], (w, h), interpolation=cv2.INTER_CUBIC)

    valid_dense = cv2.resize(valid.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
    valid_dense = cv2.GaussianBlur(valid_dense, (0, 0), sigmaX=1.5)
    valid_dense = np.clip(valid_dense, 0.0, 1.0)[:, :, np.newaxis]

    # 在mask内部：有图节点的区域用图+seed混合，无图节点的区域用seed填充
    inside = (mask_binary > 0)
    merged = seed_dense.copy()
    blended = 0.55 * seed_dense + 0.45 * dense_graph
    merged[inside] = (valid_dense * blended + (1.0 - valid_dense) * seed_dense)[inside]

    merged_u8 = np.clip(merged * 255.0, 0, 255).astype(np.uint8)
    filtered_u8 = merged_u8.copy()
    for ch in range(3):
        filtered_u8[:, :, ch] = cv2.bilateralFilter(merged_u8[:, :, ch], d=5, sigmaColor=22, sigmaSpace=14)
    filtered = filtered_u8.astype(np.float32) / 255.0

    # 仅在服装内部核心区使用平滑，避免白背景向边缘渗透
    inside_core = cv2.erode(mask_binary.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=1) > 0
    merged[inside_core] = filtered[inside_core]

    # mask外部保持原底色（接近白色）
    outside = ~inside
    bg = np.array([0.97, 0.97, 0.97], dtype=np.float32)
    merged[outside] = bg
    # 不再在边缘向白底做alpha混合，防止白色缺口

    return np.clip(merged, 0, 1)


def clean_garment_lines(garment_lines, mask_binary, view="front"):
    lines = garment_lines.squeeze().astype(np.float32)
    line_bin = (lines > 0.03).astype(np.uint8)

    h, w = mask_binary.shape
    kernel = np.ones((5, 5), np.uint8)
    near_mask = cv2.dilate(mask_binary.astype(np.uint8), kernel, iterations=3)

    # 领口/肩部保留带：允许mask上方一段区域保留线稿，避免领子消失
    collar_roi = np.zeros((h, w), dtype=np.uint8)
    ys, xs = np.where(mask_binary > 0)
    if len(xs) > 0:
        y_top = int(ys.min())
        x0 = max(0, int(xs.min()) - max(4, int(0.03 * w)))
        x1 = min(w, int(xs.max()) + max(5, int(0.03 * w)) + 1)
        y0 = max(0, y_top - max(6, int(0.10 * h)))
        y1 = min(h, y_top + max(8, int(0.16 * h)))
        collar_roi[y0:y1, x0:x1] = 1

    allow = (near_mask > 0) | (collar_roi > 0)
    cleaned = ((line_bin > 0) & allow).astype(np.uint8)

    cleaned = cv2.morphologyEx(cleaned * 255, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    cleaned = cv2.GaussianBlur(cleaned.astype(np.float32) / 255.0, (0, 0), sigmaX=0.45)

    # 前后差异：背面抑制前门襟/前领等中轴细节，避免前后几乎一致
    ys, xs = np.where(mask_binary > 0)
    if len(xs) > 0:
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        cx = int(0.5 * (x0 + x1))
        bw = max(1, x1 - x0 + 1)
        bh = max(1, y1 - y0 + 1)

        if view == "back":
            # 抑制中间门襟样式线条
            c_half = max(2, int(0.06 * bw))
            yy0 = y0 + int(0.14 * bh)
            yy1 = y1 - int(0.05 * bh)
            cleaned[yy0:yy1, max(0, cx - c_half):min(w, cx + c_half + 1)] *= 0.30

            # 抑制上胸口中间区域（前领口细节在背面通常较弱）
            neck_half = max(3, int(0.18 * bw))
            ny0 = y0
            ny1 = min(h, y0 + int(0.22 * bh))
            cleaned[ny0:ny1, max(0, cx - neck_half):min(w, cx + neck_half + 1)] *= 0.45
        else:
            # 正面略强调中轴细节，但保持自然
            c_half = max(2, int(0.04 * bw))
            yy0 = y0 + int(0.10 * bh)
            yy1 = y1 - int(0.10 * bh)
            cleaned[yy0:yy1, max(0, cx - c_half):min(w, cx + c_half + 1)] *= 1.08

    cleaned = np.clip(cleaned, 0.0, 1.0)
    return cleaned[:, :, np.newaxis]


def map_front_back_graph(subject_img, garment_img, garment_lines, garment_name=None, rows=32, cols=24):
    mask_soft, mask_binary = create_garment_space_mask_graph(garment_img, garment_name=garment_name)
    lines_front = template_line_alpha(garment_img, mask_binary)
    lines_back = template_line_alpha(garment_img, mask_binary)

    front_seed_dense = dense_subject_warp(subject_img, mask_binary, view="front")
    back_seed_dense = dense_subject_warp(subject_img, mask_binary, view="back")

    front_seed_nodes, valid_f = pool_dense_to_graph(front_seed_dense, mask_binary, rows=rows, cols=cols)
    back_seed_nodes, valid_b = pool_dense_to_graph(back_seed_dense, mask_binary, rows=rows, cols=cols)
    valid = ((valid_f > 0) | (valid_b > 0)).astype(np.uint8)

    front_nodes, back_nodes = dual_view_graph_propagation(front_seed_nodes, back_seed_nodes, valid, steps=50)

    front_graph = rasterize_graph(front_nodes, valid, front_seed_dense, mask_soft, mask_binary)
    back_graph = rasterize_graph(back_nodes, valid, back_seed_dense, mask_soft, mask_binary)

    line_color = np.array([0.25, 0.25, 0.25], dtype=np.float32)
    alpha_front = np.clip(lines_front * 0.65, 0.0, 1.0)
    alpha_back = np.clip(lines_back * 0.60, 0.0, 1.0)
    front_graph = front_graph * (1 - alpha_front) + alpha_front * line_color.reshape(1, 1, 3)
    back_graph = back_graph * (1 - alpha_back) + alpha_back * line_color.reshape(1, 1, 3)

    # 最终硬约束：确保绝不越出服装区域
    keep = mask_binary > 0
    bg = np.array([0.97, 0.97, 0.97], dtype=np.float32)
    front_graph[~keep] = bg
    back_graph[~keep] = bg

    return np.clip(front_graph, 0, 1), np.clip(back_graph, 0, 1)


def build_subject_image(painting_img):
    x, y, w, h = map(int, extract_artifact_subject_v5(painting_img))
    x = max(0, x)
    y = max(0, y)
    w = max(1, w)
    h = max(1, h)
    x2 = min(painting_img.shape[1], x + w)
    y2 = min(painting_img.shape[0], y + h)
    subject = painting_img[y:y2, x:x2]
    if subject.size == 0:
        return painting_img
    return subject


def main():
    painting_path = pick_demo_painting()
    garment_paths = list_all_garments()

    painting = load_image(str(painting_path), size=None)
    if painting is None:
        raise RuntimeError("Failed to load painting image")
    subject_img = build_subject_image(painting)

    out_root = BASE_DIR / "models" / "graph_front_back_all_styles"
    out_root.mkdir(parents=True, exist_ok=True)

    rows_data = []
    for idx, garment_path in enumerate(garment_paths, start=1):
        garment = load_image(str(garment_path), size=256)
        if garment is None:
            print(f"Skip load failed: {garment_path}")
            continue

        garment_lines = extract_garment_lines(garment)

        front_graph, back_graph = map_front_back_graph(
            subject_img,
            garment,
            garment_lines,
            garment_name=garment_path.name,
            rows=32,
            cols=24,
        )

        stem = f"style_{idx:02d}"
        front_path = out_root / f"{stem}_front_graph.png"
        back_path = out_root / f"{stem}_back_graph.png"

        cv2.imwrite(str(front_path), cv2.cvtColor((front_graph * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(back_path), cv2.cvtColor((back_graph * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))

        rows_data.append((garment_path.name, garment, front_graph, back_graph))
        print(f"Done {idx:02d}/{len(garment_paths)}: {garment_path.name}")

    if not rows_data:
        raise RuntimeError("No garment mapping result generated")

    overview_path = out_root / "all_styles_front_back_graph_overview.png"
    fig, axes = plt.subplots(len(rows_data), 3, figsize=(12, 3.2 * len(rows_data)))
    if len(rows_data) == 1:
        axes = np.array([axes])

    for i, (name, garment, front_graph, back_graph) in enumerate(rows_data):
        axes[i, 0].imshow(garment)
        axes[i, 0].set_title(f"{name}\nTemplate", fontsize=9)
        axes[i, 0].axis("off")

        axes[i, 1].imshow(front_graph)
        axes[i, 1].set_title("Front (Graph)", fontsize=9)
        axes[i, 1].axis("off")

        axes[i, 2].imshow(back_graph)
        axes[i, 2].set_title("Back (Graph)", fontsize=9)
        axes[i, 2].axis("off")

    fig.suptitle(
        "All Garment Styles: Front/Back Graph-Based Mapping",
        fontsize=13,
        y=0.995,
    )
    plt.tight_layout()
    plt.savefig(overview_path, dpi=170, bbox_inches="tight")
    plt.close()

    painting_show = BASE_DIR / "models" / "graph_front_back_all_styles" / "used_painting_preview.png"
    painting_256 = cv2.resize(painting, (256, 256), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(painting_show), cv2.cvtColor((painting_256 * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))

    print(f"Painting: {painting_path}")
    print(f"Total styles: {len(rows_data)}")
    print(f"Overview saved: {overview_path}")


if __name__ == "__main__":
    main()
