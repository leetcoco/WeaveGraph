import os
from pathlib import Path
import sys

import cv2
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np


# 配置中文字体支持
def setup_chinese_font():
    """设置matplotlib中文字体"""
    # Windows系统常用中文字体列表
    chinese_fonts = [
        'Microsoft YaHei', 'SimHei', 'SimSun', 'KaiTi', 'FangSong',
        'STHeiti', 'STSong', 'STKaiti', 'STFangsong',
    ]
    
    # 获取系统可用字体
    available_fonts = {f.name for f in fm.fontManager.ttflist}
    
    for font in chinese_fonts:
        if font in available_fonts:
            plt.rcParams['font.sans-serif'] = [font] + plt.rcParams.get('font.sans-serif', [])
            plt.rcParams['axes.unicode_minus'] = False
            print(f"使用中文字体: {font}")
            return True
    
    # 如果没找到，尝试使用系统字体目录
    import platform
    if platform.system() == 'Windows':
        win_font_dir = Path(os.environ.get('SystemRoot', 'C:\\Windows')) / 'Fonts'
        font_files = list(win_font_dir.glob('*ttc')) + list(win_font_dir.glob('*ttf'))
        for ff in font_files:
            name_lower = ff.name.lower()
            if any(k in name_lower for k in ['simhei', 'simsun', 'yahei', 'msyh', 'kaiti']):
                try:
                    fm.fontManager.addfont(str(ff))
                    font_prop = fm.FontProperties(fname=str(ff))
                    plt.rcParams['font.sans-serif'] = [font_prop.get_name()] + plt.rcParams.get('font.sans-serif', [])
                    plt.rcParams['axes.unicode_minus'] = False
                    print(f"加载中文字体: {ff.name}")
                    return True
                except Exception:
                    continue
    
    print("警告: 未找到中文字体，中文可能显示为方块")
    return False


# 初始化中文字体
setup_chinese_font()


BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


STYLE_MASK_MODE = {
    "交领短袄（汉）.png": "tight",
    "宋褙子（男）.png": "tight",
    "常见服装素描图 (1).png": "tight",
    "常见服装素描图 (2).png": "tight",
    "常见服装素描图.png": "tight",
    "旗袍.png": "loose",
    "常见服装素描图 (3).png": "loose",
}
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from direct_mapping_v5 import (  # noqa: E402
    extract_artifact_subject_v5,
    extract_garment_lines,
    load_image,
)


def pick_multiple_paintings(n=5):
    """选择多幅画作"""
    painting_dir = BASE_DIR / "static" / "paintings"
    painting_files = []
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        painting_files.extend(painting_dir.glob(f"**/{ext}"))
    painting_files = sorted(painting_files)
    if not painting_files:
        raise RuntimeError(f"No painting file found in: {painting_dir}")
    return painting_files[:n]


def list_all_garments():
    garment_dir = BASE_DIR / "static" / "downloads"
    garment_files = sorted(garment_dir.glob("*.png"))
    if not garment_files:
        raise RuntimeError(f"No garment file found in: {garment_dir}")
    return garment_files


def _keep_medium_components(binary_u8, min_area):
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary_u8, connectivity=8)
    out = np.zeros_like(binary_u8)
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            out[labels == i] = 255
    return out


