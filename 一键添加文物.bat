@echo off
echo 正在添加台北故宫文物数据...
D:\anaconda3\python.exe manage.py shell -c "
from artifacts.models import Artifact, Category, Exhibition
from django.utils.text import slugify

# 获取展览和分类
exhibition = Exhibition.objects.get(slug='npm-taiwan-collection')
yuqi = Category.objects.get(name='玉器')
shiq = Category.objects.get(name='石器')
qingtongqi = Category.objects.get(name='青铜器')
shufa = Category.objects.get(name='书法')
ciqi = Category.objects.get(name='瓷器')

# 添加5件国宝
Artifact.objects.create(
    name='翠玉白菜', slug='jade-cabbage',
    description='清代玉雕精品，以整块翡翠雕琢而成，菜叶青翠欲滴，菜虫纤毫毕现，寓意多子多孙。',
    category=yuqi, era='清光绪', color='绿色', material='翡翠',
    dimensions='18.7×9.1×5.07cm', exhibition=exhibition, collection_number='故000001', is_active=True
)
print('✓ 翠玉白菜')

Artifact.objects.create(
    name='肉形石', slug='meat-shaped-stone',
    description='天然玛瑙巧雕而成，色泽纹理酷似红烧肉，层次分明，肥瘦相间，被誉为镇馆三宝之一。',
    category=shiq, era='清代', color='红褐色', material='玛瑙',
    dimensions='5.73×6.6×5.3cm', exhibition=exhibition, collection_number='故000002', is_active=True
)
print('✓ 肉形石')

Artifact.objects.create(
    name='毛公鼎', slug='maogong-ding',
    description='西周晚期重器，腹内铭文497字，记载毛公厝辅佐周宣王的史实，是研究西周历史的重要史料。',
    category=qingtongqi, era='西周宣王时期', color='青铜色', material='青铜',
    dimensions='高53.8cm，口径47.9cm', exhibition=exhibition, collection_number='故000003', is_active=True
)
print('✓ 毛公鼎')

Artifact.objects.create(
    name='王羲之快雪时晴帖', slug='wang-xizhi-kuaixue-tie',
    description='东晋王羲之书札，行书四行二十八字，笔法圆劲古雅，意态闲逸，被誉为天下第一法书。',
    category=shufa, era='东晋永和年间', color='墨色', material='纸本墨迹',
    dimensions='23×14.8cm', exhibition=exhibition, collection_number='故000004', is_active=True
)
print('✓ 王羲之快雪时晴帖')

Artifact.objects.create(
    name='莲花温碗', slug='lotus-warming-bowl',
    description='北宋汝窑代表作，釉色天青，温润如玉，造型典雅，体现宋代极简美学的最高成就。',
    category=ciqi, era='北宋徽宗时期', color='天青色', material='汝窑青瓷',
    dimensions='高13.1cm，口径18.2cm', exhibition=exhibition, collection_number='故000005', is_active=True
)
print('✓ 莲花温碗')

print('\\n🎉 5件台北故宫国宝添加完成！')
"
echo.
echo 数据添加完成！请刷新网站查看：http://127.0.0.1:8000/
pause
