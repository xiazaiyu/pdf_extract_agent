
# PDF Extract Agent

## 项目简介

`pdf_extract_agent` 是一个用于从PDF文件中高质量提取表格信息的系统，支持如下功能：

- 多工具联合抽取，支持以下开源工具：
  - [Marker](https://github.com/VikParuchuri/marker)：将复杂的 PDF 文件转换为结构化的 Markdown、JSON 和 HTML，支持多种文件格式和语言，具有高准确性和可扩展性。
  - [MinerU](https://github.com/opendatalab/MinerU)：将 PDF 转换为机器可读格式（如 Markdown、JSON），便于提取为任意格式，专注于解决科学文献中的符号转换问题。
  - [Docling](https://github.com/docling-project/docling)：简化文档处理，解析多种格式，提供与生成式 AI 生态系统的无缝集成。
- 使用LLM优化Marker+Mineru+Docling的抽取结果
- 使用LVM，利用表格的截图，对抽取工具的抽取结果进行优化


## 安装方法

- 创建一个python3.10环境
- 安装依赖
```bash
pip install -r requirements.txt
```

## 使用方法

1. 创建LLM服务
2. 创建pdf_extract_agent
3. 指定工具进行抽取

```python
from pdf_toolkit import marker_extractor, mineru_extractor, docling_extractor, combinedTool
from my_utils import save_agent_output
from camel.models import ModelFactory
from camel.types import ModelType, ModelPlatformType
import os
# 定义LLM模型
model = ModelFactory.create(
    model_platform=ModelPlatformType.DEEPSEEK,
    model_type=ModelType.DEEPSEEK_CHAT,
    model_config_dict={"temperature": 0.0},
    )

# 创建agent
agent = TableOptimizationAgent(model=model)

# 进行抽取
pdf_file = "./test-pdf/english/DeepSeek_onlyTable.pdf"

# 方法1，采用联合工具+LLM优化
combined_tool = combinedTool(marker_extractor,mineru_extractor,docling_extractor) # 定义联合工具
content_list1,table_list1 =  agent.extract_with_combined_tables(pdf_file,combined_tool)

# 方法2，采用联合工具+表格截图辅助的VLM优化
content_list2,table_list2 =  agent.extract_with_combined_tables_vlm(pdf_file,combined_tool)

# 保存结果
pdf_name = os.path.basename(pdf_file).split(".")[0]
save_agent_output("./results/method1",pdf_name,content_list1,table_list1)
save_agent_output("./results/method2",pdf_name,content_list2,table_list2)
```

## 示例结果格式

每个表格结果为一个JSON对象，包含：

```json
{
  "page_idx": 0,
  "table_body": "<table>...</table>",
  "table_caption": "...",
  "table_footnote": "..."
}
```
