import os
import sys
from pathlib import Path

import django
import torch
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import requests
from io import BytesIO
from PIL import Image
from torchvision import transforms


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "colornet.settings")
django.setup()

from scripts.train_garment_balanced import GarmentClassifier, GARMENT_TYPES, ID_TO_GARMENT
from artifacts.models import Artifact


def load_model(device):
    """加载训练好的服装分类模型"""
    model_path = BASE_DIR / "garment_classifier" / "garment_classifier.pt"
    if not model_path.exists():
        raise RuntimeError(f"模型文件不存在: {model_path}")
    
    checkpoint = torch.load(model_path, map_location=device)
    model = GarmentClassifier(num_classes=len(GARMENT_TYPES)).to(device)
    state = checkpoint.get("model_state_dict", checkpoint)
    new_state = model.state_dict()
    
    for k, v in list(state.items()):
        if k in new_state and new_state[k].shape == v.shape:
            new_state[k] = v
    
    model.load_state_dict(new_state)
    model.eval()
    return model


def predict_garments(model, img, device, top_k=3):
    """预测画作适合的服装款式"""
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    
    img_tensor = transform(img).unsqueeze(0).to(device)
    
    with torch.no_grad():
        outputs = model(img_tensor)
        probabilities = torch.softmax(outputs, dim=1)[0]
    
    top_k_probs, top_k_indices = torch.topk(probabilities, top_k)
    
    results = []
    for prob, idx in zip(top_k_probs, top_k_indices):
        garment_id = idx.item()
        garment_type = ID_TO_GARMENT[garment_id]
        confidence = prob.item() * 100
        
        if garment_type.startswith('male'):
            gender = 'male'
        else:
            gender = 'female'
        
        results.append({
            'gender': gender,
            'garment_type': garment_type,
            'garment_id': garment_id,
            'confidence': confidence,
            'name': garment_type.replace('_', ' ').title()
        })
    
    return results


