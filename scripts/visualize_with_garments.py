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

from scripts.train_garment_classifier import GarmentClassifier, GARMENT_TYPES, ID_TO_GARMENT
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


def draw_garment_on_canvas(canvas, garment_type):
    """在Canvas上绘制服装缩略图"""
    width, height = 200, 200
    canvas.clearRect(0, 0, width, height)
    
    # 背景色
    canvas.fillStyle = "#f5f5f5"
    canvas.fillRect(0, 0, width, height)
    
    # 绘制服装
    canvas.strokeStyle = "#333"
    canvas.lineWidth = 2
    canvas.fillStyle = "#2c3e50"
    
    if garment_type == "male_tshirt":
        # 男T恤
        canvas.beginPath()
        canvas.moveTo(60, 50)
        canvas.lineTo(140, 50)
        canvas.lineTo(140, 170)
        canvas.lineTo(60, 170)
        canvas.closePath()
        canvas.fill()
        canvas.stroke()
        # 领口
        canvas.beginPath()
        canvas.arc(100, 50, 20, 0, 3.14)
        canvas.stroke()
        
    elif garment_type == "male_changshan":
        # 中式长衫
        canvas.beginPath()
        canvas.moveTo(55, 45)
        canvas.lineTo(145, 45)
        canvas.lineTo(145, 170)
        canvas.lineTo(55, 170)
        canvas.closePath()
        canvas.fill()
        canvas.stroke()
        # 中式立领
        canvas.beginPath()
        canvas.moveTo(90, 45)
        canvas.lineTo(90, 60)
        canvas.moveTo(110, 45)
        canvas.lineTo(110, 60)
        canvas.stroke()
        # 纽扣
        canvas.fillStyle = "#c0392b"
        for y in [75, 95, 115, 135]:
            canvas.beginPath()
            canvas.arc(100, y, 4, 0, 6.28)
            canvas.fill()
        
    elif garment_type == "male_tang":
        # 唐装外套
        canvas.fillStyle = "#e74c3c"
        canvas.beginPath()
        canvas.moveTo(50, 45)
        canvas.lineTo(150, 45)
        canvas.lineTo(150, 170)
        canvas.lineTo(50, 170)
        canvas.closePath()
        canvas.fill()
        canvas.stroke()
        # 唐装对襟
        canvas.beginPath()
        canvas.moveTo(100, 45)
        canvas.lineTo(100, 170)
        canvas.moveTo(100, 45)
        canvas.lineTo(85, 55)
        canvas.moveTo(100, 45)
        canvas.lineTo(115, 55)
        canvas.stroke()
        
    elif garment_type == "male_hanfu_pants":
        # 汉服长裤
        canvas.fillStyle = "#27ae60"
        canvas.fillRect(60, 50, 80, 120)
        canvas.strokeRect(60, 50, 80, 120)
        # 上衣
        canvas.fillStyle = "#2c3e50"
        canvas.fillRect(65, 50, 70, 50)
        canvas.strokeRect(65, 50, 70, 50)
        
    elif garment_type == "female_tshirt":
        # 女T恤
        canvas.fillStyle = "#e91e63"
        canvas.beginPath()
        canvas.moveTo(50, 50)
        canvas.lineTo(150, 50)
        canvas.lineTo(150, 170)
        canvas.lineTo(50, 170)
        canvas.closePath()
        canvas.fill()
        canvas.stroke()
        # V领
        canvas.beginPath()
        canvas.arc(100, 50, 25, 0, 3.14)
        canvas.stroke()
        
    elif garment_type == "female_qipao":
        # 旗袍
        canvas.fillStyle = "#c0392b"
        canvas.beginPath()
        canvas.moveTo(45, 45)
        canvas.lineTo(155, 45)
        canvas.quadraticCurveTo(160, 100, 155, 170)
        canvas.lineTo(45, 170)
        canvas.quadraticCurveTo(40, 100, 45, 45)
        canvas.closePath()
        canvas.fill()
        canvas.stroke()
        # 立领
        canvas.beginPath()
        canvas.moveTo(90, 45)
        canvas.lineTo(90, 60)
        canvas.moveTo(110, 45)
        canvas.lineTo(110, 60)
        canvas.stroke()
        # 纽扣
        canvas.fillStyle = "#f1c40f"
        for y in [75, 95, 115, 135, 155]:
            canvas.beginPath()
            canvas.arc(100, y, 3, 0, 6.28)
            canvas.fill()
        
    elif garment_type == "female_hanfu_top":
        # 汉服上衣
        canvas.fillStyle = "#9b59b6"
        canvas.beginPath()
        canvas.moveTo(40, 45)
        canvas.lineTo(160, 45)
        canvas.lineTo(160, 120)
        canvas.lineTo(40, 120)
        canvas.closePath()
        canvas.fill()
        canvas.stroke()
        # 交领
        canvas.beginPath()
        canvas.moveTo(100, 45)
        canvas.lineTo(80, 70)
        canvas.lineTo(100, 90)
        canvas.moveTo(100, 45)
        canvas.lineTo(120, 70)
        canvas.lineTo(100, 90)
        canvas.stroke()
        
    elif garment_type == "female_hanfu_skirt":
        # 汉服裙装
        # 上衣
        canvas.fillStyle = "#9b59b6"
        canvas.beginPath()
        canvas.moveTo(50, 45)
        canvas.lineTo(150, 45)
        canvas.lineTo(150, 90)
        canvas.lineTo(50, 90)
        canvas.closePath()
        canvas.fill()
        canvas.stroke()
        # 裙子
        canvas.fillStyle = "#8e44ad"
        canvas.beginPath()
        canvas.moveTo(40, 90)
        canvas.lineTo(160, 90)
        canvas.lineTo(165, 170)
        canvas.lineTo(35, 170)
        canvas.closePath()
        canvas.fill()
        canvas.stroke()
        # 交领
        canvas.beginPath()
        canvas.moveTo(100, 45)
        canvas.lineTo(85, 60)
        canvas.moveTo(100, 45)
        canvas.lineTo(115, 60)
        canvas.stroke()
        
    elif garment_type == "female_tang_skirt":
        # 唐装裙套装
        # 上衣
        canvas.fillStyle = "#e74c3c"
        canvas.beginPath()
        canvas.moveTo(50, 45)
        canvas.lineTo(150, 45)
        canvas.lineTo(150, 95)
        canvas.lineTo(50, 95)
        canvas.closePath()
        canvas.fill()
        canvas.stroke()
        # 裙子
        canvas.fillStyle = "#c0392b"
        canvas.beginPath()
        canvas.moveTo(30, 95)
        canvas.lineTo(170, 95)
        canvas.lineTo(175, 170)
        canvas.lineTo(25, 170)
        canvas.closePath()
        canvas.fill()
        canvas.stroke()
        # 腰带
        canvas.fillStyle = "#f1c40f"
        canvas.fillRect(40, 95, 120, 5)


