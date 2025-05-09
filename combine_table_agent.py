import copy
import json
from typing import Any, Dict, List, Tuple
from camel.messages import BaseMessage
from camel.models import ModelFactory
from camel.types import ModelType, TaskType, ModelPlatformType
from camel.agents import ChatAgent
from pdf_toolkit import marker_extractor, mineru_extractor, docling_extractor, combinedTool, cache_to_folder
import os
import glob
from PIL import Image
import pypdfium2 as pdfium
from PIL import Image
from my_utils import PDFCropper, get_model_response, save_agent_output

class TableOptimizationAgent:
    def __init__(self,model):
        self.model_backend = model
        self.single_tool_prompt = """You are a text correction expert specializing in accurately reproducing text from images.
You will receive an image and an html representation of the table in the image.
Your task is to correct any errors in the html representation.  The html representation should be as faithful to the original table image as possible.  The table image may be rotated, but ensure the html representation is not rotated.  Make sure to include HTML for the full table, including the opening and closing table tags.

Some guidelines:
- Reproduce the original values from the image as faithfully as possible.  
- There may be stray characters in the html representation that don't match the image - fix these.
- Ensure column headers match the correct column values.
- If you see any inline math in a table cell, fence it with the <math> tag.  Block math should be fenced with <math display="block">.
- Replace any images in table cells with a description, like "Image: [description]".
- Only use the tags th, td, tr, br, span, sup, sub, i, b, math, and table.  Only use the attributes display, style, colspan, and rowspan if necessary.  You can use br to break up text lines in cells.
- Make sure the columns and rows match the image faithfully, and are easily readable and interpretable by a human.

**Instructions:**
1. Carefully examine the provided text block image.
2. Analyze the html representation of the table.
3. Write a comparison of the image and the html representation, paying special attention to the column headers matching the correct column values.
4. If the html representation is completely correct, or you cannot read the image properly, then write "No corrections needed."  If the html representation has errors, generate the corrected html representation.  Output only either the corrected html representation or "No corrections needed."
**Example:**
Input:
```html
<table>
    <tr>
        <th>First Name</th>
        <th>Last Name</th>
        <th>Age</th>
    </tr>
    <tr>
        <td>John</td>
        <td>Doe</td>
        <td>25</td>
    </tr>
</table>
```
Output:
comparison: The image shows a table with 2 rows and 3 columns.  The text and formatting of the html table matches the image.  The column headers match the correct column values.
```html
No corrections needed.
```
**Input:**
```html
{block_html}
```
"""
        self.combine_tables_prompt = """You are an expert agent who combines table-extraction results from PDF documents.
Three candidate results will be injected into this prompt as plain Python dictionaries under the names mineru_result, docling_result, and marker_result.  Each dictionary may contain errors such as missing titles, wrongly merged rows or columns, or alignment problems.

mineru_result: {mineru_result}
docling_result: {docling_result}
marker_result: {marker_result}

Your task
	1.	Read the three candidate dictionaries.  For each one, check the HTML in table_body, and decide whether the row and column structure is correct.  Inspect table_caption and table_footnote for relevance and completeness.
	2.	Choose the best candidate or merge information across candidates.  You may, for example, keep the body from one tool but copy the caption from another if that improves quality.  When you merge, correct obvious merged-cell and alignment errors when you can do so safely.
	3.	In your internal reasoning, record why you chose one candidate or how you merged them, paying special attention to row or column merging and alignment issues.
	4.	Produce your response in two parts.
	    •	First write “comparison:” on a new line, followed by a short, plain-language assessment of the three inputs and a statement of what you decided to do.
	    •	Then start a new line with “Final Answer:\n” (note the line break).  After that, output one JSON object with the keys ‘table_body’, ‘table_caption’, ‘table_footnote’, and ‘page_idx’.  If no usable table can be produced, output the empty object {} instead.
        
    """        
        self.combine_tables_with_vlm_prompt2 = """You are a table-correction and fusion expert.  
You will receive one table screenshot and three candidate extraction results, passed as plain Python dictionaries under the names mineru_result, docling_result, and marker_result.

mineru_result: {mineru_result}
docling_result: {docling_result}
marker_result: {marker_result}

Your goal is to deliver one clean, human-readable HTML table that matches the screenshot as closely as possible.

Guidelines:
- Use the screenshot as the final authority for every value, row, and column. After choosing or merging candidate results, you must **carefully correct the result** to match the screenshot exactly.
- The screenshot only shows the table body. The caption and footnote must be selected or merged from the three candidate results. You may, for example, keep the body from one tool but copy the caption or footnote from another if that improves completeness.
- Fix stray characters, split or merged cells, and alignment errors according to the screenshot.
- If you encounter inline math, fence it with <math>. Use <math display="block"> for block math.
- If a cell contains an image, replace it with text like "Image: [short description]".
- Only use these HTML tags: table, tr, th, td, br, span, sup, sub, i, b, math.
- Only use these attributes if necessary: style, display, colspan, rowspan.
- The final table HTML must start with <table> and end with </table>. The HTML must not be rotated, even if the screenshot is rotated.

Steps you must follow:
1. Analyze the screenshot carefully to understand the correct structure.
2. Read and assess each candidate dictionary:
    - For each candidate, check if the table_body structure (rows and columns) is correct according to the screenshot.
    - Evaluate table_caption and table_footnote based on their relevance and completeness. (The screenshot does not provide caption or footnote.)
3. Choose the best candidate or merge parts from multiple candidates.
4. **After selecting or merging, you must further correct the result based on the screenshot** to fix any mistakes that remain.
5. If none of the candidates can produce a usable table, return an empty object {}.
6. Your response must have two parts:
   • First, write “comparison:” on a new line, followed by a clear explanation of the problems found in the three inputs, and what you decided to do.  
   • Then start a new line with “Final Answer:\n” (note the line break). After that, output one JSON object with the keys "table_body", "table_caption", "table_footnote", and "page_idx".

If one candidate is already perfect according to the screenshot and no corrections are needed, you may output it directly.
    """
    
    def rewrite_table_with_vlm(self, table: Dict[str, Any],table_img: Image.Image):
        '''
            对一个表格的一种表示使用VLM进行优化（使用表格截图）
        '''
        prompt = self.single_tool_prompt.replace("{block_html}", table["table_body"])
        content = get_model_response(self.model_backend,prompt,[table_img])

        # 从content中提取rewrited_table_body
        if "no corrections" in content.lower():
            rewrited_table_body = table["table_body"]
        else:
            rewrited_table_body = content.strip().lstrip("```html").rstrip("```").strip()


        rewrited_table = table.copy()
        rewrited_table["table_body"] = rewrited_table_body

        return content, rewrited_table
        
    def combine_tables(self, tables: List[Dict[str, Any]], table_img):
        '''
            对一个表格的多种表示进行融合、优化
            可选用图片来辅助，若table_img不为None
        '''
        for table in tables:
            if table is not None:
                table.pop("bbox")
        if table_img is None:
            prompt = self.combine_tables_prompt.replace("{marker_result}", str(tables[0]))
            prompt = prompt.replace("{mineru_result}",str(tables[1]))
            prompt = prompt.replace("{docling_result}",str(tables[2]))
            content = get_model_response(self.model_backend,prompt)
        else:
            prompt = self.combine_tables_with_vlm_prompt.replace("{marker_result}", str(tables[0]))
            prompt = prompt.replace("{mineru_result}",str(tables[1]))
            prompt = prompt.replace("{docling_result}",str(tables[2]))
            content = get_model_response(self.model_backend,prompt,[table_img])

        # 从content中提取rewrited_table_body
        rewrited_table = {}

        # Extract the part after "Final answer:\n"
        if "Final answer:\n" in content:
            answer_part = content.split("Final answer:\n", 1)[1].strip()
            # content_part = content.split("Final answer:\n", 1)[0]
        elif "Final Answer:\n" in content:
            answer_part = content.split("Final Answer:\n", 1)[1].strip()
            # content_part = content.split("Final Answer:\n", 1)[0]
        elif "final answer:\n" in content:
            answer_part = content.split("final answer:\n", 1)[1].strip()
            # content_part = content.split("final answer:\n", 1)[0]
        else:
            answer_part = {}
        
        # Handle potential code blocks (e.g., ```json ... ```)
        import re
        code_blocks = re.findall(r'```(?:json)?\s*(.*?)\s*```', answer_part, re.DOTALL)
        json_str = code_blocks[0] if code_blocks else answer_part
        
        try:
            rewrited_table = json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback to literal_eval for Python-like structures
            try:
                import ast
                rewrited_table = ast.literal_eval(json_str)
            except:
                pass

        return content, rewrited_table

    def extract_with_combined_tables(self,test_pdf_path,combined_tools):
        """
            提取一个pdf文件的表格，通过多种提取工具+LLM修正的方法
        """
        
        # Run the tool extraction
        extracted_tables = combined_tools(test_pdf_path)
        content_list = []
        table_list = []
        # 优化每个表格
        for tables in extracted_tables:
            content, rewrited_table = self.combine_tables(tables,None)
            content_list.append(content)
            table_list.append(rewrited_table)
        
        return content_list, table_list

    def extract_with_combined_tables_vlm(self,test_pdf_path,combined_tools):
        """
            提取一个pdf文件的表格，通过多种提取工具+表格截图辅助的VLM修正的方法
        """
        # Run the tool extraction
        extracted_tables = combined_tools(test_pdf_path)

        # # 提取表格截图
        cropper = PDFCropper(test_pdf_path)

        content_list = []
        table_list = []
        # 优化每个表格
        for i,tables in enumerate(extracted_tables):
            for table in tables:
                if table is not None:
                    rep_table = table
                    break
            bbox = rep_table.pop("bbox")
            page_idx = rep_table["page_idx"]
            table_img = cropper.crop(int(page_idx),bbox)
            content, rewrited_table = self.combine_tables(tables,table_img)
            content_list.append(content)
            table_list.append(rewrited_table)

        return content_list, table_list

    def extract_with_single_tool(self,test_pdf_path,output_dir,tool):
        """
            提取一个pdf文件的表格，通过单个提取工具+表格截图辅助的VLM修正的方法
        """
        # Run the tool extraction
        extracted_tables = tool(test_pdf_path)

        # 提取表格截图
        cropper = PDFCropper(test_pdf_path)

        content_list = []
        table_list = []
        # 优化每个表格
        for i,table in enumerate(extracted_tables):
            bbox = table.pop("bbox")
            page_idx = table["page_idx"]
            table_img = cropper.crop(int(page_idx),bbox)
            content, rewrited_table = self.rewrite_table_with_vlm(table, table_img)
            content_list.append(content)
            table_list.append(rewrited_table)

        return content_list, table_list


