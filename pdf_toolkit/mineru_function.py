from typing import List, Dict, Any
import os
import json
from .cache_decorator import cache_to_folder
import tempfile
import sys
sys.path.append('/Users/qimai/Desktop/workspace/deepResearch/all_lib/MinerU')
from magic_pdf.data.data_reader_writer import FileBasedDataReader, FileBasedDataWriter
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod


@cache_to_folder("minerU","/Users/qimai/Desktop/workspace/deepResearch/pdf_extract_agent/single_table_output/tool")
def mineru_extractor(pdf_path: str) -> List[Dict[str, Any]]:
    r"""
    Extract tables from a PDF file using mineru library.

    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries where each dictionary represents a table.
            Each dictionary contains the following keys:
                - 'table_body' (str): The content of the table.
                - 'table_caption' (str): The caption of the table.
                - 'table_footnote' (str): The footnote of the table.
                - 'page_idx' (str): The page index where the table was found.

    """

    # sys.path.append('/Users/qimai/Desktop/workspace/deepResearch/all_lib/MinerU')
    # 读取PDF文件内容
    reader = FileBasedDataReader("")
    pdf_bytes = reader.read(pdf_path)
    
    # 创建临时文件夹来存储图片
    with tempfile.TemporaryDirectory() as temp_dir:
        local_image_dir = temp_dir
        image_dir = str(os.path.basename(local_image_dir))
        image_writer = FileBasedDataWriter(local_image_dir)

        # 创建数据集实例
        ds = PymuDocDataset(pdf_bytes)
        
        # 分类PDF解析方法
        parse_method = ds.classify()
        
        # 应用解析模型
        if parse_method == SupportedPdfParseMethod.OCR:
            infer_result = ds.apply(doc_analyze, ocr=True)
            pipe_result = infer_result.pipe_ocr_mode(image_writer)
        else:
            infer_result = ds.apply(doc_analyze, ocr=False)
            pipe_result = infer_result.pipe_txt_mode(image_writer)
        
        # 获取内容列表
        content_list_content = pipe_result.get_content_list(image_dir)
        
        bbox_list = []
        for page in pipe_result._pipe_res['pdf_info']:
            for table in page['tables']:
                bbox_list.append(table['bbox'])

        # 提取表格内容
        i = 0
        extracted_tables = []
        for item in content_list_content:
            if item.get("type") == "table":
                table_entry = {
                    "table_body": item.get("table_body", ""),
                    "table_caption": "\n".join(item.get("table_caption", [])),
                    "table_footnote": "\n".join(item.get("table_footnote", [])),
                    "page_idx": str(item.get("page_idx", "")),
                    "bbox": bbox_list[i]
                }
                i += 1
                extracted_tables.append(table_entry)

        # name_without_suff = os.path.basename(pdf_path).split(".")[0]
        # save_tool_results(name_without_suff,"/Users/qimai/Desktop/workspace/deepResearch/pdf_extract_agent/tool_output/mineru",extracted_tables)
        
        return extracted_tables
    
# 示例用法
if __name__ == "__main__":
    pdf_path = '/Users/qimai/Desktop/workspace/deepResearch/test-pdf/english/DeepSeek_onlyTable.pdf'  # 替换为你的PDF文件路径
    tables = mineru_extractor(pdf_path)
    
    # 将表格内容保存到JSON文件
    output_dir = "output"
    import json
    import os
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "mineru_extracted_tables.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(tables, f, ensure_ascii=False, indent=4)

    print(f"Extracted tables have been saved to {output_file}")