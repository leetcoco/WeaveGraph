"""
画作-服装映射 v8 - 精确边界控制版
核心改进：
1. 移除膨胀操作，避免周围有色块
2. 减小羽化强度，保持圆领等细节
3. 恰到好处的边界控制
"""

import os
import cv2
import numpy as np
from PIL import Image, ImageOps
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# 设置matplotlib支持中文
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False


def load_image(img_path, size=256):
    """加载并预处理图像"""
    try:
        img = Image.open(img_path)
        
        # 如果是RGBA图像，先转换为RGB，使用白色背景
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])  # 使用alpha通道作为mask
            img = background
        elif img.mode == 'LA' or img.mode == 'P':
            img = img.convert('RGB')
        
        img_np = np.array(img)
        
        if len(img_np.shape) == 2:
            img_rgb = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
        else:
            img_rgb = img_np
        
        # 如果指定了size，则resize
        if size is not None:
            img_rgb = cv2.resize(img_rgb, (size, size), interpolation=cv2.INTER_AREA)
        
        # 归一化
        img_normalized = img_rgb.astype(float) / 255.0
        
        return img_normalized
    except Exception as e:
        print(f"加载图像失败 {img_path}: {e}")
        return None


def create_garment_mask_v8(garment_img):
    """
    创建服装mask - v8版
    改进：
    1. 完全移除膨胀操作，避免周围有色块
    2. 减小羽化到最小，保持圆领等细节
    3. 恰到好处的边界控制
    """
    # 1. 提取边缘
    gray = cv2.cvtColor((garment_img * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 30, 100)  # 降低阈值，让更多边缘被检测到
    
    print(f"[DEBUG MASK] gray shape: {gray.shape}, range: [{gray.min()}, {gray.max()}]")
    print(f"[DEBUG MASK] edges shape: {edges.shape}, non-zero pixels: {np.count_nonzero(edges)}")
    
    # 2. 膨胀边缘以连接断开的部分
    kernel = np.ones((3, 3), np.uint8)
    edges_dilated = cv2.dilate(edges, kernel, iterations=2)  # 增加迭代次数
    print(f"[DEBUG MASK] edges_dilated non-zero pixels: {np.count_nonzero(edges_dilated)}")
    
    # 3. 填充轮廓
    contours, _ = cv2.findContours(edges_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"[DEBUG MASK] found {len(contours)} contours")
    
    if len(contours) == 0:
        print("[DEBUG MASK] WARNING: No contours found, returning full mask")
        return np.ones((256, 256, 1))
    
    # 计算每个轮廓的面积
    contour_areas = [(i, cv2.contourArea(cnt)) for i, cnt in enumerate(contours)]
    print(f"[DEBUG MASK] contour areas: {contour_areas[:5]}")  # 打印前5个轮廓面积
    
    # **保留所有轮廓，不进行过滤，以保持领子、纽扣等细节**
    valid_contours = contours
    
    # 创建mask
    mask = np.zeros((256, 256), dtype=np.uint8)
    for idx, cnt in enumerate(valid_contours):
        cv2.drawContours(mask, [cnt], -1, 255, -1)
    
    print(f"[DEBUG MASK] mask before close: non-zero pixels = {np.count_nonzero(mask)}, coverage = {np.count_nonzero(mask)/(256*256)*100:.2f}%")

    close_kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=1)
    print(f"[DEBUG MASK] mask after close: non-zero pixels = {np.count_nonzero(mask)}, coverage = {np.count_nonzero(mask)/(256*256)*100:.2f}%")
    
    # **v8关键改进：完全不膨胀**
    # 避免识别周围区域导致色块
    
    # 转换为浮点数
    mask = mask.astype(float) / 255.0
    
    # **v8关键改进：极小羽化，保持圆领等细节**
    # 使用3x3最小核，sigma=0.5最小模糊
    mask_smooth = cv2.GaussianBlur(mask, (3, 3), 0.5)
    mask_smooth[mask_smooth < 0.05] = 0.0  # 降低阈值，让更多区域参与
    
    print(f"[DEBUG MASK] mask after blur: non-zero pixels = {np.count_nonzero(mask_smooth)}, coverage = {np.count_nonzero(mask_smooth)/(256*256)*100:.2f}%")
    
    mask = mask_smooth[:, :, np.newaxis]
    
    return mask


