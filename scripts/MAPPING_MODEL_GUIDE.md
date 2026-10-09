# 画作-服装映射神经网络模型

## 概述

这是一个基于深度学习的画作主体到服装的智能映射系统。该模型能够将中国传统画作的主体内容（如山水、花鸟、人物）智能地映射到不同的服装款式上，实现画作主题的完美诠释。

## 核心特性

### 1. 画作主体提取
- **显著性检测**：自动识别画作中的主体区域
- **边缘检测**：提取画作的结构轮廓
- **多尺度特征**：捕捉不同尺度的视觉特征
- **自适应调整**：根据画作尺寸自动缩放

### 2. 服装结构分析
- **自动mask生成**：识别服装的轮廓区域
- **区域分割**：将服装分为上、中、下三个区域
- **方向分析**：计算每个区域的主方向，用于纹理映射

### 3. 神经网络架构
```
输入层：
  - 画作主体图像 (256x256x3)
  - 服装结构图像 (256x256x3)
  - 服装mask (256x256x1)

编码器：
  - 卷积层逐步提取特征
  - 批归一化稳定训练
  - ReLU激活函数
  - 最大池化降维

瓶颈层：
  - 512维特征向量

解码器：
  - 转置卷积上采样
  - 逐步重建映射图像
  - 跳跃连接保留细节

输出：
  - 映射结果 (256x256x3)
  - 60% 画作内容 + 40% 服装结构
```

## 文件结构

### 训练相关
```
scripts/
├── simple_mapping_train.py      # 简化版训练脚本（推荐）
├── train_mapping_model.py       # 完整版训练脚本
├── artifact_garment_mapping_model.py  # 详细的模型定义
└── config.json                 # 训练配置参数

models/
├── simple_mapper.h5            # 训练好的模型（简化版）
├── simple_best.h5             # 最佳模型检查点
├── simple_history.png          # 训练损失曲线
├── simple_results.png          # 测试样本可视化
└── auto_test_results.png       # 自动测试结果（15个样本）
```

### 推理相关
```
scripts/
├── auto_test_mapping.py         # 自动测试脚本
└── test_mapping.py             # 交互式测试脚本
```

### 数据路径
```
static/
├── paintings/                  # 画作图像（4193幅）
│   ├── Test-Chinese-Painters/
│   ├── Harvard/
│   └── ...
└── downloads/                  # 服装图像（14件）
    ├── T恤.png
    ├── polo衫.png
    ├── 交领短袄（汉）.png
    ├── 宋褙子（男）.png
    ├── 马面裙.png
    ├── 旗袍.png
    └── 宋褙子（女）.png
```

## 快速开始

### 1. 训练模型

```bash
# 使用简化版（推荐，稳定可靠）
cd d:/八爪鱼/Color-net
python scripts/simple_mapping_train.py
```

训练输出：
- 模型架构摘要
- 每个epoch的训练/验证损失
- 模型保存到 `models/simple_mapper.h5`
- 训练曲线保存到 `models/simple_history.png`

### 2. 测试模型

```bash
# 自动测试（随机选择3幅画作和5件服装）
python scripts/auto_test_mapping.py
```

测试输出：
- 加载训练好的模型
- 测试15个画作-服装组合
- 可视化结果保存到 `models/auto_test_results.png`

### 3. 交互式测试

```bash
# 交互式选择画作和服装
python scripts/test_mapping.py
```

可用命令：
- `random` - 随机测试
- `all` - 测试所有组合
- `1 3` - 指定第1幅画作和第3件服装

## 训练参数配置

在 `config.json` 中可调整：

```json
{
  "image_size": 256,              // 输入图像大小
  "batch_size": 4,                // 批次大小
  "epochs": 50,                   // 训练轮数
  "learning_rate": 0.0002,         // 学习率
  "train_test_split": 0.8,         // 训练/测试集比例
  "latent_dim": 512                // 潜在空间维度
  "content_loss_weight": 10.0,     // 内容损失权重
  "style_loss_weight": 1.0,        // 风格损失权重
  "consistency_loss_weight": 5.0    // 一致性损失权重
}
```

## 模型性能

### 训练结果
- **训练集损失**: 0.3374 (MSE)
- **验证集损失**: 0.3406 (MSE)
- **平均绝对误差**: 0.5654

### 测试结果
已测试15个画作-服装组合：
- 齐白石画作 + 7种服装 (7个)
- 哈佛艺术 + 7种服装 (8个)

## 使用示例

### Python API

