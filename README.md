# 数字文物库 - Django Web应用

基于Django开发的数字文物展示平台，参考故宫博物院数字文物库设计。

## 功能特性

- 文物展示与浏览
- 分类筛选（按分类、年代、颜色、展览）
- 专题展览管理
- 文物详情展示
- 数据导入/导出（支持Excel）
- 响应式设计，支持移动端
- 现代中式风格UI

## 安装步骤

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置数据库

编辑 `colornet/settings.py` 文件，修改数据库配置：

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'colornet',      # 您之前创建的数据库名
        'USER': 'root',
        'PASSWORD': '您的数据库密码',  # !!! 请填入您的真实密码
        'HOST': '127.0.0.1',
        'PORT': '3306',
    }
}
```

### 3. 创建数据库表

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. 创建超级用户

```bash
python manage.py createsuperuser
```

### 5. 运行开发服务器

```bash
python manage.py runserver
```

访问 http://127.0.0.1:8000/ 查看网站

## 数据导入

### 准备Excel文件

创建Excel文件，包含以下列（列名可自定义，但需包含以下信息）：
- 文物名称（或"名称"）
- 分类（或"类别"）
- 年代
- 颜色
- 描述（或"简介"）
- 材质
- 尺寸
- 收藏编号（或"编号"）
- 图片（或"图片路径"）- 可选

### 导入数据

```bash
python manage.py import_artifacts your_data.xlsx --image-dir /path/to/images
```

### 导出数据

```bash
python manage.py export_artifacts output.xlsx
```

包含图片路径：
```bash
python manage.py export_artifacts output.xlsx --include-images
```

## 管理后台

访问 http://127.0.0.1:8000/admin/ 进入管理后台，可以：
- 管理文物信息
- 创建分类
- 创建专题展览
- 上传图片

## 项目结构

```
colornet/
├── colornet/          # 项目主配置
│   ├── settings.py    # 配置文件
│   └── urls.py       # URL路由
├── artifacts/        # 文物应用
│   ├── models.py     # 数据模型
│   ├── views.py      # 视图函数
│   ├── urls.py       # URL配置
│   ├── admin.py      # 管理后台
│   └── management/   # 管理命令
│       └── commands/ # 导入导出命令
├── templates/        # 模板文件
│   └── artifacts/    # 文物相关模板
├── static/           # 静态文件
├── media/            # 媒体文件（图片）
└── requirements.txt   # 依赖列表
```

## 数据模型

### Category（分类）
- name: 分类名称
- slug: URL标识
- description: 分类描述

### Exhibition（专题展览）
- title: 展览标题
- slug: URL标识
- description: 展览描述
- image: 封面图片
- start_date: 开始日期
- end_date: 结束日期
- is_active: 是否显示

### Artifact（文物）
- name: 文物名称
- slug: URL标识
- description: 文物描述
- category: 所属分类
- era: 年代
- color: 颜色
- image: 文物图片
- material: 材质
- dimensions: 尺寸
- collection_number: 收藏编号
- exhibition: 所属展览
- is_active: 是否显示

## 开发说明

### 添加新功能

1. 在 `artifacts/models.py` 中添加数据模型
2. 在 `artifacts/views.py` 中添加视图函数
3. 在 `artifacts/urls.py` 中配置URL
4. 在 `templates/artifacts/` 中创建模板

### 自定义样式

编辑 `templates/base.html` 中的CSS样式，或在 `static/css/` 中添加自定义样式文件。

## 注意事项

1. 上传图片前，确保在settings.py中配置了正确的MEDIA_ROOT和MEDIA_URL
2. 数据导入前，请确保MySQL数据库已创建并配置正确
3. 图片建议使用JPEG或PNG格式，大小不超过2MB

## 技术栈

- Django 3.2.16
- MySQL
- Bootstrap 5.3
- Pandas
- Openpyxl

## 许可证

版权所有 © 2024
