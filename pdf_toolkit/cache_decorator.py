"""
把工具处理一个pdf的结果缓存入指定文件夹中，若要处理已缓存的文件，直接从指定文件夹中读取结果返回。用于测试
"""
import os
import json
import pickle
import hashlib
import functools
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar, cast

F = TypeVar('F', bound=Callable[..., Any])

def save_tool_results(pdf_name_without_suff, output_folder,extracted_tables):
    output_pdf_dir = os.path.join(output_folder, pdf_name_without_suff)
    os.makedirs(output_pdf_dir, exist_ok=True)
    for i, item in enumerate(extracted_tables):
        output_file = os.path.join(output_pdf_dir, f"{i+1}.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=4)

def load_tool_results(output_folder: str) -> Any:
    """
    从指定文件夹中读取所有缓存的json文件，并按编号顺序返回一个列表
    """
    files = sorted(os.listdir(output_folder), key=lambda x: int(os.path.splitext(x)[0]))
    results = []
    for filename in files:
        if filename.endswith(".json"):
            file_path = os.path.join(output_folder, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                results.append(data)
    return results

def cache_to_folder(tool_name: str, folder_path: str) -> Callable[[F], F]:
    """
    装饰器工厂，创建一个缓存装饰器，将函数的输入输出缓存到指定文件夹

    参数:
        tool_name: 工具名，用于在缓存根目录下区分不同工具的结果
        folder_path: 缓存文件夹的根路径

    返回:
        装饰器函数
    """
    output_tool_dir = os.path.join(folder_path, tool_name)
    # 确保缓存文件夹存在
    os.makedirs(output_tool_dir, exist_ok=True)
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 将输入参数转换为可哈希的格式
            pdf_path = args[0]
            name_without_suff = os.path.basename(pdf_path).split(".")[0]
            output_pdf_dir = os.path.join(output_tool_dir, name_without_suff)
            
            # 检测output_pdf_dir是否存在且不为空
            if os.path.exists(output_pdf_dir) and len(os.listdir(output_pdf_dir)) > 0:
                # 若存在，从output_pdf_dir中读取缓存
                result = load_tool_results(output_pdf_dir)
                return result
            else:
                # 若不存在，执行函数并保存结果
                result = func(*args, **kwargs)
                save_tool_results(name_without_suff, output_tool_dir, result)
                return result
        
        return cast(F, wrapper)
    
    return decorator