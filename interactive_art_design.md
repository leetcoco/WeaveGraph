# 交互式动态中国画 - 技术方案设计

## 功能概述

将静态中国画转化为动态交互式数字艺术，实现：
- 🌊 **水流动画** - 河流、瀑布、池塘的水波纹效果
- ☁️ **云雾飘动** - 云层缓慢移动、变化
- 🌸 **花草摆动** - 树木、花草随风轻摆
- 🏔️ **山石光影** - 光照变化产生的明暗效果

---

## 技术方案对比

### 方案A：用户手动标注区域（推荐 - 最实用）

**工作流程：**
1. 用户上传/选择画作
2. 用户用鼠标框选或涂抹标记区域（水/云/花/山）
3. 系统为标记区域应用对应动画
4. 生成可交互的动态展示

**优点：**
- 实现简单，2-3天可完成
- 用户可控，适合不同风格画作
- 不需要GPU，响应快
- 适合展览现场的互动体验

**缺点：**
- 需要手动操作

---

### 方案B：AI自动识别 + 手动修正（中等难度）

**工作流程：**
1. 使用颜色+纹理特征自动识别区域
   - 蓝色+平滑 = 水
   - 白色+云状纹理 = 云
   - 绿色+边缘复杂 = 树木/花草
2. 用户可调整AI识别结果
3. 应用动画

**优点：**
- 自动化程度高
- 用户工作量小

**缺点：**
- 识别准确率不稳定
- 开发周期长（1-2周）
- 需要大量测试调优

---

### 方案C：深度学习语义分割（最先进但最复杂）

**工作流程：**
1. 使用预训练模型（如SAM、DeepLab）
2. 自动分割画面中的水、云、植物等
3. 应用动画

**优点：**
- 识别精度最高
- 全自动

**缺点：**
- 需要GPU服务器
- 模型体积大（几百MB）
- 推理速度慢（几秒到几十秒）
- 开发周期长（2-4周）

---

## 推荐方案：方案A（手动标注）

**理由：**
1. **快速可实施** - 2-3天就能做出可演示的效果
2. **艺术性强** - 用户可以创造性地定义动画区域
3. **适合展览** - 观众可以亲手"激活"画作
4. **可扩展** - 后期可以加入AI辅助

---

## 详细实现设计

### 1. 前端界面（Django模板 + Canvas/WebGL）

```html
<!-- 交互式标注界面 -->
<div class="canvas-container">
    <canvas id="annotation-canvas"></canvas>
    <canvas id="animation-canvas"></canvas>
</div>

<!-- 工具栏 -->
<div class="toolbar">
    <button class="tool" data-type="water">🌊 标记水域</button>
    <button class="tool" data-type="cloud">☁️ 标记云雾</button>
    <button class="tool" data-type="flower">🌸 标记花草</button>
    <button class="tool" data-type="mountain">🏔️ 标记山石</button>
    <button class="action" data-action="play">▶️ 播放动画</button>
    <button class="action" data-action="export">💾 导出视频</button>
</div>
```

### 2. 核心动画技术

#### 水流动画（粒子系统）
```javascript
class WaterAnimation {
    constructor(region) {
        this.particles = [];
        this.region = region;
        // 生成水流粒子
        for (let i = 0; i < 100; i++) {
            this.particles.push({
                x: Math.random() * region.width,
                y: Math.random() * region.height,
                vx: 0.5 + Math.random() * 0.5,  // 向右流动
                vy: Math.random() * 0.2 - 0.1,
                alpha: Math.random()
            });
        }
    }

    update() {
        this.particles.forEach(p => {
            p.x += p.vx;
            p.y += p.vy + Math.sin(p.x * 0.01) * 0.5;  // 波浪效果

            // 循环
            if (p.x > this.region.width) {
                p.x = 0;
            }
        });
    }

    draw(ctx) {
        this.particles.forEach(p => {
            ctx.beginPath();
            ctx.arc(p.x + this.region.x, p.y + this.region.y, 2, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, 255, 255, ${p.alpha * 0.6})`;
            ctx.fill();
        });
    }
}
```

#### 云雾飘动（Perlin噪声）
```javascript
class CloudAnimation {
    constructor(region) {
        this.region = region;
        this.offset = 0;
        this.noise = new PerlinNoise();
    }

    update() {
        this.offset += 0.01;  // 缓慢飘动
    }

    draw(ctx) {
        // 使用噪声生成云雾纹理
        for (let y = 0; y < this.region.height; y += 10) {
            for (let x = 0; x < this.region.width; x += 10) {
                const noise = this.noise.get(
                    (x + this.offset * 100) * 0.01,
                    y * 0.01
                );
                const alpha = noise * 0.3;
                ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
                ctx.fillRect(
                    x + this.region.x,
                    y + this.region.y,
                    10, 10
                );
            }
        }
    }
}
```

#### 花草摆动（正弦波）
```javascript
class FlowerAnimation {
    constructor(region, imageData) {
        this.region = region;
        this.imageData = imageData;
        this.time = 0;
        this.anchorPoints = this.detectAnchorPoints();
    }

    detectAnchorPoints() {
        // 检测边缘作为摆动锚点
        // 简化版：使用区域底部作为锚点
        const points = [];
        for (let x = 0; x < this.region.width; x += 20) {
            points.push({
                x: x,
                baseY: this.region.height,
                amplitude: 5 + Math.random() * 10,
                frequency: 0.5 + Math.random() * 0.5
            });
        }
        return points;
    }

