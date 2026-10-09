import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


BASE_DIR = Path(__file__).resolve().parent.parent


def draw_garment_from_design_html(ax, garment_type, title):
    """
    使用与design.html完全一致的绘制方法绘制服装
    """
    # 设置背景
    ax.set_facecolor('#f5f5f5')
    
    # Canvas尺寸: 200x200
    centerX, centerY = 100, 100
    
    # 样式设置
    stroke_color = '#2C3E50'
    line_width = 2
    
    # 男装
    if garment_type == 'male_tshirt':  # case 1
        # T恤 - 圆领短袖
        theta = np.linspace(np.pi, 0, 20)
        ax.plot(centerX - 18 + 18*np.cos(theta), centerY - 32 + 8*np.sin(theta), 
                color=stroke_color, lw=line_width)
        ax.plot([centerX - 18, centerX + 22], [centerY - 32, centerY - 28], color=stroke_color, lw=line_width)
        ax.plot([centerX + 22, centerX + 38, centerX + 38, centerX + 22, centerX + 22], 
                [centerY - 28, centerY - 25, centerY - 10, centerY - 12, centerY - 12], 
                color=stroke_color, lw=line_width)
        ax.plot([centerX + 22, centerX + 20, centerX + 20], [centerY - 12, centerY + 30, centerY + 30], 
                color=stroke_color, lw=line_width)
        ax.plot([centerX + 20, centerX - 20, centerX - 20], [centerY + 30, centerY + 30, centerY + 30], 
                color=stroke_color, lw=line_width)
        ax.plot([centerX - 20, centerX - 22, centerX - 22], [centerY + 30, centerY - 12, centerY - 12], 
                color=stroke_color, lw=line_width)
        ax.plot([centerX - 22, centerX - 38, centerX - 38, centerX - 22, centerX - 22], 
                [centerY - 12, centerY - 10, centerY - 25, centerY - 28, centerY - 28], 
                color=stroke_color, lw=line_width)
        ax.plot([centerX - 22, centerX - 18, centerX - 18], [centerY - 28, centerY - 32, centerY - 32], 
                color=stroke_color, lw=line_width)
        
    elif garment_type == 'male_changshan':  # case 2
        # 中式长衫
        poly = mpatches.Polygon([
            (centerX - 8, centerY - 38), (centerX + 8, centerY - 38),
            (centerX + 6, centerY - 30), (centerX - 6, centerY - 30)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX - 15, centerY - 30), (centerX + 15, centerY - 30),
            (centerX + 18, centerY - 20), (centerX + 22, centerY + 5),
            (centerX + 18, centerY + 25), (centerX + 22, centerY + 38),
            (centerX - 22, centerY + 38), (centerX - 18, centerY + 25),
            (centerX - 22, centerY + 5), (centerX - 18, centerY - 20),
            (centerX - 15, centerY - 30)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX + 18, centerY - 15), (centerX + 38, centerY - 15),
            (centerX + 38, centerY + 10), (centerX + 20, centerY + 10)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX - 18, centerY - 15), (centerX - 38, centerY - 15),
            (centerX - 38, centerY + 10), (centerX - 20, centerY + 10)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        ax.plot([centerX, centerX], [centerY - 30, centerY + 38], color=stroke_color, lw=line_width)
        
        circle1 = mpatches.Circle((centerX, centerY - 8), 1.5, fill=False, edgecolor=stroke_color, lw=line_width)
        circle2 = mpatches.Circle((centerX, centerY + 8), 1.5, fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(circle1)
        ax.add_patch(circle2)
        
    elif garment_type == 'male_tang':  # case 3
        # 唐装外套
        poly = mpatches.Polygon([
            (centerX - 18, centerY - 32), (centerX + 18, centerY - 32),
            (centerX + 22, centerY - 22), (centerX + 28, centerY + 5),
            (centerX + 20, centerY + 35), (centerX + 25, centerY + 45),
            (centerX - 25, centerY + 45), (centerX - 20, centerY + 35),
            (centerX - 28, centerY + 5), (centerX - 22, centerY - 22),
            (centerX - 18, centerY - 32)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX + 22, centerY - 18), (centerX + 40, centerY - 18),
            (centerX + 40, centerY + 10), (centerX + 24, centerY + 10)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX - 22, centerY - 18), (centerX - 40, centerY - 18),
            (centerX - 40, centerY + 10), (centerX - 24, centerY + 10)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        ax.plot([centerX, centerX], [centerY - 32, centerY + 45], color=stroke_color, lw=line_width)
        
    elif garment_type == 'male_hanfu_pants':  # case 4
        # 汉服长裤
        poly = mpatches.Polygon([
            (centerX - 12, centerY - 30), (centerX + 12, centerY - 30),
            (centerX + 15, centerY + 10), (centerX + 18, centerY + 45),
            (centerX - 18, centerY + 45), (centerX - 15, centerY + 10)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
    # 女装
    elif garment_type == 'female_tshirt':  # case 5
        # T恤
        theta = np.linspace(np.pi, 0, 20)
        ax.plot(centerX - 16 + 16*np.cos(theta), centerY - 32 + 7*np.sin(theta), 
                color=stroke_color, lw=line_width)
        ax.plot([centerX - 16, centerX + 20], [centerY - 32, centerY - 28], color=stroke_color, lw=line_width)
        ax.plot([centerX + 20, centerX + 35, centerX + 35, centerX + 20, centerX + 20], 
                [centerY - 28, centerY - 25, centerY - 10, centerY - 12, centerY - 12], 
                color=stroke_color, lw=line_width)
        ax.plot([centerX + 20, centerX + 18, centerX + 18], [centerY - 12, centerY + 28, centerY + 28], 
                color=stroke_color, lw=line_width)
        ax.plot([centerX + 18, centerX - 18, centerX - 18], [centerY + 28, centerY + 28, centerY + 28], 
                color=stroke_color, lw=line_width)
        ax.plot([centerX - 18, centerX - 20, centerX - 20], [centerY + 28, centerY - 12, centerY - 12], 
                color=stroke_color, lw=line_width)
        ax.plot([centerX - 20, centerX - 35, centerX - 35, centerX - 20, centerX - 20], 
                [centerY - 12, centerY - 10, centerY - 25, centerY - 28, centerY - 28], 
                color=stroke_color, lw=line_width)
        ax.plot([centerX - 20, centerX - 16, centerX - 16], [centerY - 28, centerY - 32, centerY - 32], 
                color=stroke_color, lw=line_width)
        
    elif garment_type == 'female_qipao':  # case 6
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
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        ax.plot([centerX + 10, centerX + 12, centerX + 10], [centerY - 38, centerY - 40, centerY - 30], 
                color=stroke_color, lw=line_width)
        ax.plot([centerX - 10, centerX - 12, centerX - 10], [centerY - 38, centerY - 40, centerY - 30], 
                color=stroke_color, lw=line_width)
        ax.plot([centerX, centerX], [centerY - 40, centerY + 20], color=stroke_color, lw=line_width)
        
    elif garment_type == 'female_hanfu_top':  # case 7
        # 汉服上衣
        poly = mpatches.Polygon([
            (centerX - 15, centerY - 35), (centerX, centerY - 18), (centerX + 15, centerY - 35),
            (centerX + 18, centerY - 25), (centerX + 20, centerY - 8), (centerX + 15, centerY + 18),
            (centerX + 12, centerY + 35), (centerX - 12, centerY + 35), (centerX - 15, centerY + 18),
            (centerX - 20, centerY - 8), (centerX - 18, centerY - 25)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX + 18, centerY - 20), (centerX + 40, centerY - 20),
            (centerX + 40, centerY + 10), (centerX + 18, centerY + 5)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX - 18, centerY - 20), (centerX - 40, centerY - 20),
            (centerX - 40, centerY + 10), (centerX - 18, centerY + 5)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        ax.plot([centerX - 10, centerX, centerX + 10], [centerY - 30, centerY - 18, centerY - 30], 
                color=stroke_color, lw=line_width)
        
    elif garment_type == 'female_hanfu_skirt':  # case 8
        # 汉服裙装
        poly = mpatches.Polygon([
            (centerX - 10, centerY - 38), (centerX + 10, centerY - 38),
            (centerX + 12, centerY - 28), (centerX + 15, centerY - 10),
            (centerX + 10, centerY + 10), (centerX + 8, centerY + 20),
            (centerX - 8, centerY + 20), (centerX - 10, centerY + 10),
            (centerX - 15, centerY - 10), (centerX - 12, centerY - 28)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX + 12, centerY - 25), (centerX + 30, centerY - 25),
            (centerX + 30, centerY - 8), (centerX + 14, centerY - 8)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX - 12, centerY - 25), (centerX - 30, centerY - 25),
            (centerX - 30, centerY - 8), (centerX - 14, centerY - 8)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX - 28, centerY + 20), (centerX - 28, centerY + 36),
            (centerX + 28, centerY + 36), (centerX + 28, centerY + 20)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX - 22, centerY + 36), (centerX - 22, centerY + 44),
            (centerX + 22, centerY + 44), (centerX + 22, centerY + 36)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX - 16, centerY + 44), (centerX - 16, centerY + 48),
            (centerX + 16, centerY + 48), (centerX + 16, centerY + 44)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        ax.plot([centerX - 10, centerX - 6], [centerY + 20, centerY + 48], color=stroke_color, lw=line_width)
        ax.plot([centerX, centerX], [centerY + 20, centerY + 48], color=stroke_color, lw=line_width)
        ax.plot([centerX + 10, centerX + 6], [centerY + 20, centerY + 48], color=stroke_color, lw=line_width)
        
    elif garment_type == 'female_tang_skirt':  # case 9
        # 唐装裙套装
        poly = mpatches.Polygon([
            (centerX - 10, centerY - 30), (centerX, centerY - 22), (centerX + 10, centerY - 30),
            (centerX + 14, centerY - 20), (centerX + 16, centerY - 8),
            (centerX + 12, centerY + 8), (centerX + 10, centerY + 12),
            (centerX - 10, centerY + 12), (centerX - 12, centerY + 8),
            (centerX - 16, centerY - 8), (centerX - 14, centerY - 20)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX + 14, centerY - 18), (centerX + 30, centerY - 18),
            (centerX + 30, centerY + 2), (centerX + 16, centerY + 2)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX - 14, centerY - 18), (centerX - 30, centerY - 18),
            (centerX - 30, centerY + 2), (centerX - 16, centerY + 2)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX - 24, centerY + 12), (centerX - 24, centerY + 38),
            (centerX + 24, centerY + 38), (centerX + 24, centerY + 12)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        poly = mpatches.Polygon([
            (centerX - 18, centerY + 38), (centerX - 18, centerY + 50),
            (centerX + 18, centerY + 50), (centerX + 18, centerY + 38)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
    
    # 设置坐标轴
    ax.set_xlim(0, 200)
    ax.set_ylim(0, 200)
    ax.axis('off')
    ax.set_title(title, fontsize=14, fontweight='bold')


def show_all_garments():
    """显示所有9种服装样式"""
    
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
        draw_garment_from_design_html(axes[idx], garment_type, f"{idx+1}. {title}")
    
    plt.tight_layout()
    
    # 保存图片
    output_dir = BASE_DIR / "garment_classifier"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "all_garments_preview.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"所有服装样式预览图已保存到: {output_path}")
    
    plt.show()


if __name__ == "__main__":
    print("生成所有9种服装的样式预览图...")
    print("=" * 70)
    show_all_garments()