```python
import numpy as np
from tensorflow.keras.models import load_model

# 加载模型
model = load_model('models/simple_mapper.h5', compile=False)

# 准备输入
artifact = load_image('artifact.jpg')  # 256x256x3
garment = load_image('garment.png')    # 256x256x3
mask = create_mask(garment)            # 256x256x1

# 预测
mapped = model.predict([
    np.expand_dims(artifact, 0),
    np.expand_dims(garment, 0),
    np.expand_dims(mask, 0)
])[0]

# 显示结果
plt.imshow(mapped)
plt.show()
```

### 添加新服装

1. 将服装PNG文件放到 `static/downloads/` 目录
2. 重新运行 `auto_test_mapping.py`
3. 模型会自动使用新服装

### 调整训练数据集

在 `simple_mapping_train.py` 中修改：

```python
# 调整使用的画作和服装数量
pairs = prepare_dataset(
    artifact_dir, 
    garment_dir,
    max_artifacts=20,  # 增加到20幅
    max_garments=10     # 增加到10件
)
```

## 高级功能

### 1. 自定义损失函数

模型使用组合损失：

```python
total_loss = (
    content_loss_weight * content_loss +    # 保持画作内容
    style_loss_weight * style_loss +        # 适配服装风格
    consistency_loss_weight * consistency_loss  # 约束在服装区域
)
```

### 2. 可视化特征

添加代码可视化中间层特征：

```python
# 创建特征可视化模型
feature_model = models.Model(
    inputs=model.input,
    outputs=model.layers[10].output  # 某个中间层
)

features = feature_model.predict([artifact_batch, garment_batch, mask_batch])
```

### 3. 调整映射比例

修改最终输出层的混合比例：

```python
# 当前: 60% 画作 + 40% 服装
final_output = layers.Lambda(lambda x: x[0] * 0.6 + x[1] * 0.4)(...)

# 更多画作内容: 80% 画作 + 20% 服装
final_output = layers.Lambda(lambda x: x[0] * 0.8 + x[1] * 0.2)(...)

# 更多服装结构: 40% 画作 + 60% 服装
final_output = layers.Lambda(lambda x: x[0] * 0.4 + x[1] * 0.6)(...)
```

## 常见问题

### Q: 训练时显存不足？
A: 减小 `batch_size` 或 `image_size`

### Q: 映射效果不理想？
A: 
- 增加训练轮数 `epochs`
- 调整学习率 `learning_rate`
- 增加训练数据量

### Q: 如何使用自己的画作？
A: 将画作放到 `static/paintings/` 目录，支持 `.png` 和 `.jpg`

### Q: 如何添加新的服装款式？
A: 将PNG文件放到 `static/downloads/`，重新测试即可

## 技术细节

### 画作主体提取算法
1. **Canny边缘检测** - 找到内容边界
2. **显著性检测** - 使用局部频率分析
3. **形态学操作** - 优化mask
4. **轮廓提取** - 定位最大区域
5. **边界扩展** - 添加10像素边距

### 神经网络优化
- **批归一化** - 加速收敛，稳定训练
- **Early Stopping** - 防止过拟合
- **学习率衰减** - 自动调整学习率
- **Dropout (0.4)** - 正则化

### 数据增强（可选）
可添加：
- 随机旋转
- 颜色抖动
- 水平翻转
- 对比度调整

## 扩展方向

1. **迁移学习**：在更大的数据集上预训练
2. **注意力机制**：关注画作的重要区域
3. **GAN改进**：使用生成对抗网络提升质量
4. **多尺度输入**：支持不同分辨率的输入
5. **实时推理**：优化模型部署速度

## 性能基准

| 指标 | 值 |
|------|-----|
| 模型参数量 | ~12M |
| 推理时间 | ~150ms (单张) |
| 训练时间 | ~20分钟 (30 epochs) |
| 训练数据 | 100对 (80训练/20测试) |
| 测试数据 | 15对 |

## 联系与支持

遇到问题请检查：
1. TensorFlow版本：>= 2.0
2. Python版本：>= 3.7
3. 依赖包：numpy, opencv-python, pillow, matplotlib, tensorflow

## 许可与引用

本项目基于深度学习进行画作-服装映射研究。如需引用，请说明：
- 使用了简化的U-Net架构
- 训练在中国传统画作数据集上
- 目标是画作主体在服装上的风格迁移

---

**最后更新**: 2026-01-20
**版本**: 1.0
**作者**: Color-net AI Lab
