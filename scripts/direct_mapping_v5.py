"""
画作-服装映射 v5 - 精细区域控制版
改进：
1. 更精确识别服装主要区域，排除领口等突出部位
2. 使用轮廓面积过滤，只保留大面积主体
3. 优化上色逻辑，避免给突出部位上色
"""
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import cv2
import os


def load_image(img_path, size=256):
    """加载并预处理图像"""
    try:
        img = Image.open(img_path)
        img_np = np.array(img)
        
        if len(img_np.shape) == 2:
            img_rgb = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
        elif len(img_np.shape) == 4:
            img_rgb = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
        else:
            img_rgb = img_np
        
        # 如果指定了size，则resize
        if size is not None:
            img_rgb = cv2.resize(img_rgb, (size, size), interpolation=cv2.INTER_AREA)
        
        # 归一化
        img_normalized = img_rgb.astype(float) / 255.0
        
        return img_normalized
    except Exception as e:
        return None


def extract_artifact_subject_v5(artifact_img):
    """
    改进的画作主体提取
    使用多种方法组合，确保主体完整
    """
    # 方法1: 基于边缘检测
    gray = cv2.cvtColor((artifact_img * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    
    # 方法2: 基于颜色对比度
    lab = cv2.cvtColor((artifact_img * 255).astype(np.uint8), cv2.COLOR_RGB2Lab)
    L, A, B = cv2.split(lab)
    mean_L = cv2.GaussianBlur(L, (21, 21), 0)
    saliency_L = np.abs(L.astype(float) - mean_L.astype(float))
    saliency_L = (saliency_L / (saliency_L.max() + 1e-6) * 255).astype(np.uint8)
    
    # 组合边缘和显著性
    combined = cv2.bitwise_or(edges, saliency_L)
    
    # 形态学操作
    kernel = np.ones((7, 7), np.uint8)
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=2)
    combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)
    
    # 找到轮廓
    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if len(contours) == 0:
        return 0, 0, artifact_img.shape[1], artifact_img.shape[0]
    
    # 选择最大的轮廓
    largest_contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest_contour)
    
    # 稍微扩展边界框（5%）
    padding = int(min(w, h) * 0.05)
    x = max(0, x - padding)
    y = max(0, y - padding)
    w = min(artifact_img.shape[1] - x, w + 2 * padding)
    h = min(artifact_img.shape[0] - y, h + 2 * padding)
    
    return x, y, w, h


def create_garment_mask_v5(garment_img):
    """
    精细的mask创建
    只保留服装主要区域，排除领口等突出部位
    """
    gray = cv2.cvtColor((garment_img * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)

    # 方法1: Canny边缘检测
    edges = cv2.Canny(gray, 30, 100)

    # 方法2: 自适应阈值
    adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 11, 2)

    # 组合两种方法
    combined = cv2.bitwise_or(edges, adaptive)

    # 形态学操作
    kernel = np.ones((7, 7), np.uint8)
    closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=2)

    # 找到所有轮廓
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 创建mask，只保留大面积轮廓
    mask = np.zeros_like(closed)

    # 计算所有轮廓面积
    areas = [cv2.contourArea(cnt) for cnt in contours]

    if len(areas) == 0:
        mask = mask.astype(float) / 255.0
        mask = mask[:, :, np.newaxis]
        return mask

    # 找到最大面积
    max_area = max(areas)

    # 只保留面积大于最大面积40%的轮廓，最多取前2个
    threshold_area = max_area * 0.40
    valid_contours = [(area, cnt) for area, cnt in zip(areas, contours) if area > threshold_area]
    valid_contours.sort(key=lambda x: x[0], reverse=True)
    for _, cnt in valid_contours[:2]:
        cv2.drawContours(mask, [cnt], -1, 255, -1)

    # 强平滑：消除轮廓填充产生的锯齿
    mask = cv2.GaussianBlur(mask.astype(np.float32), (11, 11), sigmaX=2.5)
    mask = (mask > 127).astype(np.uint8) * 255

    # 轻微膨胀，连接相邻区域
    kernel2 = np.ones((5, 5), np.uint8)
    mask = cv2.dilate(mask, kernel2, iterations=1)

    mask = mask.astype(float) / 255.0
    mask = mask[:, :, np.newaxis]

    return mask


