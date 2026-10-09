"""
修复前后对比
"""
import matplotlib.pyplot as plt
import numpy as np

# 修复前后的数据
garments = ['image.png', 'polo衫.png', 'T恤.png', '交领短袄（汉）.png', '宋褙子（女）.png']
old_coverage = [56.3, 39.9, 50.9, 33.4, 55.9]
new_coverage = [56.0, 54.3, 65.7, 46.8, 73.5]

# 计算提升
improvement = [new - old for new, old in zip(new_coverage, old_coverage)]

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# 图1：覆盖率对比
x = np.arange(len(garments))
width = 0.35

axes[0].bar(x - width/2, old_coverage, width, label='修复前', color='lightcoral')
axes[0].bar(x + width/2, new_coverage, width, label='修复后', color='lightgreen')
axes[0].set_xlabel('服装类型', fontsize=12)
axes[0].set_ylabel('Mask覆盖率 (%)', fontsize=12)
axes[0].set_title('修复前后Mask覆盖率对比', fontsize=14, fontweight='bold')
axes[0].set_xticks(x)
axes[0].set_xticklabels([g[:10] for g in garments], rotation=45, ha='right', fontsize=10)
axes[0].legend()
axes[0].grid(axis='y', alpha=0.3)

# 添加数值标签
for i, (old, new) in enumerate(zip(old_coverage, new_coverage)):
    axes[0].text(i - width/2, old + 1, f'{old:.1f}%', ha='center', fontsize=9)
    axes[0].text(i + width/2, new + 1, f'{new:.1f}%', ha='center', fontsize=9)

# 图2：提升百分比
colors = ['green' if imp > 0 else 'red' for imp in improvement]
axes[1].bar(x, improvement, color=colors)
axes[1].set_xlabel('服装类型', fontsize=12)
axes[1].set_ylabel('提升百分比 (%)', fontsize=12)
axes[1].set_title('修复后覆盖率提升', fontsize=14, fontweight='bold')
axes[1].set_xticks(x)
axes[1].set_xticklabels([g[:10] for g in garments], rotation=45, ha='right', fontsize=10)
axes[1].grid(axis='y', alpha=0.3)
axes[1].axhline(y=0, color='black', linestyle='-', linewidth=0.8)

# 添加数值标签
for i, imp in enumerate(improvement):
    axes[1].text(i, imp + (1 if imp > 0 else -1), 
                f'+{imp:.1f}%' if imp > 0 else f'{imp:.1f}%', 
                ha='center', fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig('models/fix_comparison.png', dpi=150, bbox_inches='tight')
print("对比图已保存到: models/fix_comparison.png")
plt.close()

import os
os.system('start models/fix_comparison.png')

print("\n" + "="*80)
print("修复总结:")
print("="*80)
for garment, old, new, imp in zip(garments, old_coverage, new_coverage, improvement):
    print(f"{garment[:20]:20s}: {old:5.1f}% -> {new:5.1f}% (提升: {imp:+5.1f}%)")

avg_old = np.mean(old_coverage)
avg_new = np.mean(new_coverage)
avg_imp = avg_new - avg_old
print("-" * 80)
print(f"{'平均':20s}: {avg_old:5.1f}% -> {avg_new:5.1f}% (提升: {avg_imp:+5.1f}%)")
print("="*80)