def create_garment_image(garment_type):
    """使用Canvas创建服装图片"""
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
    from matplotlib.figure import Figure
    
    fig = Figure(figsize=(2, 2), dpi=100)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111)
    
    # 清空并设置背景
    ax.set_xlim(0, 200)
    ax.set_ylim(0, 200)
    ax.axis('off')
    
    # 简化版绘制 - 直接用matplotlib
    draw_garment_simple(ax, garment_type)
    
    # 转换为PIL图片
    canvas.draw()
    buf = canvas.buffer_rgba()
    garment_img = Image.frombytes('RGBA', canvas.get_width_height(), buf)
    
    return garment_img


def draw_garment_simple(ax, garment_type):
    """使用matplotlib简化绘制服装"""
    # 设置背景
    ax.set_facecolor('#f5f5f5')
    
    if garment_type == "male_tshirt":
        # 男T恤
        rect = mpatches.Rectangle((60, 50), 80, 120, color='#3498db', ec='black', lw=2)
        ax.add_patch(rect)
        # 领口
        theta = np.linspace(0, np.pi, 20)
        ax.plot(100 + 20*np.cos(theta), 50 + 20*np.sin(theta), 'k-', lw=2)
        
    elif garment_type == "male_changshan":
        # 中式长衫
        rect = mpatches.Rectangle((55, 45), 90, 125, color='#2c3e50', ec='black', lw=2)
        ax.add_patch(rect)
        # 中式立领
        ax.plot([90, 90], [45, 60], 'k-', lw=2)
        ax.plot([110, 110], [45, 60], 'k-', lw=2)
        # 纽扣
        for y in [75, 95, 115, 135]:
            circle = mpatches.Circle((100, y), 4, color='#c0392b')
            ax.add_patch(circle)
        
    elif garment_type == "male_tang":
        # 唐装外套
        rect = mpatches.Rectangle((50, 45), 100, 125, color='#e74c3c', ec='black', lw=2)
        ax.add_patch(rect)
        # 唐装对襟
        ax.plot([100, 100], [45, 170], 'k-', lw=2)
        ax.plot([100, 85], [45, 55], 'k-', lw=2)
        ax.plot([100, 115], [45, 55], 'k-', lw=2)
        
    elif garment_type == "male_hanfu_pants":
        # 汉服长裤
        rect1 = mpatches.Rectangle((60, 50), 80, 120, color='#27ae60', ec='black', lw=2)
        ax.add_patch(rect1)
        # 上衣
        rect2 = mpatches.Rectangle((65, 50), 70, 50, color='#2c3e50', ec='black', lw=2)
        ax.add_patch(rect2)
        
    elif garment_type == "female_tshirt":
        # 女T恤
        rect = mpatches.Rectangle((50, 50), 100, 120, color='#e91e63', ec='black', lw=2)
        ax.add_patch(rect)
        # V领
        theta = np.linspace(0, np.pi, 20)
        ax.plot(100 + 25*np.cos(theta), 50 + 25*np.sin(theta), 'k-', lw=2)
        
    elif garment_type == "female_qipao":
        # 旗袍
        poly = mpatches.Polygon([[45, 45], [155, 45], [160, 100], [155, 170], [45, 170], [40, 100]], 
                          color='#c0392b', ec='black', lw=2)
        ax.add_patch(poly)
        # 立领
        ax.plot([90, 90], [45, 60], 'k-', lw=2)
        ax.plot([110, 110], [45, 60], 'k-', lw=2)
        # 纽扣
        for y in [75, 95, 115, 135, 155]:
            circle = mpatches.Circle((100, y), 3, color='#f1c40f')
            ax.add_patch(circle)
        
    elif garment_type == "female_hanfu_top":
        # 汉服上衣
        rect = mpatches.Rectangle((40, 45), 120, 75, color='#9b59b6', ec='black', lw=2)
        ax.add_patch(rect)
        # 交领
        ax.plot([100, 80], [45, 70], 'k-', lw=2)
        ax.plot([80, 100], [70, 90], 'k-', lw=2)
        ax.plot([100, 120], [45, 70], 'k-', lw=2)
        ax.plot([120, 100], [70, 90], 'k-', lw=2)
        
    elif garment_type == "female_hanfu_skirt":
        # 汉服裙装
        rect1 = mpatches.Rectangle((50, 45), 100, 45, color='#9b59b6', ec='black', lw=2)
        ax.add_patch(rect1)
        # 裙子
        poly = mpatches.Polygon([[40, 90], [160, 90], [165, 170], [35, 170]], 
                          color='#8e44ad', ec='black', lw=2)
        ax.add_patch(poly)
        # 交领
        ax.plot([100, 85], [45, 60], 'k-', lw=2)
        ax.plot([100, 115], [45, 60], 'k-', lw=2)
        
    elif garment_type == "female_tang_skirt":
        # 唐装裙套装
        rect1 = mpatches.Rectangle((50, 45), 100, 50, color='#e74c3c', ec='black', lw=2)
        ax.add_patch(rect1)
        # 裙子
        poly = mpatches.Polygon([[30, 95], [170, 95], [175, 170], [25, 170]], 
                          color='#c0392b', ec='black', lw=2)
        ax.add_patch(poly)
        # 腰带
        rect2 = mpatches.Rectangle((40, 95), 120, 5, color='#f1c40f', ec='black', lw=1)
        ax.add_patch(rect2)