def extract_garment_lines(garment_img):
    """提取服装线条"""
    gray = cv2.cvtColor((garment_img * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    lines = cv2.Canny(gray, 50, 120)
    lines = lines.astype(float) / 255.0
    lines = lines[:, :, np.newaxis]
    return lines


def map_artifact_to_garment_v8(artifact_img, garment_img, garment_mask, target_size=256):
    """
    将画作映射到服装上 - v8优化版
    改进：前后衔接更自然，保持主体正确性
    
    参数:
        artifact_img: 画作图像 [0,1] RGB
        garment_img: 服装图像 [0,1] RGB (用于调试，暂不使用)
        garment_mask: 服装mask [0,1]
        target_size: 目标尺寸
    """
    # 1. 提取画作主体
    artifact_gray = cv2.cvtColor((artifact_img * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    print(f"[DEBUG ARTIFACT] artifact_img shape: {artifact_img.shape}, range: [{artifact_img.min():.3f}, {artifact_img.max():.3f}]")
    print(f"[DEBUG ARTIFACT] artifact_gray shape: {artifact_gray.shape}, range: [{artifact_gray.min()}, {artifact_gray.max()}]")
    
    # 组合边缘检测和显著性检测
    edges = cv2.Canny(artifact_gray, 30, 100)
    print(f"[DEBUG ARTIFACT] edges non-zero pixels: {np.count_nonzero(edges)}")
    
    # 使用Otsu阈值分割
    _, threshold = cv2.threshold(artifact_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    print(f"[DEBUG ARTIFACT] threshold non-zero pixels: {np.count_nonzero(threshold)}")
    
    # 计算显著性（反色）
    saliency = 255 - threshold
    
    # 组合边缘和显著性
    combined = cv2.bitwise_or(edges, saliency)
    print(f"[DEBUG ARTIFACT] combined non-zero pixels: {np.count_nonzero(combined)}")
    
    # 膨胀连接
    kernel = np.ones((5, 5), np.uint8)
    combined = cv2.dilate(combined, kernel, iterations=2)
    print(f"[DEBUG ARTIFACT] combined after dilate non-zero pixels: {np.count_nonzero(combined)}")
    
    # 找到轮廓
    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"[DEBUG ARTIFACT] found {len(contours)} contours")
    
    if len(contours) == 0:
        print("[DEBUG ARTIFACT] WARNING: No contours found, returning white image")
        return np.ones((target_size, target_size, 3))
    
    # 简化：直接选择最大面积的轮廓
    candidates = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)
        candidates.append((area, x, y, w, h))

    max_area, x, y, w, h = max(candidates, key=lambda t: t[0])
    print(f"[DEBUG ARTIFACT] Selected bounding box: x={x}, y={y}, w={w}, h={h}, area={max_area}")
    print(f"[DEBUG ARTIFACT] Image size: {artifact_img.shape}, bbox coverage: {(w*h)/(256*256)*100:.2f}%")
    
    # 添加padding（5%）
    padding = 0.05
    pad_x = int(w * padding)
    pad_y = int(h * padding)
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(artifact_img.shape[1], x + w + pad_x)
    y1 = min(artifact_img.shape[0], y + h + pad_y)
    w = max(1, x1 - x0)
    h = max(1, y1 - y0)
    
    print(f"[DEBUG ARTIFACT] After padding: x0={x0}, y0={y0}, w={w}, h={h}")
    
    # 提取画作主体
    artifact_subject = artifact_img[y0:y1, x0:x1]
    print(f"[DEBUG ARTIFACT] artifact_subject shape: {artifact_subject.shape}")
    
    # 2. 计算mask的边界框
    mask_squeezed = garment_mask.squeeze()
    contours, _ = cv2.findContours((mask_squeezed * 255).astype(np.uint8),
                                  cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    print(f"[DEBUG MASK BBOX] mask non-zero pixels: {np.count_nonzero(mask_squeezed)}, coverage: {np.count_nonzero(mask_squeezed)/(256*256)*100:.2f}%")
    print(f"[DEBUG MASK BBOX] found {len(contours)} contours")
    
    if len(contours) == 0:
        print("[DEBUG MASK BBOX] WARNING: No contours in mask, returning white image")
        return np.ones((target_size, target_size, 3))
    
    # 计算每个轮廓的边界框，选择最大的
    max_area = 0
    gx, gy, gw, gh = 0, 0, 0, 0
    for idx, cnt in enumerate(contours):
        cx, cy, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        if area > max_area:
            max_area = area
            gx, gy, gw, gh = cx, cy, cw, ch
        if idx < 3:  # 打印前3个轮廓
            print(f"[DEBUG MASK BBOX] Contour {idx}: x={cx}, y={cy}, w={cw}, h={ch}, area={area}")
    
    print(f"[DEBUG MASK BBOX] Selected bounding box: gx={gx}, gy={gy}, gw={gw}, gh={gh}, area={max_area}")
    print(f"[DEBUG MASK BBOX] Garment bbox coverage: {(gw*gh)/(256*256)*100:.2f}%")
    
    # 3. 智能缩放画作主体（优化缩放逻辑，更自然）
    scale_x = gw / max(1, w)
    scale_y = gh / max(1, h)
    # 优化缩放系数：根据宽高比例动态调整，避免过度拉伸
    aspect_ratio = w / h
    if aspect_ratio > 1.5:  # 宽图
        scale = max(scale_x, scale_y) * 1.2  # 增加到1.2
    elif aspect_ratio < 0.7:  # 高图
        scale = max(scale_x, scale_y) * 1.3  # 增加到1.3
    else:  # 近似正方形
        scale = max(scale_x, scale_y) * 1.15  # 增加到1.15
    
    print(f"[DEBUG SCALE] scale_x={scale_x:.3f}, scale_y={scale_y:.3f}, aspect_ratio={aspect_ratio:.3f}")
    print(f"[DEBUG SCALE] final scale={scale:.3f}")
    
    # 计算新尺寸
    new_w = int(w * scale)
    new_h = int(h * scale)
    print(f"[DEBUG SCALE] Original: {w}x{h} -> Resized: {new_w}x{new_h}")
    
    # 使用LANCZOS高质量插值，并确保颜色正确
    artifact_uint8 = (artifact_subject * 255).astype(np.uint8)
    artifact_pil = Image.fromarray(artifact_uint8, mode='RGB')
    artifact_resized = artifact_pil.resize((new_w, new_h), Image.LANCZOS)
    artifact_resized = np.array(artifact_resized).astype(float) / 255.0
    print(f"[DEBUG SCALE] artifact_resized shape: {artifact_resized.shape}")
    
    # 4. 创建白色背景
    result = np.ones((target_size, target_size, 3))
    
    # 5. 计算居中位置
    start_x = gx + (gw - new_w) // 2
    start_y = gy + (gh - new_h) // 2
    
    # 6. 优化融合算法：自然衔接
    # 创建画作的边缘羽化mask
    artifact_edge_mask = np.ones((new_h, new_w))
    edge_width = max(3, min(new_w, new_h) // 20)  # 动态边缘宽度
    
    # 为画作边缘创建渐变羽化
    for i in range(new_h):
        for j in range(new_w):
            # 计算到边缘的距离
            dist_top = i
            dist_bottom = new_h - 1 - i
            dist_left = j
            dist_right = new_w - 1 - j
            dist_edge = min(dist_top, dist_bottom, dist_left, dist_right)
            
            # 边缘羽化效果
            if dist_edge < edge_width:
                artifact_edge_mask[i, j] = max(0.3, dist_edge / edge_width)
    
    # 7. 双重融合：mask透明度 + 边缘羽化
    for i in range(new_h):
        for j in range(new_w):
            result_y = start_y + i
            result_x = start_x + j
            
            if 0 <= result_y < target_size and 0 <= result_x < target_size:
                alpha_mask = float(garment_mask[result_y, result_x, 0])
                
                if alpha_mask > 0.05:  # 进一步降低阈值，让更多区域参与融合
                    # 双重透明度：mask透明度 × 边缘羽化
                    effective_alpha = alpha_mask * artifact_edge_mask[i, j]
                    
                    # 优化融合公式：自然过渡
                    if effective_alpha > 0.01:  # 进一步降低阈值
                        # 使用更平滑的融合曲线
                        blend_factor = effective_alpha ** 0.5  # 降低指数，让融合更明显
                        result[result_y, result_x] = (
                            result[result_y, result_x] * (1 - blend_factor) + 
                            artifact_resized[i, j] * blend_factor
                        )
    
    # 8. 只对画作区域添加轻微模糊，避免影响白色背景颜色
    # 创建一个mask标识哪些位置有画作内容
    content_mask = np.zeros((target_size, target_size), dtype=np.uint8)
    for i in range(new_h):
        for j in range(new_w):
            result_y = start_y + i
            result_x = start_x + j
            if 0 <= result_y < target_size and 0 <= result_x < target_size:
                alpha_mask = float(garment_mask[result_y, result_x, 0])
                if alpha_mask > 0.05:  # 降低阈值
                    content_mask[result_y, result_x] = 255
    
    # 只对有内容的区域进行模糊
    if np.any(content_mask > 0):
        result_blurred = cv2.GaussianBlur(result, (3, 3), 0.3)
        content_mask_float = content_mask.astype(float) / 255.0
        for i in range(target_size):
            for j in range(target_size):
                if content_mask_float[i, j] > 0:
                    result[i, j] = (
                        result[i, j] * (1 - content_mask_float[i, j]) + 
                        result_blurred[i, j] * content_mask_float[i, j]
                    )
    
    # 确保数值范围正确
    result = np.clip(result, 0, 1)
    
    return result


def main():
    # 获取图片
    painting_dir = 'd:/八爪鱼/Color-net/static/paintings/Harvard/Harvard'
    garment_dir = 'd:/八爪鱼/Color-net/downloads'
    
    # 获取所有画作和服装
    painting_files = [os.path.join(painting_dir, f) for f in os.listdir(painting_dir) 
                     if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    garment_files = [os.path.join(garment_dir, f) for f in os.listdir(garment_dir)
                    if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    # 选择测试样本 - 测试50张画作
    test_paintings = painting_files[:min(50, len(painting_files))]
    test_garments = garment_files[:7]
    
    print("=" * 60)
    print("画作-服装映射 v8 - 精确边界控制版")
    print("=" * 60)
    print()
    print(f"找到 {len(painting_files)} 幅画作")
    print(f"找到 {len(garment_files)} 件服装")
    print()
    print(f"测试:")
    print(f"  画作: {len(test_paintings)} 幅")
    print(f"  服装: {len(test_garments)} 件")
    print()
    
    # 创建输出目录
    output_dir = 'd:/八爪鱼/Color-net/models'
    os.makedirs(output_dir, exist_ok=True)
    
    # 统计每件服装的mask覆盖率
    garment_mask_coverage = {}
    
    # 生成结果 - 每页5幅画作
    paintings_per_page = 5
    total_pages = (len(test_paintings) + paintings_per_page - 1) // paintings_per_page
    
    for page in range(total_pages):
        start_idx = page * paintings_per_page
        end_idx = min(start_idx + paintings_per_page, len(test_paintings))
        page_paintings = test_paintings[start_idx:end_idx]
        
        # 创建子图
        n_rows = len(page_paintings)
        n_cols = len(test_garments)
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(4*n_cols, 4*n_rows))
        if n_rows == 1:
            axes = axes.reshape(1, -1)
        if n_cols == 1:
            axes = axes.reshape(-1, 1)
        
        fig.suptitle(f'v8精确边界控制 - 画作映射结果 (第{page+1}页，共{total_pages}页)', 
                    fontsize=16, fontweight='bold')
        
        # 处理每幅画作
        for i, painting_path in enumerate(page_paintings):
            painting_name = os.path.basename(painting_path)
            artifact_img = load_image(painting_path, size=256)
            
            if artifact_img is None:
                print(f"加载画作失败: {painting_name}")
                continue
            
            # 处理每件服装
            for j, garment_path in enumerate(test_garments):
                garment_name = os.path.basename(garment_path)
                garment_img = load_image(garment_path, size=256)
                
                if garment_img is None:
                    print(f"加载服装失败: {garment_name}")
                    continue
                
                # 创建mask和线条
                garment_mask = create_garment_mask_v8(garment_img)
                garment_lines = extract_garment_lines(garment_img)
                
                # 计算mask覆盖率
                coverage = np.sum(garment_mask > 0.1) / (256 * 256) * 100
                garment_mask_coverage[garment_name] = coverage
                
                # 映射
                result = map_artifact_to_garment_v8(artifact_img, garment_lines, garment_mask)
                
                # 显示结果
                ax = axes[i, j]
                ax.imshow(result)
                ax.axis('off')
                ax.set_title(f'{garment_name}\n{coverage:.1f}%', fontsize=9)
        
        plt.tight_layout()
        output_path = os.path.join(output_dir, f'direct_mapping_v8_results_page{page+1}.png')
        plt.savefig(output_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        print(f"结果已保存到: {output_path}")
        
        # 打印处理进度
        for idx in range(start_idx, end_idx):
            painting_name = os.path.basename(test_paintings[idx])
            print(f"处理画作 {idx+1}/{len(test_paintings)}: {painting_name}")
            for garment_path in test_garments:
                garment_name = os.path.basename(garment_path)
                coverage = garment_mask_coverage.get(garment_name, 0)
                print(f"  服装 {list(test_garments).index(garment_path)+1}/{len(test_garments)}: "
                      f"{garment_name} ({coverage:.1f}%) - OK")
    
    # 打印统计信息
    print()
    print("=" * 60)
    print("Mask覆盖率统计")
    print("=" * 60)
    sorted_garments = sorted(garment_mask_coverage.items(), key=lambda x: x[1], reverse=True)
    for garment_name, coverage in sorted_garments:
        print(f"  {garment_name}: {coverage:.1f}%")
    print()
    print("=" * 60)
    print(f"完成! 共{total_pages}页结果，{len(test_paintings)}幅画×{len(test_garments)}件服装")
    print("=" * 60)


if __name__ == '__main__':
    main()
