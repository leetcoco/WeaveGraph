"""
提取画作色彩并映射到服装样式
"""
import os
import sys
from pathlib import Path
import django
import torch
import numpy as np
import requests
from io import BytesIO
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from sklearn.cluster import KMeans

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "colornet.settings")
django.setup()

from artifacts.models import Artifact


def extract_dominant_colors(pil_image, n_colors=5):
    """从PIL Image对象中提取主要颜色"""
    try:
        img = pil_image.resize((100, 100))  # 缩小以加快处理
        img_array = np.array(img)
        pixels = img_array.reshape(-1, 3)
        
        # 使用K-means聚类提取主色
        kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=10)
        kmeans.fit(pixels)
        
        # 获取聚类中心（即主要颜色）
        colors = kmeans.cluster_centers_.astype(int)
        
        # 按颜色占比排序（距离聚类中心近的像素多，说明颜色占比大）
        labels = kmeans.labels_
        counts = np.bincount(labels)
        sorted_indices = np.argsort(counts)[::-1]
        colors = colors[sorted_indices]
        
        return colors
    except Exception as e:
        print(f"提取颜色失败: {e}")
        return None


def load_artifact_image(artifact):
    """加载文物的图片"""
    img = None
    
    # 尝试从external_image加载
    if artifact.external_image:
        try:
            response = requests.get(artifact.external_image, timeout=10)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content)).convert("RGB")
            return img
        except:
            pass
    
    # 尝试从image字段加载
    if artifact.image:
        image_str = str(artifact.image)
        if image_str.startswith('http'):
            try:
                response = requests.get(image_str, timeout=10)
                response.raise_for_status()
                img = Image.open(BytesIO(response.content)).convert("RGB")
                return img
            except:
                pass
        else:
            # 本地路径
            try:
                img_path = Path(BASE_DIR) / image_str.lstrip('/')
                if img_path.exists():
                    img = Image.open(img_path).convert("RGB")
                    return img
            except:
                pass
    
    return None


def rgb_to_hex(rgb):
    """将RGB转换为十六进制颜色"""
    return '#{:02x}{:02x}{:02x}'.format(*rgb)