def extract_garment_lines(garment_img):
    """提取服装线条"""
    gray = cv2.cvtColor((garment_img * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    lines = cv2.Canny(gray, 30, 100)
    lines = lines.astype(float) / 255.0
    lines = lines[:, :, np.newaxis]
    return lines


def map_artifact_to_garment_v5(artifact_img, garment_lines, garment_mask, target_size=256):
    """
    精确映射画作到服装
    只在主要服装区域上色，排除突出部位
    """
    # 1. 提取画作主体
    x, y, w, h = extract_artifact_subject_v5(artifact_img)
    artifact_subject = artifact_img[y:y+h, x:x+w]
    
    # 2. 计算mask的有效区域
    mask_squeezed = garment_mask.squeeze()
    contours, _ = cv2.findContours((mask_squeezed * 255).astype(np.uint8),
                                  cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if len(contours) == 0:
        return np.ones((target_size, target_size, 3))
    
    # 选择最大轮廓的边界框
    max_area = 0
    gx, gy, gw, gh = 0, 0, 0, 0
    for cnt in contours:
        x_cnt, y_cnt, w_cnt, h_cnt = cv2.boundingRect(cnt)
        area = w_cnt * h_cnt
        if area > max_area:
            max_area = area
            gx, gy, gw, gh = x_cnt, y_cnt, w_cnt, h_cnt
    
    # 3. 计算最佳缩放比例
    max_side = max(gw, gh)
    artifact_max_side = max(w, h)
    
    # 计算缩放比例
    scale = max_side / artifact_max_side
    
    # 适度放大（1.05倍），确保填满但不过度
    scale = min(scale, 1.05)
    
    # 调整画作主体大小
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    # 限制最大尺寸不超过target_size
    new_w = min(new_w, target_size)
    new_h = min(new_h, target_size)
    
    # 使用高质量插值
    if new_w > 0 and new_h > 0:
        artifact_resized = cv2.resize(artifact_subject, (new_w, new_h),
                                      interpolation=cv2.INTER_AREA)
    else:
        artifact_resized = artifact_subject
    
    # 4. 智能定位到mask中心
    start_x = (target_size - new_w) // 2
    start_y = (target_size - new_h) // 2
    
    # 边界检查
    start_x = max(0, start_x)
    start_y = max(0, start_y)
    end_x = min(target_size, start_x + new_w)
    end_y = min(target_size, start_y + new_h)
    
    # 5. 创建输出图像
    # 初始化为白色背景
    output = np.ones((target_size, target_size, 3))
    
    # 确保mask形状正确
    if len(garment_mask.shape) == 2:
        garment_mask = garment_mask[:, :, np.newaxis]
    
    if len(garment_lines.shape) == 2:
        garment_lines = garment_lines[:, :, np.newaxis]
    
    # 6. 精确放置画作：只在主要mask区域内显示
    actual_h = end_y - start_y
    actual_w = end_x - start_x
    
    if actual_h > 0 and actual_w > 0:
        # 调整画作尺寸以匹配放置区域
        artifact_resized = cv2.resize(artifact_resized, (actual_w, actual_h))
        
        # 创建一个临时图层，放置画作
        temp_layer = np.ones((target_size, target_size, 3))
        temp_layer[start_y:end_y, start_x:end_x] = artifact_resized
        
        # 只保留mask区域内的画作内容（精确使用mask）
        mask_crop = garment_mask[start_y:end_y, start_x:end_x]
        if len(mask_crop.shape) == 2:
            mask_crop = mask_crop[:, :, np.newaxis]
        
        output[start_y:end_y, start_x:end_x] = temp_layer[start_y:end_y, start_x:end_x] * mask_crop
        
        # 7. mask外区域保持白色
        output = output * garment_mask + np.ones_like(output) * (1 - garment_mask)
    
    # 8. 添加服装线条（深色），叠加在最上层
    line_color = np.array([0.2, 0.2, 0.2])
    lines_layer = garment_lines * line_color.reshape(1, 1, 3)
    
    # 线条叠加
    final = output * (1 - garment_lines) + lines_layer
    
    # 确保数值在[0,1]范围内
    final = np.clip(final, 0, 1)
    
    return final


def main():
    print("=" * 60)
    print("画作-服装映射 v5 - 精细区域控制版")
    print("=" * 60)

    # 获取图片
    painting_dir = 'd:/八爪鱼/Color-net/static/paintings'
    garment_dir = 'd:/八爪鱼/Color-net/static/downloads'

    # 获取画作文件
    painting_files = []
    for root, dirs, files in os.walk(painting_dir):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                painting_files.append(os.path.join(root, file))

    # 获取服装文件
    garment_files = [f for f in os.listdir(garment_dir) if f.endswith('.png')]

    print(f"找到 {len(painting_files)} 幅画作")
    print(f"找到 {len(garment_files)} 件服装")

    # 选择测试样本 - 20张画作
    test_paintings = painting_files[:min(20, len(painting_files))]
    test_garments = garment_files[:5]

    print(f"\n测试:")
    print(f"  画作: {len(test_paintings)} 幅")
    print(f"  服装: {len(test_garments)} 件")

    # 创建结果图
    fig, axes = plt.subplots(len(test_paintings), len(test_garments) + 1,
                             figsize=(4 * (len(test_garments) + 1), 4 * len(test_paintings)))

    if len(test_paintings) == 1:
        axes = axes.reshape(1, -1)

    for i, painting_path in enumerate(test_paintings):
        print(f"\n处理画作 {i+1}/{len(test_paintings)}: {os.path.basename(painting_path)[:30]}")

        # 加载画作
        painting = load_image(painting_path, size=None)  # 不resize，保持原始大小

        if painting is None:
            print(f"  跳过：无法加载")
            continue

        # 显示原始画作
        painting_display = cv2.resize(painting, (256, 256))
        axes[i, 0].imshow(painting_display)
        axes[i, 0].set_title('Original Painting', fontsize=10)
        axes[i, 0].axis('off')

        # 测试每件服装
        for j, garment_file in enumerate(test_garments):
            print(f"  服装 {j+1}/{len(test_garments)}: {garment_file[:20]}", end='')

            # 加载服装
            garment_path = os.path.join(garment_dir, garment_file)
            garment = load_image(garment_path, size=256)

            if garment is None:
                print(" - 跳过")
                axes[i, j+1].text(0.5, 0.5, 'Load Failed', ha='center', va='center')
                axes[i, j+1].axis('off')
                continue

            # 提取线条和mask
            garment_lines = extract_garment_lines(garment)
            garment_mask = create_garment_mask_v5(garment)

            # 检查mask覆盖率
            coverage = garment_mask.mean()
            print(f" (Mask: {coverage:.1%})", end='')

            # 智能映射
            mapped = map_artifact_to_garment_v5(painting, garment_lines, garment_mask)

            # 显示结果
            axes[i, j+1].imshow(mapped)
            axes[i, j+1].set_title(garment_file[:10], fontsize=10)
            axes[i, j+1].axis('off')

            print(" - OK")

    plt.tight_layout()
    output_path = 'models/direct_mapping_v5_results.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n结果已保存到: {output_path}")
    plt.close()

    # 打开图片
    os.system(f'start {output_path}')

    print("\n" + "=" * 60)
    print("完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