    update() {
        this.time += 0.05;
    }

    draw(ctx) {
        // 应用摆动变换
        this.anchorPoints.forEach((point, i) => {
            const swing = Math.sin(this.time * point.frequency + i * 0.5)
                        * point.amplitude;

            // 绘制摆动的植物
            ctx.save();
            ctx.translate(this.region.x + point.x, this.region.y + point.baseY);
            ctx.rotate(swing * 0.02);
            ctx.restore();
        });
    }
}
```

### 3. 后端架构（Django）

#### 模型设计
```python
# artifacts/models.py

class InteractiveArtwork(models.Model):
    """交互式动态艺术作品"""
    artifact = models.ForeignKey('Artifact', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    # 标注数据（JSON格式）
    annotations = models.JSONField(default=dict)
    # {
    #     'water': [{'x': 100, 'y': 200, 'width': 300, 'height': 100}, ...],
    #     'cloud': [...],
    #     'flower': [...],
    #     'mountain': [...]
    # }

    # 动画参数
    animation_settings = models.JSONField(default=dict)

    # 导出的视频/动图路径
    output_video = models.FileField(upload_to='interactive_videos/', null=True)

    def get_animation_config(self):
        return {
            'water': {
                'particles': 100,
                'speed': 1.0,
                'color': '#4A90E2'
            },
            'cloud': {
                'speed': 0.5,
                'density': 0.7
            },
            'flower': {
                'amplitude': 10,
                'frequency': 0.8
            }
        }
```

#### 视图函数
```python
# artifacts/views_interactive.py

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Artifact, InteractiveArtwork
import json

def interactive_art_list(request):
    """交互式艺术作品列表"""
    artifacts = Artifact.objects.filter(
        is_active=True,
        image__isnull=False
    )[:20]

    return render(request, 'artifacts/interactive_list.html', {
        'artifacts': artifacts
    })

def interactive_art_editor(request, slug):
    """交互式艺术编辑器"""
    artifact = get_object_or_404(Artifact, slug=slug)

    # 获取或创建交互作品
    interactive, created = InteractiveArtwork.objects.get_or_create(
        artifact=artifact
    )

    return render(request, 'artifacts/interactive_editor.html', {
        'artifact': artifact,
        'interactive': interactive
    })

def save_annotations(request, slug):
    """保存标注数据"""
    if request.method == 'POST':
        artifact = get_object_or_404(Artifact, slug=slug)
        interactive, _ = InteractiveArtwork.objects.get_or_create(
            artifact=artifact
        )

        interactive.annotations = json.loads(request.body)
        interactive.save()

        return JsonResponse({'status': 'success'})

def export_animation(request, slug):
    """导出动画为视频/GIF"""
    # 使用FFmpeg或Canvas录制API导出
    # 可以使用moviepy库
    pass
```

### 4. 开发路线图

#### 第一阶段：基础功能（2-3天）
- [x] 创建数据模型
- [ ] 标注界面（画布+工具栏）
- [ ] 水流动画（粒子系统）
- [ ] 实时预览

#### 第二阶段：丰富动画（3-4天）
- [ ] 云雾飘动动画
- [ ] 花草摆动动画
- [ ] 山石光影效果
- [ ] 参数调节面板

#### 第三阶段：优化体验（2-3天）
- [ ] 动画性能优化
- [ ] 导出视频/GIF功能
- [ ] 作品分享功能
- [ ] 移动端适配

---

## 技术栈

### 前端
- **Canvas API** - 图像绘制和动画
- **WebGL**（可选）- 高性能粒子效果
- **Three.js**（可选）- 3D效果

### 后端
- **Django** - Web框架
- **Pillow** - 图像处理
- **OpenCV**（可选）- 图像分析

### 导出
- **moviepy** - 视频生成
- **FFmpeg** - 视频编码
- **gif.js** - GIF生成（前端）

---

## 实际应用场景

### 1. 数字博物馆展览
- 观众点击画作，观看动态效果
- 可定制互动体验

### 2. 文化教育
- 教学演示：展示中国画的"意境"
- 学生互动：自己制作动态画作

### 3. 艺术创作
- 艺术家创作动态数字艺术
- 社交媒体分享

### 4. 文创产品
- 生成动态壁纸
- 制作电子贺卡

---

## 可行性评估

✅ **技术成熟** - Canvas/WebGL动画技术成熟
✅ **开发周期短** - 2-3天可完成基础版本
✅ **用户价值高** - 适合展览、教育、创作
✅ **可扩展性强** - 后期可加入AI、3D效果

---

## 预算估算

- **开发时间**：1-2周
- **人力成本**：1名前端开发
- **服务器成本**：普通Web服务器即可（无需GPU）
- **存储成本**：用户上传图片+导出视频，建议100GB+

---

## 下一步行动

你确认这个方案吗？如果确认，我立即开始实施：

1. 创建数据模型和URL路由
2. 开发标注界面
3. 实现水流动画（先做最简单的）
4. 测试并展示效果

还是你想调整方案？比如：
- 先实现某个特定动画（只要水流）
- 使用不同的技术方案
- 优先考虑移动端

请告诉我你的想法！