def draw_garment_with_painting_colors(ax, garment_type, painting_colors):
    """
    使用画作的色彩绘制服装
    
    Args:
        ax: matplotlib的axes对象
        garment_type: 服装类型
        painting_colors: 从画作提取的颜色数组，shape=(n_colors, 3)
    """
    # 设置背景
    ax.set_facecolor('#f5f5f5')
    
    # Canvas尺寸: 200x200
    centerX, centerY = 100, 100
    
    # 样式设置
    stroke_color = '#2C3E50'
    line_width = 2
    
    # 使用画作的第一个颜色作为主色
    if len(painting_colors) > 0:
        primary_color = rgb_to_hex(painting_colors[0])
    else:
        primary_color = '#2c3e50'  # 默认深色
    
    # 使用第二个颜色作为辅色
    if len(painting_colors) > 1:
        secondary_color = rgb_to_hex(painting_colors[1])
    else:
        secondary_color = primary_color
    
    # 绘制服装
    if garment_type == 'male_tshirt':
        # T恤 - 使用画作主色
        poly = mpatches.Polygon([
            (centerX - 18, centerY - 32), (centerX + 18, centerY - 32),
            (centerX + 22, centerY - 28), (centerX + 38, centerY - 25),
            (centerX + 38, centerY - 10), (centerX + 22, centerY - 12),
            (centerX + 20, centerY + 30), (centerX - 20, centerY + 30),
            (centerX - 22, centerY - 12), (centerX - 38, centerY - 10),
            (centerX - 38, centerY - 25), (centerX - 22, centerY - 28),
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 领口（背景色）
        theta = np.linspace(np.pi, 0, 20)
        x = centerX + 18 * np.cos(theta)
        y = centerY - 32 + 8 * np.sin(theta)
        ax.fill(x, y, color='#f5f5f5', ec=stroke_color, lw=line_width)
        
    elif garment_type == 'male_changshan':
        # 中式长衫
        poly = mpatches.Polygon([
            (centerX - 15, centerY - 30), (centerX + 15, centerY - 30),
            (centerX + 18, centerY - 20), (centerX + 22, centerY + 5),
            (centerX + 18, centerY + 25), (centerX + 22, centerY + 38),
            (centerX - 22, centerY + 38), (centerX - 18, centerY + 25),
            (centerX - 22, centerY + 5), (centerX - 18, centerY - 20),
            (centerX - 15, centerY - 30)
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 右袖
        poly = mpatches.Polygon([
            (centerX + 18, centerY - 15), (centerX + 38, centerY - 15),
            (centerX + 38, centerY + 10), (centerX + 20, centerY + 10)
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 左袖
        poly = mpatches.Polygon([
            (centerX - 18, centerY - 15), (centerX - 38, centerY - 15),
            (centerX - 38, centerY + 10), (centerX - 20, centerY + 10)
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 立领（深色）
        poly = mpatches.Polygon([
            (centerX - 8, centerY - 38), (centerX + 8, centerY - 38),
            (centerX + 6, centerY - 30), (centerX - 6, centerY - 30)
        ], facecolor='#1a252f', edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 盘扣（使用第三个颜色）
        button_color = rgb_to_hex(painting_colors[2]) if len(painting_colors) > 2 else '#c0392b'
        circle1 = mpatches.Circle((centerX, centerY - 8), 3, facecolor=button_color, edgecolor=stroke_color, lw=line_width)
        circle2 = mpatches.Circle((centerX, centerY + 8), 3, facecolor=button_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(circle1)
        ax.add_patch(circle2)
        
        # 中线
        ax.plot([centerX, centerX], [centerY - 30, centerY + 38], color=stroke_color, lw=line_width)
        
    elif garment_type == 'male_tang':
        # 唐装外套
        poly = mpatches.Polygon([
            (centerX - 18, centerY - 32), (centerX + 18, centerY - 32),
            (centerX + 22, centerY - 22), (centerX + 28, centerY + 5),
            (centerX + 20, centerY + 35), (centerX + 25, centerY + 45),
            (centerX - 25, centerY + 45), (centerX - 20, centerY + 35),
            (centerX - 28, centerY + 5), (centerX - 22, centerY - 22),
            (centerX - 18, centerY - 32)
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 右袖
        poly = mpatches.Polygon([
            (centerX + 22, centerY - 18), (centerX + 40, centerY - 18),
            (centerX + 40, centerY + 10), (centerX + 24, centerY + 10)
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 左袖
        poly = mpatches.Polygon([
            (centerX - 22, centerY - 18), (centerX - 40, centerY - 18),
            (centerX - 40, centerY + 10), (centerX - 24, centerY + 10)
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 中线
        ax.plot([centerX, centerX], [centerY - 32, centerY + 45], color=stroke_color, lw=line_width)
        
    elif garment_type == 'male_hanfu_pants':
        # 汉服长裤
        poly = mpatches.Polygon([
            (centerX - 12, centerY - 30), (centerX + 12, centerY - 30),
            (centerX + 15, centerY + 10), (centerX + 18, centerY + 45),
            (centerX - 18, centerY + 45), (centerX - 15, centerY + 10)
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
    elif garment_type == 'female_tshirt':
        # 女T恤
        poly = mpatches.Polygon([
            (centerX - 16, centerY - 32), (centerX + 16, centerY - 32),
            (centerX + 20, centerY - 28), (centerX + 35, centerY - 25),
            (centerX + 35, centerY - 10), (centerX + 20, centerY - 12),
            (centerX + 18, centerY + 28), (centerX - 18, centerY + 28),
            (centerX - 20, centerY - 12), (centerX - 35, centerY - 10),
            (centerX - 35, centerY - 25), (centerX - 20, centerY - 28),
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 领口
        theta = np.linspace(np.pi, 0, 20)
        x = centerX + 16 * np.cos(theta)
        y = centerY - 32 + 7 * np.sin(theta)
        ax.fill(x, y, color='#f5f5f5', ec=stroke_color, lw=line_width)
        
    elif garment_type == 'female_qipao':
        # 旗袍
        poly = mpatches.Polygon([
            (centerX - 10, centerY - 40), (centerX + 10, centerY - 40),
            (centerX + 12, centerY - 35), (centerX + 14, centerY - 20),
            (centerX + 12, centerY), (centerX + 10, centerY + 20),
            (centerX + 8, centerY + 40), (centerX + 6, centerY + 45),
            (centerX - 6, centerY + 45), (centerX - 8, centerY + 40),
            (centerX - 10, centerY + 20), (centerX - 12, centerY),
            (centerX - 14, centerY - 20), (centerX - 12, centerY - 35),
            (centerX - 10, centerY - 40)
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 中线
        ax.plot([centerX, centerX], [centerY - 40, centerY + 20], color=stroke_color, lw=line_width)
        
        # 纽扣（使用第二个颜色）
        button_color = secondary_color
        for y in [centerY - 20, centerY, centerY + 20]:
            circle = mpatches.Circle((centerX, y), 3, facecolor=button_color, edgecolor=stroke_color, lw=line_width)
            ax.add_patch(circle)
        
    elif garment_type == 'female_hanfu_top':
        # 汉服上衣
        poly = mpatches.Polygon([
            (centerX - 15, centerY - 35), (centerX, centerY - 18), (centerX + 15, centerY - 35),
            (centerX + 18, centerY - 25), (centerX + 20, centerY - 8), (centerX + 15, centerY + 18),
            (centerX + 12, centerY + 35), (centerX - 12, centerY + 35), (centerX - 15, centerY + 18),
            (centerX - 20, centerY - 8), (centerX - 18, centerY - 25)
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 右宽袖
        poly = mpatches.Polygon([
            (centerX + 18, centerY - 20), (centerX + 40, centerY - 20),
            (centerX + 40, centerY + 10), (centerX + 18, centerY + 5)
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 左宽袖
        poly = mpatches.Polygon([
            (centerX - 18, centerY - 20), (centerX - 40, centerY - 20),
            (centerX - 40, centerY + 10), (centerX - 18, centerY + 5)
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
    elif garment_type == 'female_hanfu_skirt':
        # 汉服裙装
        # 上衣
        poly1 = mpatches.Polygon([
            (centerX - 10, centerY - 38), (centerX + 10, centerY - 38),
            (centerX + 12, centerY - 28), (centerX + 15, centerY - 10),
            (centerX + 10, centerY + 10), (centerX + 8, centerY + 20),
            (centerX - 8, centerY + 20), (centerX - 10, centerY + 10),
            (centerX - 15, centerY - 10), (centerX - 12, centerY - 28)
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly1)
        
        # 裙子（使用第二个颜色）
        poly2 = mpatches.Polygon([
            (centerX - 28, centerY + 20), (centerX - 28, centerY + 36),
            (centerX + 28, centerY + 36), (centerX + 28, centerY + 20)
        ], facecolor=secondary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly2)
        
        # 使用第三个颜色
        if len(painting_colors) > 2:
            tertiary_color = rgb_to_hex(painting_colors[2])
        else:
            tertiary_color = secondary_color
        
        poly3 = mpatches.Polygon([
            (centerX - 22, centerY + 36), (centerX - 22, centerY + 44),
            (centerX + 22, centerY + 44), (centerX + 22, centerY + 36)
        ], facecolor=tertiary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly3)
        
        poly4 = mpatches.Polygon([
            (centerX - 16, centerY + 44), (centerX - 16, centerY + 48),
            (centerX + 16, centerY + 48), (centerX + 16, centerY + 44)
        ], facecolor=tertiary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly4)
        
    elif garment_type == 'female_tang_skirt':
        # 唐装裙套装
        # 上衣
        poly1 = mpatches.Polygon([
            (centerX - 10, centerY - 30), (centerX, centerY - 22), (centerX + 10, centerY - 30),
            (centerX + 14, centerY - 20), (centerX + 16, centerY - 8),
            (centerX + 12, centerY + 8), (centerX + 10, centerY + 12),
            (centerX - 10, centerY + 12), (centerX - 12, centerY + 8),
            (centerX - 16, centerY - 8), (centerX - 14, centerY - 20)
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly1)
        
        # 裙子
        poly2 = mpatches.Polygon([
            (centerX - 24, centerY + 12), (centerX - 24, centerY + 38),
            (centerX + 24, centerY + 38), (centerX + 24, centerY + 12)
        ], facecolor=primary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly2)
        
        # 使用第二个颜色
        poly3 = mpatches.Polygon([
            (centerX - 18, centerY + 38), (centerX - 18, centerY + 50),
            (centerX + 18, centerY + 50), (centerX + 18, centerY + 38)
        ], facecolor=secondary_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly3)
    
    # 设置坐标轴
    ax.set_xlim(0, 200)
    ax.set_ylim(0, 200)
    ax.axis('off')


def visualize_painting_to_garment(num_samples=5):
    """可视化：从画作提取颜色并应用到服装"""
    
    # 获取文物
    artifacts = Artifact.objects.filter(is_active=True)[:num_samples]
    
    if not artifacts:
        print("没有找到文物数据")
        return
    
    # 创建子图 - 每个文物3列：原图 + 提取的调色板 + 映射后的服装
    fig, axes = plt.subplots(num_samples, 3, figsize=(18, 4*num_samples))
    if num_samples == 1:
        axes = axes.reshape(1, -1)
    
    for idx, artifact in enumerate(artifacts):
        print(f"\n处理: {artifact.name}")
        
        # 加载图片
        img = load_artifact_image(artifact)
        if not img:
            print(f"无法加载图片: {artifact.name}")
            continue
        
        # 提取主要颜色
        colors = extract_dominant_colors(img, n_colors=5)
        if colors is None:
            print(f"无法提取颜色: {artifact.name}")
            continue
        
        print(f"  提取到的主要颜色: {[rgb_to_hex(c) for c in colors[:3]]}")
        
        # 显示文物图片
        axes[idx, 0].imshow(img)
        axes[idx, 0].set_title(f"Painting: {artifact.name}", fontsize=10)
        axes[idx, 0].axis('off')
        
        # 显示提取的调色板
        axes[idx, 1].set_xlim(0, 10)
        axes[idx, 1].set_ylim(0, 10)
        axes[idx, 1].axis('off')
        
        # 绘制色板
        bar_height = 10 / len(colors)
        for i, color in enumerate(colors):
            rect = mpatches.Rectangle((0, i*bar_height), 10, bar_height, 
                                     facecolor=rgb_to_hex(color), edgecolor='black', lw=1)
            axes[idx, 1].add_patch(rect)
            axes[idx, 1].text(5, i*bar_height + bar_height/2, rgb_to_hex(color), 
                            ha='center', va='center', fontsize=8, 
                            color='white' if sum(color)/3 < 128 else 'black')
        axes[idx, 1].set_title("Extracted Colors", fontsize=10)
        
        # 显示映射后的服装示例（使用第一个服装类型）
        garment_type = 'female_qipao'  # 示例
        draw_garment_with_painting_colors(axes[idx, 2], garment_type, colors)
        axes[idx, 2].set_title(f"Garment with Painting Colors", fontsize=10)
    
    plt.tight_layout()
    
    # 保存图片
    output_dir = BASE_DIR / "garment_classifier"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "painting_colors_mapped_to_garments.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n可视化结果已保存到: {output_path}")
    
    plt.show()


if __name__ == "__main__":
    print("从画作提取颜色并映射到服装样式...")
    print("=" * 70)
    visualize_painting_to_garment(num_samples=5)