def create_garment_mask_v8(garment_img, size=256):
    """
    V8版本Mask计算：参考 design.html 的 createGarmentMaskV8
    - Canny边缘检测 + 膨胀连接断线
    - 只保留面积>最大面积40%的前2个轮廓
    - 洪水填充确定内部区域
    - 用凸包形状约束去除边缘溢出（领口/袖口/下摆）
    - 极小羽化3x3高斯模糊
    - 如果Canny检测失败，自动回退到基于线条的mask方法
    """
    h, w = garment_img.shape[:2]

    # 1. 转为灰度
    gray = cv2.cvtColor((np.clip(garment_img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)

    # 2. Canny边缘检测 (阈值50, 120)
    edges = cv2.Canny(gray, 50, 120)

    # 3. 最小膨胀连接断线（2x2核减少外扩）
    dilated = cv2.dilate(edges, np.ones((2, 2)), iterations=1)

    # 4. 查找轮廓
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if len(contours) == 0 or max(cv2.contourArea(c) for c in contours) < h * w * 0.02:
        return _fallback_line_based_mask(garment_img)

    # 5. 只保留面积 > 最大面积40% 的轮廓，最多取前2个
    areas = [cv2.contourArea(c) for c in contours]
    max_area = max(areas)
    threshold = max_area * 0.4

    valid_contours = [c for c, a in zip(contours, areas) if a > threshold]
    valid_contours = sorted(valid_contours, key=cv2.contourArea, reverse=True)[:2]

    if not valid_contours:
        return _fallback_line_based_mask(garment_img)

    # 6. 创建边缘mask
    edge_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(edge_mask, valid_contours, -1, 255, 1)

    # 7. 洪水填充：从四边边缘向内填充，标记外部区域
    outside = np.zeros((h, w), dtype=np.uint8)

    for x in range(w):
        if edge_mask[0, x] == 0:
            cv2.floodFill(outside, None, (x, 0), 255)
        if edge_mask[h-1, x] == 0:
            cv2.floodFill(outside, None, (x, h-1), 255)

    for y in range(h):
        if edge_mask[y, 0] == 0:
            cv2.floodFill(outside, None, (0, y), 255)
        if edge_mask[y, w-1] == 0:
            cv2.floodFill(outside, None, (w-1, y), 255)

    # 8. 反转得到内部mask（基于边缘的洪水填充）
    mask = cv2.bitwise_not(outside)

    # ===== 8b. 底部恢复：V领开口导致洪水填充从领口灌入，使底部被掏空 =====
    # V领开口让外部洪水填充进入服装内部，标记为"外部"，导致底部只剩轮廓线
    # 策略：检测下半部分是否被掏空 → 用扫描线填充恢复
    if np.count_nonzero(mask) > h * w * 0.01:
        top_half_pct = np.count_nonzero(mask[:h//2, :]) / max(h//2 * w, 1)
        bot_half_pct = np.count_nonzero(mask[h//2:, :]) / max((h - h//2) * w, 1)
        # 底部密度严重低于顶部 = 被V领洪水填充掏空了
        if top_half_pct > 0.03 and (bot_half_pct < top_half_pct * 0.35 or bot_half_pct < 0.04):
            # 从外形轮廓推算下半部分的实心填充
            filled = mask.copy()
            # 扫描下半部分每行：取最左/最右mask像素 → 填充整行
            for y in range(h//2, h):
                cols = np.where(mask[y, :] > 0)[0]
                if len(cols) >= 2:
                    l, r = cols[0], cols[-1]
                    # 填充行内间隙(保留原本的中段开阔设计，只填稀疏行)
                    row_density = len(cols) / max(r - l, 1)
                    if row_density < 0.25:  # 该行严重稀疏(<25%密度) → 整行填充
                        filled[y, l:r + 1] = 255
                    elif row_density < 0.50:  # 中度稀疏 → 分段填充大间隙
                        # 找大间隙并填充
                        segs = []
                        s = cols[0]; p = cols[0]
                        for c in cols[1:]:
                            if c - p > 6:
                                segs.append((int(s), int(p)))
                                s = c; p = c
                            else:
                                p = c
                        segs.append((int(s), int(p)))
                        for i in range(len(segs) - 1):
                            gap_lo = segs[i][1] + 1
                            gap_hi = segs[i + 1][0]
                            if gap_hi - gap_lo > 0:
                                filled[y, gap_lo:gap_hi] = 255
            mask = filled

    mask_area = np.count_nonzero(mask)
    if mask_area < h * w * 0.05:
        return _fallback_line_based_mask(garment_img)

    # ===== 用凸包+形状分析约束mask，去除领口/右下角溢出 =====
    mask = _constrain_mask_by_shape(mask, garment_img)

    # 9. 最小闭运算连断线 + 最终腐蚀收缩回线条边界内
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3)), iterations=1)
    mask = cv2.erode(mask, np.ones((2, 2)), iterations=1)

    # 10. 极小羽化
    blurred = cv2.GaussianBlur(mask.astype(np.float32), (3, 3), sigmaX=0.5)
    blurred = np.clip(blurred, 0, 255).astype(np.uint8)
    blurred[blurred < 39] = 0

    return blurred


def _fill_vneck_with_silhouette(mask, silhouette):
    h,w=mask.shape
    total_px=h*w
    ma=np.count_nonzero(mask)
    if ma<total_px*0.003 or ma>total_px*0.65: return mask

    scan_bot=int(h*0.58)
    row_info=[]
    for y in range(scan_bot):
        cols=np.where(mask[y,:]>0)[0]
        if len(cols)<3:
            row_info.append((y,-1,-1,0,0,0,True)); continue
        l,r=int(cols[0]),int(cols[-1]); wid=r-l
        segs=[]; s=cols[0]; p=cols[0]
        for c in cols[1:]:
            if c-p>6: segs.append((s,p)); s=c; p=c
            else: p=c
        segs.append((s,p))
        ns=len(segs)
        mg=max((segs[i+1][0]-segs[i][1]) for i in range(len(segs)-1)) if ns>1 else 0
        row_info.append((y,l,r,wid,ns,mg,False))

    valid=[r for r in row_info if not r[6]]
    empty=[r for r in row_info if r[6]]
    multi=[r for r in valid if r[4]>=2]

    # ===== 模式一：顶部开裂V领（素描图V领） =====
    # 特征：大量2段行，间隙在图像中央区域
    # 原始mask: y=0整行→y=1分裂(first_two_seg_y<=2)
    # 处理后mask: rowfill已填顶部, 2段从y~200开始(first_two_seg_y>2)
    # 统一条件：2段行足够多 且 间隙居中
    first_two_seg_y = -1
    last_two_seg_y = -1
    n_two_seg = 0
    two_gap_sum = 0  # 2段行的平均间隙
    for r in multi:
        if r[4] == 2:
            if first_two_seg_y < 0: first_two_seg_y = r[0]
            last_two_seg_y = r[0]
            n_two_seg += 1
            two_gap_sum += r[5]  # max_gap

    avg_gap = two_gap_sum / max(n_two_seg, 1)
    # 条件A：原始特征(从y<=2开始分裂)
    is_top_split_strict = (first_two_seg_y <= 2 and n_two_seg >= 50)
    # 条件B：宽松特征(处理后mask)：2段行多+跨度大+平均间隙显著
    two_span = last_two_seg_y - first_two_seg_y if last_two_seg_y > 0 else 0
    is_top_split_relaxed = (
        n_two_seg >= 30 and
        two_span > h * 0.20 and
        avg_gap > w * 0.05
    )
    is_top_split_vneck = is_top_split_strict or is_top_split_relaxed

    # ===== 模式二：顶部空洞V领（旗袍类） =====
    # 旗袍特征值：空行=126, 首有效宽=8px(处理后)
    n_empty_top = len(empty)
    first_wid = valid[0][3] if valid else 0
    is_qipao_vneck = (
        50 <= n_empty_top <= 150 and
        3 <= first_wid <= 15
    )

    if not is_qipao_vneck and not is_top_split_vneck:
        return mask

    # ===== 分支处理 =====
    if is_top_split_vneck:
        # 顶部开裂V领：智能填充2段行间隙，保留V领自然开口
        # 核心改进：V领开口由服装设计本身造成，不应被填充
        #   - 间隙变化呈V型（宽→窄）= 真实V领开口 → 保留
        #   - 间隙宽度稳定/极小 = mask计算制品 → 填充
        # 用silhouette辅助验证：silhouette同位置也是2段=真实V领
        
        filled = mask.copy()
        max_gap_px = int(w * 0.45)  # 间隙超过45%图宽则不填（避免侧开叉被错误填充）
        
        # ===== Step 1: 收集所有2段行的间隙数据 =====
        gap_records = []  # [(y, gap_lo, gap_hi, gap_w, gap_center)]
        for y in range(1, scan_bot):
            cols = np.where(mask[y, :] > 0)[0]
            if len(cols) < 3:
                continue
            sg = []
            s = cols[0]; p = cols[0]
            for c in cols[1:]:
                if c - p > 6:
                    sg.append((int(s), int(p)))
                    s = c; p = c
                else:
                    p = c
            sg.append((int(s), int(p)))
            if len(sg) != 2:
                continue
            gap_lo = sg[0][1] + 1
            gap_hi = sg[1][0]
            gap_w = gap_hi - gap_lo
            if gap_w > 0 and gap_w <= max_gap_px:
                gap_c = (gap_lo + gap_hi) // 2
                gap_records.append((y, gap_lo, gap_hi, gap_w, gap_c))
        
        if not gap_records:
            return filled
        
        gap_ys = np.array([g[0] for g in gap_records])
        gap_ws = np.array([g[3] for g in gap_records], dtype=np.float64)
        first_gap_y = gap_ys[0]
        last_gap_y = gap_ys[-1]
        gap_span = last_gap_y - first_gap_y
        
        # ===== Step 2: 检测V领自然结束点 =====
        # V领特征：间隙从顶部开始，向下递减（V型收窄），到达V领底部后趋于稳定
        # 策略：
        #   a) 平滑间隙宽度，找趋势转折点
        #   b) silhouette验证：silhouette同位置2段=真实V领开口
        #   c) 保守上界：V领最小间隙位置 + 安全余量
        
        v_bottom_y = first_gap_y  # 默认从第一行就是V领底部（不填充）
        n_records = len(gap_records)
        
        if n_records > 5:
            # 平滑间隙宽度（移动平均）
            win = max(3, min(n_records // 8, 15))
            kernel_smooth = np.ones(win) / win
            ws_smooth = np.convolve(gap_ws, kernel_smooth, mode='same')
            
            # 策略a: 找间隙宽度由宽变窄的转折点（V领收口处）
            # 间隙最小值在前半段内查找（V领不会超过服装上半段）
            half_n = max(n_records // 2, 3)
            min_idx_half = int(np.argmin(ws_smooth[:half_n]))
            
            # 从最小间隙处向下找梯度趋于零的位置（间隙停止缩窄）
            gradients = np.diff(ws_smooth)
            settle_idx = min_idx_half
            for i in range(min_idx_half, min(len(gradients), n_records - 1)):
                if i < len(gradients):
                    # 梯度接近0或变正 = 间隙不再缩窄
                    if gradients[i] > -ws_smooth[i] * 0.015:
                        settle_idx = i + 1
                        break
                settle_idx = i + 1
            
            # 策略b: silhouette验证
            # 检查silhouette在间隙区域是否也是2段 → 真实V领开口
            sil_is_split = False
            check_y = gap_ys[min(min_idx_half, n_records - 1)]
            if silhouette is not None and np.count_nonzero(silhouette) > 0:
                sil_cols = np.where(silhouette[int(check_y), :] > 0)[0]
                if len(sil_cols) >= 3:
                    sil_sg = []
                    s_sil = sil_cols[0]; p_sil = sil_cols[0]
                    for c in sil_cols[1:]:
                        if c - p_sil > 6:
                            sil_sg.append((int(s_sil), int(p_sil)))
                            s_sil = c; p_sil = c
                        else:
                            p_sil = c
                    sil_sg.append((int(s_sil), int(p_sil)))
                    sil_is_split = (len(sil_sg) == 2)
            
            # 综合确定V领底部：
            # - 如果silhouette被确认是2段 → V领较大，V-bottom = settle_idx的y
            # - 如果silhouette是1段 → mask的2段是制品
            # - 安全余量：从min_idx再往下走10%的span
            if sil_is_split:
                # silhouette确认有V领，取settle点 + 5%安全余量
                v_bottom_idx = min(settle_idx + max(1, n_records // 20), n_records - 1)
                v_bottom_y = int(gap_ys[v_bottom_idx])
            else:
                # silhouette没确认V领 → mask的2段是制品，保守填充
                # 从30% span处开始填充
                v_bottom_idx = max(0, int(n_records * 0.30))
                v_bottom_y = int(gap_ys[v_bottom_idx])
            
            # 额外约束：V领底部不应超过60% scan_bot
            max_v_bottom = int(h * 0.30)
            v_bottom_y = min(v_bottom_y, max_v_bottom)
        
        # ===== Step 3: 只填充V领底部以下的间隙 =====
        # 额外安全措施：对于y > first_gap_y + 20% span以下的间隙，统一填充
        # （下方间隙大概率是制品而非V领开口）
        safe_fill_start = int(first_gap_y + gap_span * 0.35) if gap_span > 0 else v_bottom_y
        
        actual_fill_start = min(v_bottom_y, safe_fill_start)
        
        for g in gap_records:
            y, gap_lo, gap_hi, gap_w, gap_c = g
            if y >= actual_fill_start and gap_w <= max_gap_px:
                filled[y, gap_lo:gap_hi] = 255

        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        filled = cv2.morphologyEx(filled, cv2.MORPH_CLOSE, k, iterations=1)
        return filled

    # ===== 模式二：旗袍类处理 =====

    # 只用宽体行(w>15%图宽)做参考，避免窄行拖低插值结果
    wide=[r for r in valid if r[3]>w*0.15]
    if len(wide)<5: wide=valid  # 回退到全部
    ref_ys=[r[0] for r in wide]
    ref_l=[r[1] for r in wide]
    ref_r=[r[2] for r in wide]
    if len(ref_ys)<8: return mask

    all_ys=np.arange(scan_bot,dtype=np.float64)
    try:
        el_arr=np.interp(all_ys,ref_ys,ref_l)
        er_arr=np.interp(all_ys,ref_ys,ref_r)
    except ValueError: return mask

    # NaN填充：向上外推用第一个宽体值（不是最窄行的值）
    fl0,fr0=ref_l[0],ref_r[0]  # 第一个宽体行的边界
    ll,rr=fl0,fr0
    for i in range(len(all_ys)):
        if np.isnan(el_arr[i]): el_arr[i]=ll
        else: ll=el_arr[i]
        if np.isnan(er_arr[i]): er_arr[i]=rr
        else: rr=er_arr[i]

    fill_y1=min(scan_bot,max((r[0] for r in multi),default=scan_bot)+20)
    anchor=[r for r in valid if r[3]>w*0.18 and h*0.15<r[0]<h*0.50]
    if anchor: fill_y1=max(fill_y1,min(r[0] for r in anchor)+10)

    filled=mask.copy()
    for y in range(0,fill_y1):
        if y>=len(row_info): break
        ri=y; info=row_info[ri]
        al,ar,aw,ns,mg,ie=info[1],info[2],info[3],info[4],info[5],info[6]
        el=int(el_arr[ri]); er=int(er_arr[ri])
        if er<=el or el<0 or er>w: continue
        ew=er-el

        if ie or aw<ew*0.70:
            db=max(fill_y1-y,1); th=max(fill_y1,1)
            st=min(1.0,db/(th*0.55))
            tw=int(ew*st)
            if tw<12: continue
            mid=(el+er)//2; hw=tw//2
            filled[y,max(0,mid-hw):min(w,mid+hw+1)]=255
        elif ns>=2 and mg>=3:
            c=np.where(mask[y,:]>0)[0]
            sg=[]; s=c[0]; p=c[0]
            for x in c[1:]:
                if x-p>6: sg.append((s,p)); s=x; p=x
                else: p=x
            sg.append((s,p))
            if len(sg)<2: continue
            lo=sg[0][1]+1; hi=sg[-1][0]-1
            if hi>lo: filled[y,lo:hi]=255

    k=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3))
    filled=cv2.morphologyEx(filled,cv2.MORPH_CLOSE,k,iterations=1)
    return filled



def _constrain_mask_by_shape(mask, garment_img):
    """
    直接约束mask边界，去除领口上方和右下角溢出
    策略：保守裁剪可疑区域（只处理明确溢出的区域，不吃有效内容）
    """
    h, w = mask.shape
    result = mask.copy()

    # ========== 1. 裁剪顶部溢出区（领口溢出）==========
    # 顶部裁剪需要考虑服装实际是否有内容：
    # - 如果顶部10%区域的mask面积<总mask的2%，说明是溢出→裁剪
    # - 否则保留（可能有V领等有效内容）
    top_search = int(h * 0.12)
    top_area = np.count_nonzero(result[:top_search, :])
    total_area = np.count_nonzero(result)
    if total_area > 100:
        top_pct = top_area / max(total_area, 1)
        if top_pct < 0.03:
            # 顶部几乎没有内容→安全裁剪顶部12%
            top_cut = int(h * 0.12)
            result[:top_cut, :] = 0
    else:
        # 总面具太小时保守裁剪顶部15%
        top_cut = int(h * 0.15)
        result[:top_cut, :] = 0

    # ========== 2. 强制清除边缘像素的mask（防止边缘毛刺）==========
    margin = 4
    result[:margin, :] = 0       # 顶边
    result[-margin:, :] = 0      # 底边
    result[:, :margin] = 0       # 左边
    result[:, -margin:] = 0      # 右边

    # ========== 3. 右下角溢出处理（横线残留）==========
    # 改为保守策略：只在确认是溢出时才裁剪
    # 检查右下角区域的mask占比，如果占比过高说明是有效服装区域，不裁剪
    corner_w = int(w * 0.12)
    corner_h = int(h * 0.08)
    if corner_w > 5 and corner_h > 3:
        corner_region = result[-corner_h:, -corner_w:]
        corner_area = np.count_nonzero(corner_region)
        corner_pct = corner_area / max(total_area, 1)
        # 只有在该区域mask占比<5%时才认为是溢出并裁剪
        if corner_pct < 0.05:
            result[-corner_h:, -corner_w:] = 0

    # ========== 4. 清理孤立小区域 ==========
    n_lbl, lbls, stats, _ = cv2.connectedComponentsWithStats(result)
    if n_lbl > 1:
        main_lbl = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        result = (lbls == main_lbl).astype(np.uint8) * 255

    return result


def _fallback_line_based_mask(garment_img):
    """
    回退方法：当Canny检测失败时使用基于线条提取的mask方法
    适用于线稿图/素描模板
    """
    h, w = garment_img.shape[:2]
    gray = cv2.cvtColor((np.clip(garment_img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    
    # 提取线条（深色像素）
    stroke = (gray < 220).astype(np.uint8) * 255

    # 形态学闭运算连接断线（小核减少外扩）
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    stroke = cv2.morphologyEx(stroke, cv2.MORPH_CLOSE, kernel, iterations=1)
    stroke = cv2.dilate(stroke, np.ones((2, 2)), iterations=1)
    
    # 查找轮廓
    contours, _ = cv2.findContours(stroke, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        # 最终回退：返回全图中心区域
        mask = np.zeros((h, w), dtype=np.uint8)
        cx, cy = w // 2, h // 2
        mask[cy//4:cy+3*cy//4, cx//4:cx+3*cx//4] = 255
        return mask
    
    # 选择最大的轮廓（服装主体）
    areas = [cv2.contourArea(c) for c in contours]
    main_cnt = contours[np.argmax(areas)]
    
    # 填充轮廓
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(mask, [main_cnt], -1, 255, -1)
    
    # 用洪水填充填补内部空洞
    inv = cv2.bitwise_not(mask)
    ff = inv.copy()
    flood = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, flood, (0, 0), 255)
    holes = cv2.bitwise_not(ff)
    mask = cv2.bitwise_or(mask, holes)
    
    # 确保连通性（小核）
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3)), iterations=1)
    
    # 最终腐蚀收缩
    mask = cv2.erode(mask, np.ones((2, 2)), iterations=1)
    
    # ===== 兜底：V领素描等floodFill从领口灌入导致结果过少，改用二值化+连通域 =====
    # 关键改进：不选面积最大的组件（通常是背景通过V领开口连通），
    # 而是用中心感知策略选"最像服装"的组件
    if np.count_nonzero(mask) < h * w * 0.01:
        _, bin_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        kernel5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        bin_mask = cv2.morphologyEx(bin_mask, cv2.MORPH_CLOSE, kernel5)
        n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(bin_mask, connectivity=4)
        if n_labels > 1:
            cx, cy = w // 2, h // 2
            # 策略A：优先用图像中心像素所在的组件（服装应在画面中央）
            if labels[cy, cx] > 0:
                keep_id = int(labels[cy, cx])
            else:
                # 策略B：中心不在任何组件 → 选"最像服装"的组件
                # 服装特征：面积大、居中、不接触太多图像边缘
                # 背景特征：面积最大、接触全部4条边
                best_idx = 1
                best_score = -1.0
                for i in range(1, n_labels):
                    area = float(stats[i, cv2.CC_STAT_AREA])
                    x = int(stats[i, cv2.CC_STAT_LEFT])
                    y = int(stats[i, cv2.CC_STAT_TOP])
                    ww = int(stats[i, cv2.CC_STAT_WIDTH])
                    hh = int(stats[i, cv2.CC_STAT_HEIGHT])
                    # 接触边缘计数
                    touches = 0
                    if x <= 3: touches += 1
                    if y <= 3: touches += 1
                    if x + ww >= w - 3: touches += 1
                    if y + hh >= h - 3: touches += 1
                    # 接触3+条边 → 忽略（几乎一定是背景）
                    if touches >= 3:
                        continue
                    # 穿中心十字的加分
                    center_cross = (x <= cx <= x + ww) and (y <= cy <= y + hh)
                    near_center = abs((x + ww / 2.0) - cx) < 0.25 * w
                    # 高宽比不要太宽（服装一般是竖长型）
                    aspect_ok = hh > ww * 0.35 if ww > 0 else True
                    score = area * (1.5 if center_cross else 1.0) * \
                            (1.2 if near_center else 1.0) * \
                            (1.0 if aspect_ok else 0.3) / (1 + touches)
                    if score > best_score:
                        best_score = score
                        best_idx = i
                keep_id = best_idx
            # 安全校验：选出的组件面积不能太小
            if stats[keep_id, cv2.CC_STAT_AREA] > h * w * 0.02:
                mask = np.where(labels == keep_id, 255, 0).astype(np.uint8)
            else:
                # 面积太小则保留全部bin_mask（后续AND/base会限制）
                mask = bin_mask
        else:
            mask = bin_mask
    
    return mask


def _template_silhouette_mask(garment_img):
    h, w = garment_img.shape[:2]
    gray = cv2.cvtColor((np.clip(garment_img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)

    # 基于模板线条提取主体笔画
    stroke = (gray < 245).astype(np.uint8) * 255
    stroke = cv2.morphologyEx(stroke, cv2.MORPH_CLOSE, np.ones((2, 2)), iterations=1)
    stroke = cv2.dilate(stroke, np.ones((2, 2)), iterations=1)

    contours, _ = cv2.findContours(stroke, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return np.zeros((h, w), dtype=np.uint8)

    cx = w // 2
    areas = [cv2.contourArea(c) for c in contours]
    max_area = max(areas) if areas else 0.0

    out = np.zeros((h, w), dtype=np.uint8)
    picked = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        x, y, ww, hh = cv2.boundingRect(cnt)
        center_cross = (x < int(0.78 * w)) and (x + ww > int(0.22 * w))
        tall_enough = hh > int(0.18 * h)
        near_center_x = abs((x + ww / 2.0) - cx) < 0.34 * w
        if area >= max_area * 0.05 and center_cross and tall_enough and near_center_x:
            cv2.drawContours(out, [cnt], -1, 255, -1)
            picked += 1

    if picked == 0:
        main = max(contours, key=cv2.contourArea)
        cv2.drawContours(out, [main], -1, 255, -1)

    out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    return out


def _scanline_fill_from_stroke(garment_img):
    h, w = garment_img.shape[:2]
    gray = cv2.cvtColor((np.clip(garment_img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    stroke = (gray < 245).astype(np.uint8)
    stroke = cv2.morphologyEx((stroke * 255).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    stroke = (stroke > 0).astype(np.uint8)

    filled = np.zeros((h, w), dtype=np.uint8)
    for y in range(h):
        xs = np.where(stroke[y] > 0)[0]
        if xs.size < 2:
            continue
        x0 = int(np.percentile(xs, 8))
        x1 = int(np.percentile(xs, 92))
        if x1 - x0 < int(0.10 * w):
            continue
        filled[y, x0:x1 + 1] = 255

    filled = cv2.morphologyEx(filled, cv2.MORPH_CLOSE, np.ones((3, 3)), iterations=1)
    return filled


def _keep_center_body_component(mask_u8):
    h, w = mask_u8.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    if n <= 1:
        return mask_u8

    cx, cy = w // 2, h // 2
    if labels[cy, cx] > 0:
        keep_id = int(labels[cy, cx])
    else:
        keep_id = 1
        best_score = -1.0
        for i in range(1, n):
            area = float(stats[i, cv2.CC_STAT_AREA])
            x = int(stats[i, cv2.CC_STAT_LEFT])
            y = int(stats[i, cv2.CC_STAT_TOP])
            ww = int(stats[i, cv2.CC_STAT_WIDTH])
            hh = int(stats[i, cv2.CC_STAT_HEIGHT])
            center_cross = (x <= cx <= x + ww) and (y <= cy <= y + hh)
            near_center = abs((x + ww / 2.0) - cx) < 0.25 * w
            score = area * (1.6 if center_cross else 1.0) * (1.2 if near_center else 1.0)
            if score > best_score:
                best_score = score
                keep_id = i

    out = np.zeros_like(mask_u8)
    out[labels == keep_id] = 255
    out = cv2.morphologyEx(out, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    return out


def _prune_thin_bridges(mask_u8):
    opened = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8), iterations=1)
    opened = _keep_center_body_component(opened)
    if np.count_nonzero(opened) == 0:
        return mask_u8

    restored = cv2.dilate(opened, np.ones((3, 3), np.uint8), iterations=1)
    pruned = cv2.bitwise_and(mask_u8, restored)
    if np.count_nonzero(pruned) < 0.55 * np.count_nonzero(mask_u8):
        return mask_u8
    return pruned


def create_garment_space_mask_graph(garment_img, garment_name=None):
    """
    精确边界mask生成 — 防止边缘外溢的核心函数
    关键改进：
    1. 所有模式最终都用base_mask做AND约束（绝不超出基础轮廓）
    2. 去掉5x5大核闭运算，改用3x3+最终腐蚀收缩
    3. floodFill补洞只补小洞不扩展外部
    4. 全局最终腐蚀1px回缩到线条边界内
    """
    h, w = garment_img.shape[:2]

    base_mask_raw = create_garment_mask_v8(garment_img)
    base_mask = (base_mask_raw > 0.15).astype(np.uint8) * 255

    mode = STYLE_MASK_MODE.get(garment_name, "normal")

    silhouette = _template_silhouette_mask(garment_img)
    if np.count_nonzero(silhouette) == 0:
        silhouette = base_mask.copy()

    if mode == "loose":
        # loose款：以base为主，silhouette只做内部补洞不扩展外部
        mask = base_mask.copy()
        # 用silhouette的内部区域补充base中可能的缺口（只补不扩）
        sil_inner = cv2.erode(silhouette, np.ones((3, 3)), iterations=1)
        mask = cv2.bitwise_or(mask, cv2.bitwise_and(sil_inner, base_mask))
        # 行填充也限制在base范围内
        area_base = float(np.count_nonzero(base_mask))
        area_now = float(np.count_nonzero(mask))
        if area_base > 10 and area_now < 1.05 * area_base:
            rowfill = _scanline_fill_from_stroke(garment_img)
            rowfill = cv2.bitwise_and(rowfill, base_mask)  # 绝不出base范围
            if np.count_nonzero(rowfill) > 0:
                mask = cv2.bitwise_or(mask, rowfill)
    elif mode == "tight":
        mask = cv2.bitwise_and(base_mask, silhouette)
    else:
        # normal模式：AND约束，但加安全回退
        # 如果silhouette线条稀疏（如旗袍大面积空白），AND结果可能过小
        mask_and = cv2.bitwise_and(base_mask, silhouette)
        area_base = float(np.count_nonzero(base_mask))
        area_and = float(np.count_nonzero(mask_and))
        if area_base > 100 and area_and < area_base * 0.40:
            # AND结果太小 → 回退到base为主，用silhouette只做内部补洞
            mask = base_mask.copy()
            sil_inner = cv2.erode(silhouette, np.ones((3, 3)), iterations=1)
            mask = cv2.bitwise_or(mask, cv2.bitwise_and(sil_inner, base_mask))
        else:
            mask = mask_and

    # 只补小面积内部洞（<3%总面积），防止从缺口溢出到图像外围
    inv = cv2.bitwise_not(mask)
    ff = inv.copy()
    flood_pad = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, flood_pad, (0, 0), 255)
    holes_all = cv2.bitwise_not(ff)
    # 只保留小洞
    small_hole_area_limit = int(h * w * 0.03)
    n_lbl, lbls, stats, _ = cv2.connectedComponentsWithStats(holes_all)
    small_holes = np.zeros_like(holes_all)
    for i in range(1, n_lbl):
        if stats[i, cv2.CC_STAT_AREA] <= small_hole_area_limit:
            small_holes[lbls == i] = 255
    mask = cv2.bitwise_or(mask, small_holes)

    # 保留中心主体连通域
    mask = _keep_center_body_component(mask)

    if mode != "loose":
        mask = _prune_thin_bridges(mask)

    if mode == "tight":
        mask = cv2.erode(mask, np.ones((3, 3)), iterations=1)
        mask = cv2.dilate(mask, np.ones((3, 3)), iterations=1)
        mask = cv2.bitwise_and(mask, base_mask)

    # ===== 最关键的一步：全局最终AND约束回base_mask =====
    # 无论前面怎么处理，最终绝不允许超出base_mask边界
    mask = cv2.bitwise_and(mask, base_mask)

    # ===== 胸部+底部镂空恢复：确保服装区域内无空白 =====
    # V领开口导致洪水填充掏空下半部分+胸口 → 扫描线全面填充
    # 从h//3开始（覆盖V领以下的胸口区域），仅loose模式
    if mode == "loose" and np.count_nonzero(mask) > h * w * 0.005:
        top_third = np.count_nonzero(mask[:h//3, :]) / max(h//3 * w, 1)
        bot_two_third = np.count_nonzero(mask[h//3:, :]) / max((h - h//3) * w, 1)
        last3_empty = sum(1 for y in range(h-3, h) if np.count_nonzero(mask[y,:]) < 3)
        bottom_missing = last3_empty >= 2
        # 触发条件：下半区密度明显低于上半 OR 最后几行缺失
        underfilled = (top_third > 0.02 and bot_two_third < top_third * 0.60) or bottom_missing
        # 或者：任意行有>15px空隙
        if not underfilled:
            for y in range(h//3, h):
                nz = np.where(mask[y,:] > 0)[0]
                if len(nz) >= 2 and (nz[-1]-nz[0]) - len(nz) > 15:
                    underfilled = True
                    break
        
        if underfilled:
            filled = mask.copy()
            # 从V领以下(h//3)到底部全覆盖，只填mask有像素的行(不外推)
            for y in range(h//3, h):
                m_cols = np.where(mask[y, :] > 0)[0]
                if len(m_cols) < 2:
                    continue
                l, r = m_cols[0], m_cols[-1]
                if r - l < 3:
                    continue
                filled[y, l:r + 1] = 255
            mask = filled

    # 轻微闭运算连断线（3x3，不用5x5）
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3)), iterations=1)

    # ===== 对称性修复：解决Canny检测不均匀导致单侧mask问题 =====
    # 在最终约束后检查，如果左右不对称则用镜像补充
    left_area = np.count_nonzero(mask[:, :w//2])
    right_area = np.count_nonzero(mask[:, w//2:])
    total_lr = left_area + right_area
    if total_lr > 200:
        ratio = min(left_area, right_area) / max(left_area, right_area) if max(left_area, right_area) > 0 else 0
        if ratio < 0.72:
            mirror = cv2.flip(mask, 1)
            mask = cv2.bitwise_or(mask, mirror)
            mask = _keep_center_body_component(mask)

    # 线条邻近性约束已禁用：对旗袍等大面积空白服装误切严重
    # mask = _trim_mask_by_line_proximity(mask, garment_img)

    # loose模式trim已禁用，避免误伤有效内容

    # ===== V领缺口修复：用silhouette补充胸口被floodFill/AND误切的区域 =====
    mask = _fill_vneck_with_silhouette(mask, silhouette)

    # ===== 最终腐蚀：收缩回线条边界内（2x2核减小边缘损失）=====
    mask = cv2.erode(mask, np.ones((2, 2)), iterations=1)

    # ===== 边缘恢复：用base_mask外扩约束，收回腐蚀损失的1-2px =====
    # 管道累积多次腐蚀，左右边缘可能比base_mask窄1-3px
    # 用3x3对称膨胀反补，但限制在base_mask外扩范围内防止溢出
    mask_dilated = cv2.dilate(mask, np.ones((3, 3)), iterations=1)
    base_expanded = cv2.dilate(base_mask, np.ones((3, 3)), iterations=1)
    mask_dilated = cv2.bitwise_and(mask_dilated, base_expanded)
    mask = cv2.bitwise_or(mask, mask_dilated)

    # 生成软mask
    soft = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (3, 3), sigmaX=0.5)
    soft = np.clip(soft, 0.0, 1.0)

    # ===== 关键：用硬二值边界截断软mask =====
    # GaussianBlur必然产生边缘渗透（这是blur的数学特性）
    # 解决方案：将软mask乘以腐蚀后的二值mask，彻底切断外部溢出
    hard_boundary = (mask > 128).astype(np.float32)
    soft = soft * hard_boundary

    return soft[:, :, np.newaxis].astype(np.float32), (mask > 0).astype(np.uint8)







def _trim_mask_by_line_proximity(mask_u8, garment_img):
    """
    用线条邻近性约束裁剪mask边缘溢出：
    只切除mask边缘中离笔画远的像素（真正的溢出），
    保留内部核心区（即使离笔画远也不切，那是正常的空白区域）。
    
    关键改进：用mask自身距离变换区分"边界薄层"和"内部核心"，
    解决旗袍等大面积空白服装被误切的问题。
    """
    h, w = mask_u8.shape
    if np.count_nonzero(mask_u8) == 0:
        return mask_u8

    gray = cv2.cvtColor((np.clip(garment_img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    strokes = (gray < 230).astype(np.uint8)

    if np.count_nonzero(strokes) == 0:
        return mask_u8

    # 到最近笔画的距离
    dist_to_stroke = cv2.distanceTransform(255 - strokes, cv2.DIST_L2, 5)

    # mask自身的距离变换（从mask边界向内递增）
    dist_from_edge = cv2.distanceTransform(mask_u8, cv2.DIST_L2, 5)

    # 距离阈值
    dist_limit = max(4, int(min(h, w) * 0.025))

    # 核心改进：只切"在mask边缘附近(距边界<12px)" 且 "离笔画远" 的像素
    # 内部核心（距边界>=12px）即使离笔画远也保留——那是正常空白区域
    edge_band = dist_from_edge < 12  # 边界带~12px内
    far_from_strokes = dist_to_stroke > dist_limit

    trimmed = mask_u8.copy()
    # 只清除同时满足两个条件的：在边界带内 AND 离笔画远 → 这才是真正的溢出
    trimmed[edge_band & far_from_strokes & (trimmed > 0)] = 0

    # 安全检查：不裁超过20%
    area_before = np.count_nonzero(mask_u8)
    area_after = np.count_nonzero(trimmed)
    if area_before > 100 and area_after < area_before * 0.80:
        return mask_u8

    return trimmed


def template_line_alpha(garment_img, mask_binary):
    alpha = extract_garment_lines(garment_img).squeeze().astype(np.float32)
    alpha = cv2.GaussianBlur(alpha, (0, 0), sigmaX=0.5)
    alpha = alpha * mask_binary.astype(np.float32)
    return np.clip(alpha, 0.0, 1.0)[:, :, np.newaxis]


def dense_subject_warp(subject_img, mask_binary, view="front"):
    h, w = mask_binary.shape
    out = np.ones((h, w, 3), dtype=np.float32) * 0.97

    ys, xs = np.where(mask_binary > 0)
    if len(xs) == 0:
        return out

    min_x, max_x = float(xs.min()), float(xs.max())
    min_y, max_y = float(ys.min()), float(ys.max())
    box_w = max(1.0, max_x - min_x)
    box_h = max(1.0, max_y - min_y)

    sh, sw, _ = subject_img.shape
    grid_x, grid_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))

    u = np.clip((grid_x - min_x) / box_w, 0.0, 1.0)
    v = np.clip((grid_y - min_y) / box_h, 0.0, 1.0)

    shoulder_t = np.clip(v / 0.30, 0.0, 1.0)
    shoulder_scale = 0.68 + 0.32 * shoulder_t
    u = np.clip(0.5 + (u - 0.5) * shoulder_scale, 0.0, 1.0)

    if view == "back":
        u = 1.0 - u

    map_x = (u * (sw - 1)).astype(np.float32)
    map_y = ((0.04 + 0.92 * v) * (sh - 1)).astype(np.float32)
    warped = cv2.remap(subject_img.astype(np.float32), map_x, map_y, interpolation=cv2.INTER_LINEAR)
    keep = mask_binary > 0
    out[keep] = warped[keep]
    return np.clip(out, 0, 1)


def pool_dense_to_graph(dense_img, mask_binary, rows=32, cols=24):
    h, w = mask_binary.shape
    cell_h = max(1, h // rows)
    cell_w = max(1, w // cols)

    nodes = np.zeros((rows, cols, 3), dtype=np.float32)
    valid = np.zeros((rows, cols), dtype=np.uint8)

    for r in range(rows):
        y0 = r * cell_h
        y1 = h if r == rows - 1 else min(h, (r + 1) * cell_h)
        for c in range(cols):
            x0 = c * cell_w
            x1 = w if c == cols - 1 else min(w, (c + 1) * cell_w)
            m = mask_binary[y0:y1, x0:x1] > 0
            if np.mean(m) < 0.04:
                continue
            patch = dense_img[y0:y1, x0:x1]
            nodes[r, c] = patch[m].mean(axis=0)
            valid[r, c] = 1

    return nodes, valid


def dual_view_graph_propagation(front_seed, back_seed, valid, steps=50):
    front = front_seed.copy()
    back = back_seed.copy()

    if np.any(valid):
        g_front = front_seed[valid > 0].mean(axis=0)
        g_back = back_seed[valid > 0].mean(axis=0)
        global_mean = 0.5 * (g_front + g_back)
    else:
        global_mean = np.array([0.95, 0.95, 0.95], dtype=np.float32)

    rows, cols, _ = front.shape

    for _ in range(steps):
        new_front = front.copy()
        new_back = back.copy()

        for r in range(rows):
            for c in range(cols):
                if valid[r, c] == 0:
                    continue

                neigh_f = []
                neigh_b = []
                for dr, dc, w in (
                    (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
                    (-1, -1, 0.65), (-1, 1, 0.65), (1, -1, 0.65), (1, 1, 0.65),
                ):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < rows and 0 <= cc < cols and valid[rr, cc] == 1:
                        neigh_f.append((front[rr, cc], w))
                        neigh_b.append((back[rr, cc], w))

                if neigh_f:
                    sum_w = float(sum(w for _, w in neigh_f))
                    f_avg = np.zeros(3, dtype=np.float32)
                    b_avg = np.zeros(3, dtype=np.float32)
                    for val, ww in neigh_f:
                        f_avg += val * (ww / sum_w)
                    for val, ww in neigh_b:
                        b_avg += val * (ww / sum_w)
                else:
                    f_avg = front[r, c]
                    b_avg = back[r, c]

                mirror_c = cols - 1 - c
                cross_from_back = back[r, mirror_c]
                cross_from_front = front[r, mirror_c]

                new_front[r, c] = (
                    0.62 * front_seed[r, c]
                    + 0.24 * f_avg
                    + 0.10 * cross_from_back
                    + 0.04 * global_mean
                )
                new_back[r, c] = (
                    0.62 * back_seed[r, c]
                    + 0.24 * b_avg
                    + 0.10 * cross_from_front
                    + 0.04 * global_mean
                )

        front = new_front
        back = new_back

    return front, back


def rasterize_graph(nodes, valid, seed_dense, mask_soft, mask_binary):
    h, w = mask_binary.shape

    dense_graph = np.zeros((h, w, 3), dtype=np.float32)
    for ch in range(3):
        dense_graph[:, :, ch] = cv2.resize(nodes[:, :, ch], (w, h), interpolation=cv2.INTER_CUBIC)

    valid_dense = cv2.resize(valid.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
    valid_dense = cv2.GaussianBlur(valid_dense, (0, 0), sigmaX=1.5)
    valid_dense = np.clip(valid_dense, 0.0, 1.0)[:, :, np.newaxis]

    # 在mask内部：有图节点的区域用图+seed混合，无图节点的区域用seed填充
    inside = (mask_binary > 0)
    merged = seed_dense.copy()
    blended = 0.55 * seed_dense + 0.45 * dense_graph
    merged[inside] = (valid_dense * blended + (1.0 - valid_dense) * seed_dense)[inside]

    merged_u8 = np.clip(merged * 255.0, 0, 255).astype(np.uint8)
    filtered_u8 = merged_u8.copy()
    for ch in range(3):
        filtered_u8[:, :, ch] = cv2.bilateralFilter(merged_u8[:, :, ch], d=5, sigmaColor=22, sigmaSpace=14)
    filtered = filtered_u8.astype(np.float32) / 255.0

    # 仅在服装内部核心区使用平滑，避免白背景向边缘渗透
    inside_core = cv2.erode(mask_binary.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=1) > 0
    merged[inside_core] = filtered[inside_core]

    # mask外部保持原底色（接近白色）
    outside = ~inside
    bg = np.array([0.97, 0.97, 0.97], dtype=np.float32)
    merged[outside] = bg
    # 不再在边缘向白底做alpha混合，防止白色缺口

    # ===== 关键：应用mask_soft做软边界 =====
    soft_alpha = mask_soft.squeeze()
    if soft_alpha.ndim == 2:
        soft_alpha = soft_alpha[:, :, np.newaxis]
    merged = merged * soft_alpha + bg * (1.0 - soft_alpha)

    return np.clip(merged, 0, 1)


def clean_garment_lines(garment_lines, mask_binary, view="front"):
    lines = garment_lines.squeeze().astype(np.float32)
    line_bin = (lines > 0.03).astype(np.uint8)

    h, w = mask_binary.shape
    kernel = np.ones((5, 5), np.uint8)
    near_mask = cv2.dilate(mask_binary.astype(np.uint8), kernel, iterations=3)

    # 领口/肩部保留带：允许mask上方一段区域保留线稿，避免领子消失
    collar_roi = np.zeros((h, w), dtype=np.uint8)
    ys, xs = np.where(mask_binary > 0)
    if len(xs) > 0:
        y_top = int(ys.min())
        x0 = max(0, int(xs.min()) - max(4, int(0.03 * w)))
        x1 = min(w, int(xs.max()) + max(5, int(0.03 * w)) + 1)
        y0 = max(0, y_top - max(6, int(0.10 * h)))
        y1 = min(h, y_top + max(8, int(0.16 * h)))
        collar_roi[y0:y1, x0:x1] = 1

    allow = (near_mask > 0) | (collar_roi > 0)
    cleaned = ((line_bin > 0) & allow).astype(np.uint8)

    cleaned = cv2.morphologyEx(cleaned * 255, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    cleaned = cv2.GaussianBlur(cleaned.astype(np.float32) / 255.0, (0, 0), sigmaX=0.45)

    # 前后差异：背面抑制前门襟/前领等中轴细节，避免前后几乎一致
    ys, xs = np.where(mask_binary > 0)
    if len(xs) > 0:
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        cx = int(0.5 * (x0 + x1))
        bw = max(1, x1 - x0 + 1)
        bh = max(1, y1 - y0 + 1)

        if view == "back":
            # 抑制中间门襟样式线条
            c_half = max(2, int(0.06 * bw))
            yy0 = y0 + int(0.14 * bh)
            yy1 = y1 - int(0.05 * bh)
            cleaned[yy0:yy1, max(0, cx - c_half):min(w, cx + c_half + 1)] *= 0.30

            # 抑制上胸口中间区域（前领口细节在背面通常较弱）
            neck_half = max(3, int(0.18 * bw))
            ny0 = y0
            ny1 = min(h, y0 + int(0.22 * bh))
            cleaned[ny0:ny1, max(0, cx - neck_half):min(w, cx + neck_half + 1)] *= 0.45
        else:
            # 正面略强调中轴细节，但保持自然
            c_half = max(2, int(0.04 * bw))
            yy0 = y0 + int(0.10 * bh)
            yy1 = y1 - int(0.10 * bh)
            cleaned[yy0:yy1, max(0, cx - c_half):min(w, cx + c_half + 1)] *= 1.08

    cleaned = np.clip(cleaned, 0.0, 1.0)
    return cleaned[:, :, np.newaxis]


def map_front_back_graph(subject_img, garment_img, garment_lines, garment_name=None, rows=32, cols=24):
    mask_soft, mask_binary = create_garment_space_mask_graph(garment_img, garment_name=garment_name)
    lines_front = template_line_alpha(garment_img, mask_binary)
    lines_back = template_line_alpha(garment_img, mask_binary)

    front_seed_dense = dense_subject_warp(subject_img, mask_binary, view="front")
    back_seed_dense = dense_subject_warp(subject_img, mask_binary, view="back")

    front_seed_nodes, valid_f = pool_dense_to_graph(front_seed_dense, mask_binary, rows=rows, cols=cols)
    back_seed_nodes, valid_b = pool_dense_to_graph(back_seed_dense, mask_binary, rows=rows, cols=cols)
    valid = ((valid_f > 0) | (valid_b > 0)).astype(np.uint8)

    front_nodes, back_nodes = dual_view_graph_propagation(front_seed_nodes, back_seed_nodes, valid, steps=50)

    front_graph = rasterize_graph(front_nodes, valid, front_seed_dense, mask_soft, mask_binary)
    back_graph = rasterize_graph(back_nodes, valid, back_seed_dense, mask_soft, mask_binary)

    line_color = np.array([0.25, 0.25, 0.25], dtype=np.float32)
    alpha_front = np.clip(lines_front * 0.65, 0.0, 1.0)
    alpha_back = np.clip(lines_back * 0.60, 0.0, 1.0)
    front_graph = front_graph * (1 - alpha_front) + alpha_front * line_color.reshape(1, 1, 3)
    back_graph = back_graph * (1 - alpha_back) + alpha_back * line_color.reshape(1, 1, 3)

    # 最终硬约束：确保绝不越出服装区域
    keep = mask_binary > 0
    bg = np.array([0.97, 0.97, 0.97], dtype=np.float32)
    front_graph[~keep] = bg
    back_graph[~keep] = bg

    return np.clip(front_graph, 0, 1), np.clip(back_graph, 0, 1)


def build_subject_image(painting_img):
    x, y, w, h = map(int, extract_artifact_subject_v5(painting_img))
    x = max(0, x)
    y = max(0, y)
    w = max(1, w)
    h = max(1, h)
    x2 = min(painting_img.shape[1], x + w)
    y2 = min(painting_img.shape[0], y + h)
    subject = painting_img[y:y2, x:x2]
    if subject.size == 0:
        return painting_img
    return subject


def main():
    # 选择多幅画作进行测试
    num_paintings = 5
    painting_paths = pick_multiple_paintings(n=num_paintings)
    garment_paths = list_all_garments()

    out_root = BASE_DIR / "models" / f"graph_front_back_{num_paintings}paintings"
    out_root.mkdir(parents=True, exist_ok=True)

    all_results = []
    
    for p_idx, painting_path in enumerate(painting_paths, start=1):
        print(f"\n{'='*50}")
        print(f"Processing painting {p_idx}/{num_paintings}: {painting_path.name}")
        
        painting = load_image(str(painting_path), size=None)
        if painting is None:
            print(f"Skip load failed: {painting_path}")
            continue
        subject_img = build_subject_image(painting)

        painting_rows = []
        for idx, garment_path in enumerate(garment_paths, start=1):
            garment = load_image(str(garment_path), size=256)
            if garment is None:
                print(f"Skip load failed: {garment_path}")
                continue

            garment_lines = extract_garment_lines(garment)

            front_graph, back_graph = map_front_back_graph(
                subject_img,
                garment,
                garment_lines,
                garment_name=garment_path.name,
                rows=32,
                cols=24,
            )

            painting_rows.append((garment_path.name, front_graph, back_graph))
            print(f"  Done {idx}/{len(garment_paths)}: {garment_path.name}")

        all_results.append({
            'painting_name': painting_path.name,
            'painting_img': painting,
            'rows': painting_rows
        })

    # 生成多画作总览图
    print(f"\n{'='*50}")
    print("Generating multi-painting overview...")
    
    if not all_results:
        raise RuntimeError("No results generated")
    
    num_styles = len(all_results[0]['rows'])
    
    # 每幅画生成一个子图
    fig, axes = plt.subplots(len(all_results), num_styles * 2 + 2, figsize=(3 * (num_styles * 2 + 2), 4 * len(all_results)))
    
    if len(all_results) == 1:
        axes = axes.reshape(1, -1)
    
    for p_idx, result in enumerate(all_results):
        painting_img = result['painting_img']
        painting_256 = cv2.resize(painting_img, (256, 256), interpolation=cv2.INTER_AREA)
        
        # 显示画作预览
        axes[p_idx, 0].imshow(painting_256)
        axes[p_idx, 0].set_title(f"画作 {p_idx+1}\n{result['painting_name'][:15]}...", fontsize=8)
        axes[p_idx, 0].axis('off')
        
        # 显示正面总览（第一件服装）
        if result['rows']:
            axes[p_idx, 1].imshow(result['rows'][0][1])  # 第一件服装正面
            axes[p_idx, 1].set_title("正面示例", fontsize=8)
            axes[p_idx, 1].axis('off')
        
        # 显示所有款式结果
        for style_idx, (_, front, back) in enumerate(result['rows'][:num_styles]):
            col = 2 + style_idx * 2
            if col < axes.shape[1]:
                axes[p_idx, col].imshow(front)
                axes[p_idx, col].set_title(f"款式{style_idx+1}正面", fontsize=7)
                axes[p_idx, col].axis('off')
            
            col_back = 2 + style_idx * 2 + 1
            if col_back < axes.shape[1]:
                axes[p_idx, col_back].imshow(back)
                axes[p_idx, col_back].set_title(f"款式{style_idx+1}背面", fontsize=7)
                axes[p_idx, col_back].axis('off')
    
    fig.suptitle(f"多画作图表示学习映射结果 ({num_paintings}幅画 x {num_styles}种款式)", fontsize=14, y=0.995)
    plt.tight_layout()
    
    overview_path = out_root / f"multi_painting_graph_overview.png"
    plt.savefig(overview_path, dpi=150, bbox_inches="tight")
    plt.close()

    # 保存单独的画作预览
    for p_idx, result in enumerate(all_results, start=1):
        painting_img = result['painting_img']
        painting_256 = cv2.resize(painting_img, (256, 256), interpolation=cv2.INTER_AREA)
        painting_preview_path = out_root / f"painting_{p_idx:02d}_{result['painting_name']}"
        cv2.imwrite(str(painting_preview_path), cv2.cvtColor((painting_256 * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
    
    # 打印总结
    print(f"\n{'='*50}")
    print("测试完成!")
    print(f"画作数量: {len(all_results)}")
    print(f"服装款式: {num_styles}")
    print(f"输出目录: {out_root}")
    print(f"总览图: {overview_path}")
    
    # 列出每幅画的详细信息
    for p_idx, result in enumerate(all_results, start=1):
        print(f"\n画作 {p_idx}: {result['painting_name']}")
        print(f"  - 处理款式数: {len(result['rows'])}")


if __name__ == "__main__":
    main()
