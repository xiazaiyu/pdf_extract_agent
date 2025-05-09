from typing import List, Dict, Any
import logging
import os
import json
from pathlib import Path
from docling.document_converter import DocumentConverter
from .cache_decorator import cache_to_folder

@cache_to_folder("docling","/Users/qimai/Desktop/workspace/deepResearch/pdf_extract_agent/single_table_output/tool")
def docling_extractor(pdf_path: str) -> List[Dict[str, Any]]:
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
    

    # Convert PDF to structured document
    doc_converter = DocumentConverter()
    conv_res = doc_converter.convert(Path(pdf_path))
    
    extracted_tables = []
    
    for table in conv_res.document.tables:
        # Extract table content as HTML
        table_html = table.export_to_html()
        
        # Extract table caption
        table_caption = table.caption_text(conv_res.document)
        
        # Extract table footnotes
        footnotes = []
        for footnote in table.footnotes:
            footnotes.append(footnote.resolve(conv_res.document).text)
        table_footnote = "\n".join(footnotes)
        
        # Extract page index (convert to 0-based index)
        page_idx = table.prov[0].page_no - 1
        page_height = conv_res.pages[page_idx].size.height

        bbox = table.prov[0].bbox

        # Create table entry
        table_entry = {
            "table_body": table_html,
            "table_caption": table_caption,
            "table_footnote": table_footnote,
            "page_idx": str(page_idx),
            "bbox": [bbox.l, page_height - bbox.t, bbox.r, page_height - bbox.b] #letf, top, right, bottom
        }
        extracted_tables.append(table_entry)

    # name_without_suff = os.path.basename(pdf_path).split(".")[0]
    # save_tool_results(name_without_suff,"/Users/qimai/Desktop/workspace/deepResearch/pdf_extract_agent/tool_output/docling",extracted_tables)

    return extracted_tables

# 示例用法
if __name__ == "__main__":
    pdf_path = '/Users/qimai/Desktop/workspace/deepResearch/test-pdf/english/DeepSeek_onlyTable.pdf'  # 替换为你的PDF文件路径
    tables = docling_extractor(pdf_path)
    
    # 将表格内容保存到JSON文件
    output_dir = "output"
    import json
    import os
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "docling_extracted_tables.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(tables, f, ensure_ascii=False, indent=4)

       
    
    print(f"Extracted tables have been saved to {output_file}")