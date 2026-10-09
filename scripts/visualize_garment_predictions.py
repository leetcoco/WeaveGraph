import os
import sys
from pathlib import Path

import django
import torch
import matplotlib.pyplot as plt
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
    """
    预测画作适合的服装款式
    
    返回: [(gender, garment_type, garment_id, confidence), ...]
    """
    # 图片预处理
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    
    img_tensor = transform(img).unsqueeze(0).to(device)
    
    # 预测
    with torch.no_grad():
        outputs = model(img_tensor)
        probabilities = torch.softmax(outputs, dim=1)[0]
    
    # 获取top-k结果
    top_k_probs, top_k_indices = torch.topk(probabilities, top_k)
    
    results = []
    for prob, idx in zip(top_k_probs, top_k_indices):
        garment_id = idx.item()
        garment_type = ID_TO_GARMENT[garment_id]
        confidence = prob.item() * 100
        
        # 确定性别
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
        print(f"无法加载图片: {e}")
        return None


def visualize_predictions(num_samples=5):
    """可视化预测结果"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")
    
    # 加载模型
    model = load_model(device)
    
    # 获取文物
    artifacts = Artifact.objects.filter(is_active=True)[:num_samples]
    
    # 创建子图
    fig, axes = plt.subplots(num_samples, 2, figsize=(15, 4*num_samples))
    if num_samples == 1:
        axes = axes.reshape(1, -1)
    
    for idx, artifact in enumerate(artifacts):
        print(f"\n处理: {artifact.name}")
        
        # 获取图片
        img = None
        img_url = None
        
        # 尝试external_image字段
        if artifact.external_image:
            img_url = artifact.external_image
            img = load_image_from_url(img_url)
        
        # 如果external_image没有，尝试image字段（可能是URL）
        if not img and artifact.image:
            image_str = str(artifact.image)
            if image_str.startswith('http'):
                img_url = image_str
                img = load_image_from_url(img_url)
        
        if not img:
            print(f"无法加载图片: {artifact.name}")
            continue
        
        # 预测
        results = predict_garments(model, img, device, top_k=5)
        
        # 显示图片
        axes[idx, 0].imshow(img)
        axes[idx, 0].set_title(f"画作: {artifact.name}", fontsize=12, fontweight='bold')
        axes[idx, 0].axis('off')
        
        # 显示预测结果
        axes[idx, 1].axis('off')
        y_pos = 0.9
        axes[idx, 1].text(0.1, y_pos, "推荐服装款式:", fontsize=12, fontweight='bold', 
                         transform=axes[idx, 1].transAxes)
        y_pos -= 0.15
        
        for i, result in enumerate(results):
            emoji = "👔" if result['gender'] == 'male' else "👗"
            text = f"{i+1}. {emoji} {result['name']}: {result['confidence']:.1f}%"
            color = 'green' if result['confidence'] > 60 else 'orange' if result['confidence'] > 40 else 'red'
            axes[idx, 1].text(0.1, y_pos, text, fontsize=11, transform=axes[idx, 1].transAxes,
                            color=color)
            y_pos -= 0.15
        
        print(f"  推荐: {results[0]['name']} ({results[0]['confidence']:.1f}%)")
    
    plt.tight_layout()
    
    # 保存图片
    output_dir = BASE_DIR / "garment_classifier"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "predictions_visualization.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n可视化结果已保存到: {output_path}")
    
    # 显示图片
    plt.show()


if __name__ == "__main__":
    visualize_predictions(num_samples=5)