def load_image_from_url(url):
    """从URL加载图片"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert("RGB")
        return img
    except Exception as e:
        return None


def draw_garment_from_design_html(ax, garment_type):
    """
    使用与design.html完全一致的绘制方法绘制服装
    将Canvas代码转换为matplotlib绘制
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
        # 领口 - 凹进去的圆弧
        theta = np.linspace(np.pi, 0, 20)
        ax.plot(centerX - 18 + 18*np.cos(theta), centerY - 32 + 8*np.sin(theta), 
                color=stroke_color, lw=line_width)
        # 右肩
        ax.plot([centerX - 18, centerX + 22], [centerY - 32, centerY - 28], color=stroke_color, lw=line_width)
        # 右袖 - 短袖
        ax.plot([centerX + 22, centerX + 38, centerX + 38, centerX + 22, centerX + 22], 
                [centerY - 28, centerY - 25, centerY - 10, centerY - 12, centerY - 12], 
                color=stroke_color, lw=line_width)
        # 右侧身体
        ax.plot([centerX + 22, centerX + 20, centerX + 20], [centerY - 12, centerY + 30, centerY + 30], 
                color=stroke_color, lw=line_width)
        # 底部
        ax.plot([centerX + 20, centerX - 20, centerX - 20], [centerY + 30, centerY + 30, centerY + 30], 
                color=stroke_color, lw=line_width)
        # 左侧身体
        ax.plot([centerX - 20, centerX - 22, centerX - 22], [centerY + 30, centerY - 12, centerY - 12], 
                color=stroke_color, lw=line_width)
        # 左袖 - 短袖
        ax.plot([centerX - 22, centerX - 38, centerX - 38, centerX - 22, centerX - 22], 
                [centerY - 12, centerY - 10, centerY - 25, centerY - 28, centerY - 28], 
                color=stroke_color, lw=line_width)
        # 左肩
        ax.plot([centerX - 22, centerX - 18, centerX - 18], [centerY - 28, centerY - 32, centerY - 32], 
                color=stroke_color, lw=line_width)
        
    elif garment_type == 'male_changshan':  # case 2
        # 中式长衫 - 经典中式长衫
        # 立领
        poly = mpatches.Polygon([
            (centerX - 8, centerY - 38), (centerX + 8, centerY - 38),
            (centerX + 6, centerY - 30), (centerX - 6, centerY - 30)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 领口下方的衣服主体
        poly = mpatches.Polygon([
            (centerX - 15, centerY - 30), (centerX + 15, centerY - 30),
            (centerX + 18, centerY - 20), (centerX + 22, centerY + 5),
            (centerX + 18, centerY + 25), (centerX + 22, centerY + 38),
            (centerX - 22, centerY + 38), (centerX - 18, centerY + 25),
            (centerX - 22, centerY + 5), (centerX - 18, centerY - 20),
            (centerX - 15, centerY - 30)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 右袖
        poly = mpatches.Polygon([
            (centerX + 18, centerY - 15), (centerX + 38, centerY - 15),
            (centerX + 38, centerY + 10), (centerX + 20, centerY + 10)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 左袖
        poly = mpatches.Polygon([
            (centerX - 18, centerY - 15), (centerX - 38, centerY - 15),
            (centerX - 38, centerY + 10), (centerX - 20, centerY + 10)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 中线
        ax.plot([centerX, centerX], [centerY - 30, centerY + 38], color=stroke_color, lw=line_width)
        
        # 盘扣 - 2个盘扣
        circle1 = mpatches.Circle((centerX, centerY - 8), 1.5, fill=False, edgecolor=stroke_color, lw=line_width)
        circle2 = mpatches.Circle((centerX, centerY + 8), 1.5, fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(circle1)
        ax.add_patch(circle2)
        
    elif garment_type == 'male_tang':  # case 3
        # 唐装外套 - 经典唐装
        poly = mpatches.Polygon([
            (centerX - 18, centerY - 32), (centerX + 18, centerY - 32),
            (centerX + 22, centerY - 22), (centerX + 28, centerY + 5),
            (centerX + 20, centerY + 35), (centerX + 25, centerY + 45),
            (centerX - 25, centerY + 45), (centerX - 20, centerY + 35),
            (centerX - 28, centerY + 5), (centerX - 22, centerY - 22),
            (centerX - 18, centerY - 32)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 右袖
        poly = mpatches.Polygon([
            (centerX + 22, centerY - 18), (centerX + 40, centerY - 18),
            (centerX + 40, centerY + 10), (centerX + 24, centerY + 10)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 左袖
        poly = mpatches.Polygon([
            (centerX - 22, centerY - 18), (centerX - 40, centerY - 18),
            (centerX - 40, centerY + 10), (centerX - 24, centerY + 10)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 中线
        ax.plot([centerX, centerX], [centerY - 32, centerY + 45], color=stroke_color, lw=line_width)
        
    elif garment_type == 'male_hanfu_pants':  # case 4 (but not in design.html)
        # 汉服长裤 - 简化版
        poly = mpatches.Polygon([
            (centerX - 12, centerY - 30), (centerX + 12, centerY - 30),
            (centerX + 15, centerY + 10), (centerX + 18, centerY + 45),
            (centerX - 18, centerY + 45), (centerX - 15, centerY + 10)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
    # 女装
    elif garment_type == 'female_tshirt':  # case 5
        # T恤 - 女款圆领短袖
        # 领口 - 凹进去的圆弧
        theta = np.linspace(np.pi, 0, 20)
        ax.plot(centerX - 16 + 16*np.cos(theta), centerY - 32 + 7*np.sin(theta), 
                color=stroke_color, lw=line_width)
        # 右肩
        ax.plot([centerX - 16, centerX + 20], [centerY - 32, centerY - 28], color=stroke_color, lw=line_width)
        # 右袖 - 短袖
        ax.plot([centerX + 20, centerX + 35, centerX + 35, centerX + 20, centerX + 20], 
                [centerY - 28, centerY - 25, centerY - 10, centerY - 12, centerY - 12], 
                color=stroke_color, lw=line_width)
        # 右侧身体 - 略修身
        ax.plot([centerX + 20, centerX + 18, centerX + 18], [centerY - 12, centerY + 28, centerY + 28], 
                color=stroke_color, lw=line_width)
        # 底部
        ax.plot([centerX + 18, centerX - 18, centerX - 18], [centerY + 28, centerY + 28, centerY + 28], 
                color=stroke_color, lw=line_width)
        # 左侧身体 - 略修身
        ax.plot([centerX - 18, centerX - 20, centerX - 20], [centerY + 28, centerY - 12, centerY - 12], 
                color=stroke_color, lw=line_width)
        # 左袖 - 短袖
        ax.plot([centerX - 20, centerX - 35, centerX - 35, centerX - 20, centerX - 20], 
                [centerY - 12, centerY - 10, centerY - 25, centerY - 28, centerY - 28], 
                color=stroke_color, lw=line_width)
        # 左肩
        ax.plot([centerX - 20, centerX - 16, centerX - 16], [centerY - 28, centerY - 32, centerY - 32], 
                color=stroke_color, lw=line_width)
        
    elif garment_type == 'female_qipao':  # case 6
        # 旗袍 - 经典旗袍
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
        
        # 右肩带
        ax.plot([centerX + 10, centerX + 12, centerX + 10], [centerY - 38, centerY - 40, centerY - 30], 
                color=stroke_color, lw=line_width)
        # 左肩带
        ax.plot([centerX - 10, centerX - 12, centerX - 10], [centerY - 38, centerY - 40, centerY - 30], 
                color=stroke_color, lw=line_width)
        # 中线
        ax.plot([centerX, centerX], [centerY - 40, centerY + 20], color=stroke_color, lw=line_width)
        
    elif garment_type == 'female_hanfu_top':  # case 7
        # 汉服上衣 - 宽袖设计
        poly = mpatches.Polygon([
            (centerX - 15, centerY - 35), (centerX, centerY - 18), (centerX + 15, centerY - 35),
            (centerX + 18, centerY - 25), (centerX + 20, centerY - 8), (centerX + 15, centerY + 18),
            (centerX + 12, centerY + 35), (centerX - 12, centerY + 35), (centerX - 15, centerY + 18),
            (centerX - 20, centerY - 8), (centerX - 18, centerY - 25)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 右宽袖
        poly = mpatches.Polygon([
            (centerX + 18, centerY - 20), (centerX + 40, centerY - 20),
            (centerX + 40, centerY + 10), (centerX + 18, centerY + 5)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 左宽袖
        poly = mpatches.Polygon([
            (centerX - 18, centerY - 20), (centerX - 40, centerY - 20),
            (centerX - 40, centerY + 10), (centerX - 18, centerY + 5)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 交领的装饰线
        ax.plot([centerX - 10, centerX, centerX + 10], [centerY - 30, centerY - 18, centerY - 30], 
                color=stroke_color, lw=line_width)
        
    elif garment_type == 'female_hanfu_skirt':  # case 8
        # 汉服裙装 - 上衣+大裙摆
        poly = mpatches.Polygon([
            (centerX - 10, centerY - 38), (centerX + 10, centerY - 38),
            (centerX + 12, centerY - 28), (centerX + 15, centerY - 10),
            (centerX + 10, centerY + 10), (centerX + 8, centerY + 20),
            (centerX - 8, centerY + 20), (centerX - 10, centerY + 10),
            (centerX - 15, centerY - 10), (centerX - 12, centerY - 28)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 右袖
        poly = mpatches.Polygon([
            (centerX + 12, centerY - 25), (centerX + 30, centerY - 25),
            (centerX + 30, centerY - 8), (centerX + 14, centerY - 8)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 左袖
        poly = mpatches.Polygon([
            (centerX - 12, centerY - 25), (centerX - 30, centerY - 25),
            (centerX - 30, centerY - 8), (centerX - 14, centerY - 8)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 裙摆 - 第一层
        poly = mpatches.Polygon([
            (centerX - 28, centerY + 20), (centerX - 28, centerY + 36),
            (centerX + 28, centerY + 36), (centerX + 28, centerY + 20)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 第二层
        poly = mpatches.Polygon([
            (centerX - 22, centerY + 36), (centerX - 22, centerY + 44),
            (centerX + 22, centerY + 44), (centerX + 22, centerY + 36)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 第三层
        poly = mpatches.Polygon([
            (centerX - 16, centerY + 44), (centerX - 16, centerY + 48),
            (centerX + 16, centerY + 48), (centerX + 16, centerY + 44)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 裙摆褶皱线
        ax.plot([centerX - 10, centerX - 6], [centerY + 20, centerY + 48], color=stroke_color, lw=line_width)
        ax.plot([centerX, centerX], [centerY + 20, centerY + 48], color=stroke_color, lw=line_width)
        ax.plot([centerX + 10, centerX + 6], [centerY + 20, centerY + 48], color=stroke_color, lw=line_width)
        
    elif garment_type == 'female_tang_skirt':  # case 9
        # 唐装裙套装 - 上衣+A字裙
        poly = mpatches.Polygon([
            (centerX - 10, centerY - 30), (centerX, centerY - 22), (centerX + 10, centerY - 30),
            (centerX + 14, centerY - 20), (centerX + 16, centerY - 8),
            (centerX + 12, centerY + 8), (centerX + 10, centerY + 12),
            (centerX - 10, centerY + 12), (centerX - 12, centerY + 8),
            (centerX - 16, centerY - 8), (centerX - 14, centerY - 20)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 右袖
        poly = mpatches.Polygon([
            (centerX + 14, centerY - 18), (centerX + 30, centerY - 18),
            (centerX + 30, centerY + 2), (centerX + 16, centerY + 2)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 左袖
        poly = mpatches.Polygon([
            (centerX - 14, centerY - 18), (centerX - 30, centerY - 18),
            (centerX - 30, centerY + 2), (centerX - 16, centerY + 2)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # A字裙 - 第一层
        poly = mpatches.Polygon([
            (centerX - 24, centerY + 12), (centerX - 24, centerY + 38),
            (centerX + 24, centerY + 38), (centerX + 24, centerY + 12)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
        
        # 第二层
        poly = mpatches.Polygon([
            (centerX - 18, centerY + 38), (centerX - 18, centerY + 50),
            (centerX + 18, centerY + 50), (centerX + 18, centerY + 38)
        ], fill=False, edgecolor=stroke_color, lw=line_width)
        ax.add_patch(poly)
    
    # 设置坐标轴
    ax.set_xlim(0, 200)
    ax.set_ylim(0, 200)
    ax.axis('off')


def visualize_predictions(num_samples=5):
    """可视化预测结果 - 显示文物和服装"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")
    
    # 加载模型
    model = load_model(device)
    
    # 获取文物
    artifacts = Artifact.objects.filter(is_active=True)[:num_samples]
    
    # 创建子图 - 每个文物3列：原图 + 推荐服装 + 信息
    fig, axes = plt.subplots(num_samples, 3, figsize=(18, 4*num_samples))
    if num_samples == 1:
        axes = axes.reshape(1, -1)
    
    for idx, artifact in enumerate(artifacts):
        print(f"\n处理: {artifact.name}")
        
        # 获取图片
        img = None
        img_url = None
        
        if artifact.external_image:
            img_url = artifact.external_image
            img = load_image_from_url(img_url)
        
        if not img and artifact.image:
            image_str = str(artifact.image)
            if image_str.startswith('http'):
                img_url = image_str
                img = load_image_from_url(img_url)
        
        if not img:
            print(f"无法加载图片: {artifact.name}")
            continue
        
        # 预测
        results = predict_garments(model, img, device, top_k=1)
        top_result = results[0]
        
        # 显示文物图片
        axes[idx, 0].imshow(img)
        axes[idx, 0].set_title(f"Artwork: {artifact.name}", fontsize=11)
        axes[idx, 0].axis('off')
        
        # 显示推荐服装（用design.html的绘制方法）
        draw_garment_from_design_html(axes[idx, 1], top_result['garment_type'])
        axes[idx, 1].set_title(f"Recommended: {top_result['name']}", fontsize=11)
        
        # 显示详细信息
        axes[idx, 2].axis('off')
        info_text = f"Confidence: {top_result['confidence']:.1f}%\n\n"
        info_text += f"Type: {top_result['garment_type']}\n"
        info_text += f"Gender: {top_result['gender'].title()}\n"
        info_text += f"ID: {top_result['garment_id']}\n\n"
        info_text += f"Artwork Colors: {len(artifact.color_palette) if artifact.color_palette else 0}"
        
        # 根据置信度设置颜色
        if top_result['confidence'] > 50:
            color = 'green'
        elif top_result['confidence'] > 30:
            color = 'orange'
        else:
            color = 'red'
        
        axes[idx, 2].text(0.1, 0.5, info_text, fontsize=12, transform=axes[idx, 2].transAxes,
                         color=color, va='center', family='monospace')
        
        print(f"  推荐: {top_result['name']} ({top_result['confidence']:.1f}%)")
    
    plt.tight_layout()
    
    # 保存图片
    output_dir = BASE_DIR / "garment_classifier"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "predictions_proper.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\n可视化结果已保存到: {output_path}")
    
    plt.show()


if __name__ == "__main__":
    visualize_predictions(num_samples=5)