def visualize_predictions(num_samples=5):
    """可视化预测结果 - 显示文物和服装"""
    import numpy as np
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")
    
    # 加载模型
    model = load_model(device)
    
    # 获取文物
    artifacts = Artifact.objects.filter(is_active=True)[:num_samples]
    
    # 创建子图 - 每个文物2列：原图 + 推荐服装
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
        axes[idx, 0].set_title(f"Painting: {artifact.name}", fontsize=10)
        axes[idx, 0].axis('off')
        
        # 显示推荐服装（绘制）
        axes[idx, 1].set_xlim(0, 200)
        axes[idx, 1].set_ylim(0, 200)
        axes[idx, 1].axis('off')
        draw_garment_simple(axes[idx, 1], top_result['garment_type'])
        axes[idx, 1].set_title(f"Recommended: {top_result['name']}", fontsize=10)
        
        # 显示详细信息
        axes[idx, 2].axis('off')
        info_text = f"Confidence: {top_result['confidence']:.1f}%\n"
        info_text += f"Gender: {top_result['gender'].title()}\n"
        info_text += f"Type: {top_result['garment_type']}\n"
        info_text += f"ID: {top_result['garment_id']}"
        
        # 根据置信度设置颜色
        color = 'green' if top_result['confidence'] > 50 else 'orange' if top_result['confidence'] > 30 else 'red'
        axes[idx, 2].text(0.1, 0.5, info_text, fontsize=12, transform=axes[idx, 2].transAxes,
                         color=color, va='center')
        
        print(f"  推荐: {top_result['name']} ({top_result['confidence']:.1f}%)")
    
    plt.tight_layout()
    
    # 保存图片
    output_dir = BASE_DIR / "garment_classifier"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "predictions_with_garments.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n可视化结果已保存到: {output_path}")
    
    plt.show()


if __name__ == "__main__":
    visualize_predictions(num_samples=5)