if __name__ == "__main__":
    input_folder = "/Users/qimai/Desktop/workspace/deepResearch/test-pdf/english2"
    
    # 定义LLM模型
    output_folder = "./single_table_output/agent/deepseek_combined"
    model = ModelFactory.create(
        model_platform=ModelPlatformType.DEEPSEEK,
        model_type=ModelType.DEEPSEEK_CHAT,
        model_config_dict={"temperature": 0.0},
        )

    # 创建agent
    agent = TableOptimizationAgent(model=model)

    # 获取文件夹内所有PDF文件
    # pdf_files = glob.glob(os.path.join(input_folder, "*.pdf"))
    pdf_files = [
        "/Users/qimai/Desktop/workspace/deepResearch/test-pdf/english/DeepSeek_onlyTable.pdf",
    ]

    # 同时用marker, minerU, docling三种工具进行提取
    combined_tool = combinedTool(marker_extractor,mineru_extractor,docling_extractor)

    for pdf_file in pdf_files:
        print(f"start to process {pdf_file}")
        pdf_name = os.path.basename(pdf_file).split(".")[0]
        # extract_with_single_tool(agent, pdf_file, output_folder,mineru_extractor)
        
        # 使用agent提取表格
        content_list,table_list =  agent.extract_with_combined_tables(pdf_file,combined_tool)
        
        # 保存输出
        save_agent_output(output_folder,pdf_name,content_list,table_list)
        
        print(f"Processed {pdf_file}")














