import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


BASE_DIR = Path(__file__).resolve().parent.parent


def draw_garment_with_color(ax, garment_type, title):
    """
    绘制带颜色的服装样式 - 更真实的外观
    """
    # 设置背景
    ax.set_facecolor('#f5f5f5')
    
    # Canvas尺寸: 200x200
    centerX, centerY = 100, 100
    
    # 样式设置
    stroke_color = '#2C3E50'
    line_width = 3  # 更粗的线条
    
    # 根据服装类型设置填充颜色
    fill_colors = {
        'male_tshirt': '#3498db',        # 蓝色
        'male_changshan': '#2c3e50',     # 深蓝
        'male_tang': '#e74c3c',          # 红色
        'male_hanfu_pants': '#27ae60',    # 绿色
        'female_tshirt': '#e91e63',       # 粉红
        'female_qipao': '#c0392b',       # 深红
        'female_hanfu_top': '#9b59b6',    # 紫色
        'female_hanfu_skirt': '#8e44ad',   # 深紫
        'female_tang_skirt': '#e74c3c',   # 红色
    }
    
    fill_color = fill_colors.get(garment_type, '#3498db')
    
    # 男装
    if garment_type == 'male_tshirt':
        # T恤 - 带颜色的圆领短袖
        # 主体
        poly = mpatches.Polygon([
            (centerX - 18, centerY - 32), (centerX + 18, centerY - 32),
            (centerX + 22, centerY - 28), (centerX + 38, centerY - 25),
            (centerX + 38, centerY - 10), (centerX + 22, centerY - 12),
            (centerX + 20, centerY + 30), (centerX - 20, centerY + 30),
            (centerX - 22, centerY - 12), (centerX - 38, centerY - 10),
            (centerX - 38, centerY - 25), (centerX - 22, centerY - 28),
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 领口（用颜色覆盖）
        theta = np.linspace(np.pi, 0, 20)
        x = centerX + 18 * np.cos(theta)
        y = centerY - 32 + 8 * np.sin(theta)
        ax.fill(x, y, color='#f5f5f5', ec=stroke_color, lw=line_width)
        
    elif garment_type == 'male_changshan':
        # 中式长衫
        # 衣身
        poly = mpatches.Polygon([
            (centerX - 15, centerY - 30), (centerX + 15, centerY - 30),
            (centerX + 18, centerY - 20), (centerX + 22, centerY + 5),
            (centerX + 18, centerY + 25), (centerX + 22, centerY + 38),
            (centerX - 22, centerY + 38), (centerX - 18, centerY + 25),
            (centerX - 22, centerY + 5), (centerX - 18, centerY - 20),
            (centerX - 15, centerY - 30)
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 右袖
        poly = mpatches.Polygon([
            (centerX + 18, centerY - 15), (centerX + 38, centerY - 15),
            (centerX + 38, centerY + 10), (centerX + 20, centerY + 10)
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 左袖
        poly = mpatches.Polygon([
            (centerX - 18, centerY - 15), (centerX - 38, centerY - 15),
            (centerX - 38, centerY + 10), (centerX - 20, centerY + 10)
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 立领（深色）
        poly = mpatches.Polygon([
            (centerX - 8, centerY - 38), (centerX + 8, centerY - 38),
            (centerX + 6, centerY - 30), (centerX - 6, centerY - 30)
        ], facecolor='#1a252f', edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 盘扣（红色）
        circle1 = mpatches.Circle((centerX, centerY - 8), 3, facecolor='#c0392b', edgecolor=stroke_color, lw=line_width)
        circle2 = mpatches.Circle((centerX, centerY + 8), 3, facecolor='#c0392b', edgecolor=stroke_color, lw=line_width)
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
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 右袖
        poly = mpatches.Polygon([
            (centerX + 22, centerY - 18), (centerX + 40, centerY - 18),
            (centerX + 40, centerY + 10), (centerX + 24, centerY + 10)
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 左袖
        poly = mpatches.Polygon([
            (centerX - 22, centerY - 18), (centerX - 40, centerY - 18),
            (centerX - 40, centerY + 10), (centerX - 24, centerY + 10)
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 中线
        ax.plot([centerX, centerX], [centerY - 32, centerY + 45], color=stroke_color, lw=line_width)
        
    elif garment_type == 'male_hanfu_pants':
        # 汉服长裤
        poly = mpatches.Polygon([
            (centerX - 12, centerY - 30), (centerX + 12, centerY - 30),
            (centerX + 15, centerY + 10), (centerX + 18, centerY + 45),
            (centerX - 18, centerY + 45), (centerX - 15, centerY + 10)
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
    # 女装
    elif garment_type == 'female_tshirt':
        # 女T恤
        poly = mpatches.Polygon([
            (centerX - 16, centerY - 32), (centerX + 16, centerY - 32),
            (centerX + 20, centerY - 28), (centerX + 35, centerY - 25),
            (centerX + 35, centerY - 10), (centerX + 20, centerY - 12),
            (centerX + 18, centerY + 28), (centerX - 18, centerY + 28),
            (centerX - 20, centerY - 12), (centerX - 35, centerY - 10),
            (centerX - 35, centerY - 25), (centerX - 20, centerY - 28),
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
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
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 中线
        ax.plot([centerX, centerX], [centerY - 40, centerY + 20], color=stroke_color, lw=line_width)
        
        # 纽扣（金色）
        for y in [centerY - 20, centerY, centerY + 20]:
            circle = mpatches.Circle((centerX, y), 3, facecolor='#f1c40f', edgecolor=stroke_color, lw=line_width)
            ax.add_patch(circle)
        
    elif garment_type == 'female_hanfu_top':
        # 汉服上衣
        poly = mpatches.Polygon([
            (centerX - 15, centerY - 35), (centerX, centerY - 18), (centerX + 15, centerY - 35),
            (centerX + 18, centerY - 25), (centerX + 20, centerY - 8), (centerX + 15, centerY + 18),
            (centerX + 12, centerY + 35), (centerX - 12, centerY + 35), (centerX - 15, centerY + 18),
            (centerX - 20, centerY - 8), (centerX - 18, centerY - 25)
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 右宽袖
        poly = mpatches.Polygon([
            (centerX + 18, centerY - 20), (centerX + 40, centerY - 20),
            (centerX + 40, centerY + 10), (centerX + 18, centerY + 5)
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 左宽袖
        poly = mpatches.Polygon([
            (centerX - 18, centerY - 20), (centerX - 40, centerY - 20),
            (centerX - 40, centerY + 10), (centerX - 18, centerY + 5)
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
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
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly1)
        
        # 裙子（渐变色）
        poly2 = mpatches.Polygon([
            (centerX - 28, centerY + 20), (centerX - 28, centerY + 36),
            (centerX + 28, centerY + 36), (centerX + 28, centerY + 20)
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly2)
        
        poly3 = mpatches.Polygon([
            (centerX - 22, centerY + 36), (centerX - 22, centerY + 44),
            (centerX + 22, centerY + 44), (centerX + 22, centerY + 36)
        ], facecolor='#7e3998', edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly3)
        
        poly4 = mpatches.Polygon([
            (centerX - 16, centerY + 44), (centerX - 16, centerY + 48),
            (centerX + 16, centerY + 48), (centerX + 16, centerY + 44)
        ], facecolor='#7e3998', edgecolor=stroke_color, lw=line_width)
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
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly1)
        
        # 裙子
        poly2 = mpatches.Polygon([
            (centerX - 24, centerY + 12), (centerX - 24, centerY + 38),
            (centerX + 24, centerY + 38), (centerX + 24, centerY + 12)
        ], facecolor=fill_color, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly2)
        
        poly3 = mpatches.Polygon([
            (centerX - 18, centerY + 38), (centerX - 18, centerY + 50),
            (centerX + 18, centerY + 50), (centerX + 18, centerY + 38)
        ], facecolor='#c0392b', edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly3)
    
    # 设置坐标轴
    ax.set_xlim(0, 200)
    ax.set_ylim(0, 200)
    ax.axis('off')
    ax.set_title(title, fontsize=12, fontweight='bold')


def show_all_garments_with_color():
    """显示所有9种服装的彩色样式"""
    
    # 定义所有服装类型
    garments = [
        ('male_tshirt', '男 T恤'),
        ('male_changshan', '男 中式长衫'),
        ('male_tang', '男 唐装外套'),
        ('male_hanfu_pants', '男 汉服长裤'),
        ('female_tshirt', '女 T恤'),
        ('female_qipao', '女 旗袍'),
        ('female_hanfu_top', '女 汉服上衣'),
        ('female_hanfu_skirt', '女 汉服裙装'),
        ('female_tang_skirt', '女 唐装裙套装'),
    ]
    
    # 创建3x3的子图
    fig, axes = plt.subplots(3, 3, figsize=(15, 15))
    axes = axes.flatten()
    
    for idx, (garment_type, title) in enumerate(garments):
        draw_garment_with_color(axes[idx], garment_type, f"{idx+1}. {title}")
    
    plt.tight_layout()
    
    # 保存图片
    output_dir = BASE_DIR / "garment_classifier"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "all_garments_colored.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"所有服装彩色预览图已保存到: {output_path}")
    
    plt.show()


if __name__ == "__main__":
    print("生成所有9种服装的彩色样式预览图...")
    print("=" * 70)
    show_all_garments_with_color()
