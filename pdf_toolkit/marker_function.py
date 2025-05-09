from typing import List, Dict, Any
import logging
import os
import json
from pathlib import Path
from marker.converters.table import TableConverter
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.output import text_from_rendered
from marker.renderers.json import JSONRenderer

from marker.renderers.html import HTMLOutput
from marker.renderers.json import JSONOutput, JSONBlockOutput
from marker.renderers.markdown import MarkdownOutput
from marker.schema.blocks import BlockOutput
from marker.schema import BlockTypes
from .cache_decorator import cache_to_folder

@cache_to_folder("marker","/Users/qimai/Desktop/workspace/deepResearch/pdf_extract_agent/single_table_output/tool")
def marker_extractor(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extract tables from a PDF file using docling library.

    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries where each dictionary represents a table.
            Each dictionary contains the following keys:
                - 'table_body' (str): The content of the table in HTML format.
                - 'table_caption' (str): The caption of the table.
                - 'table_footnote' (str): The footnote of the table.
                - 'page_idx' (str): The page index where the table was found.
    """    
    extracted_tables = []
    # 使用marker提取表格
    

    config = {
        "output_format": "json",
        # "use_llm": True,
        "disable_image_extraction": True
    }
    config_parser = ConfigParser(config)

    converter = TableConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service()
    )
    rendered = converter(pdf_path)

    def find_all_table(rendered):
        if rendered.block_type=="Table":
            return [rendered]
        table_list = []
        if rendered.children is not None:
            for block in rendered.children:
                table_list += find_all_table(block)
        return table_list
    
    for block in find_all_table(rendered):
        table_content = block.html
        page_idx = block.id.split('/')[2]
        table_entry = {
            "table_body": table_content,
            "table_caption": "",
            "table_footnote": "",
            "page_idx": page_idx,
            "bbox": block.bbox
        }
        extracted_tables.append(table_entry)

    # only for test
    # name_without_suff = os.path.basename(pdf_path).split(".")[0]
    # save_tool_results(name_without_suff,"/Users/qimai/Desktop/workspace/deepResearch/pdf_extract_agent/tool_output/marker",extracted_tables)
    
    return extracted_tables

# 示例用法
if __name__ == "__main__":
    pdf_path = '/Users/qimai/Desktop/workspace/deepResearch/test-pdf/english/DeepSeek_onlyTable.pdf'  # 替换为你的PDF文件路径
    tables = marker_extractor(pdf_path)
    
    # 将表格内容保存到JSON文件
    output_dir = "output"
    import json
    import os
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "marker_extracted_tables.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(tables, f, ensure_ascii=False, indent=4)

    print(f"Extracted tables have been saved to {output_file}")