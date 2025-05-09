"""
把多种工具给出的结果进行对齐。
例如：
tool1处理一个pdf文件返回表格[a1,a2,a3]
tool2处理该pdf文件返回表格[b1,b2,b3,b4]
最终对齐为[[a1,b2], [a2,b3], [a3,b4]],同一个二元组内是同一个表格的两种工具提取结果
"""
from typing import Callable, List, Dict, Any, Tuple
import math

class combinedTool:
    def __init__(self,*tools: Callable):
        self.tools = tools
    def __call__(self, pdf_path):
        results = [ tool(pdf_path) for tool in self.tools ]
        matched_results = match_tables(results)
        return matched_results


def _iou(b1: List[float], b2: List[float]) -> float:
    left   = max(b1[0], b2[0])
    top    = max(b1[1], b2[1])
    right  = min(b1[2], b2[2])
    bottom = min(b1[3], b2[3])

    if right <= left or bottom <= top:
        return 0.0

    inter_area = (right - left) * (bottom - top)
    area1      = (b1[2] - b1[0]) * (b1[3] - b1[1])
    area2      = (b2[2] - b2[0]) * (b2[3] - b2[1])
    union_area = area1 + area2 - inter_area
    return inter_area / union_area

def match_tables(
    tools_tables: List[List[Dict[str, Any]]],
    iou_threshold: float = 0.70,
) -> List[List[Dict[str, Any]]]:
    """
    将多个工具检测到的表格对齐，并只保留被“超过半数”工具检测到的表格。
    返回值中的各组按 (page_idx, top, left) 升序排序。
    """
    n_tools = len(tools_tables)
    majority = n_tools // 2 + 1      # 严格超过半数

    groups: List[List[Any]] = []     # 每组对应一个真实表格
    reps:   List[Tuple[int, List[float]]] = []  # 代表框 (page_idx, bbox) 与 groups 同步

    for t_idx, tables in enumerate(tools_tables):
        for tbl in tables:
            page = tbl["page_idx"]
            bbox = tbl["bbox"]

            assigned = False
            for g_idx, (g_page, g_bbox) in enumerate(reps):
                if page == g_page and _iou(bbox, g_bbox) >= iou_threshold:
                    groups[g_idx][t_idx] = tbl
                    assigned = True
                    break

            if not assigned:
                new_group = [None] * n_tools
                new_group[t_idx] = tbl
                groups.append(new_group)
                reps.append((page, bbox))

    # 过滤掉低于“超过半数”票数的组
    kept = [
        (grp, reps[i])
        for i, grp in enumerate(groups)
        if sum(tbl is not None for tbl in grp) >= majority
    ]

    otn = ",".join([str(len(tt)) for tt in tools_tables])
    print(f"原始表格数为：{otn}\n保留了：{len(kept)}\n保留率为：{len(kept)/len(reps)*100}%")

    # 按 (page_idx, bbox_top, bbox_left) 排序
    kept.sort(key=lambda item: (int(item[1][0]), item[1][1][1], item[1][1][0]))

    # 丢掉代表框，只返回表格组
    return [grp for grp, _ in kept]