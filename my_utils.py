import json
import os
from typing import Any, Dict
import pypdfium2 as pdfium
from PIL import Image
from camel.types import ChatCompletion, RoleType
import json
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Type,
    Union,
)
from camel.agents._types import ModelResponse, ToolCallRequest
from camel.agents._utils import (
    handle_logprobs,
    safe_model_dump,
)
from camel.messages import BaseMessage

def get_model_response(model,prompt: str,img_list: List[Image.Image]| None = None) -> str:
    """
        LLM的调用接口，输入提示词与图像列表，返回LLM的回复
    """
    input_message = BaseMessage.make_user_message(
            role_name="User", 
            content=prompt,
            image_list= img_list
        )
    
    openai_message = input_message.to_openai_user_message()
    response = model.run([openai_message])
    response = _handle_batch_response(response)

    content = response.output_messages[0].content if response.output_messages else ""

    return content

def save_agent_output(output_dir,pdf_name, content_list, table_list):
    local_pdf_dir = os.path.join(output_dir, pdf_name)
    local_table_dir = os.path.join(local_pdf_dir, "tables")
    local_content_dir = os.path.join(local_pdf_dir, "contents")
    os.makedirs(local_pdf_dir, exist_ok=True)
    os.makedirs(local_table_dir, exist_ok=True)
    os.makedirs(local_content_dir, exist_ok=True)

    for i,(content,table) in enumerate(zip(content_list,table_list)):
        output_file = os.path.join(local_table_dir, f"{i+1}.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(table, f, ensure_ascii=False, indent=4)

        output_content_file = os.path.join(local_content_dir, f"{i+1}.md")
        with open(output_content_file, "w", encoding="utf-8") as f:
            f.write(content)


class PDFCropper:
    def __init__(self, pdf_path, dpi=192, flatten_page=False):
        self.pdf = pdfium.PdfDocument(pdf_path)
        self.page_images = {}  # 缓存每页渲染好的PIL图
        self.dpi = dpi
        self.flatten_page = flatten_page

    def _render_page(self, page_id):
        page = self.pdf[page_id]
        if self.flatten_page:
            page.flatten()
            page = self.pdf[page_id]
        pil_image = page.render(scale=self.dpi / 72, draw_annots=False).to_pil()
        pil_image = pil_image.convert("RGB")
        return pil_image

    def crop(self, page_id, bbox) -> Image.Image:
        """
        page_id: 页码，从0开始
        bbox: [left, top, right, bottom]
        返回：PIL.Image对象
        """
        if page_id not in self.page_images:
            self.page_images[page_id] = self._render_page(page_id)

        full_image = self.page_images[page_id]
        scale = self.dpi / 72
        left, top, right, bottom = [x * scale for x in bbox]
        cropped_image = full_image.crop((left, top, right, bottom))

        # 直接手动赋值 format
        cropped_image.format = "png"

        return cropped_image

    def close(self):
        self.page_images.clear()
        self.pdf.close()

def _handle_batch_response(
    response: ChatCompletion
) -> ModelResponse:
    r"""Process a batch response from the model and extract the necessary
    information.

    Args:
        response (ChatCompletion): Model response.

    Returns:
        _ModelResponse: parsed model response.
    """
    output_messages: List[BaseMessage] = []
    for choice in response.choices:
        meta_dict = {}
        if logprobs_info := handle_logprobs(choice):
            meta_dict["logprobs_info"] = logprobs_info

        chat_message = BaseMessage(
            role_name="assistant",
            role_type=RoleType.ASSISTANT,
            meta_dict=meta_dict,
            content=choice.message.content or "",
            parsed=getattr(choice.message, "parsed", None),
        )

        output_messages.append(chat_message)

    finish_reasons = [
        str(choice.finish_reason) for choice in response.choices
    ]

    usage = {}
    if response.usage is not None:
        usage = safe_model_dump(response.usage)

    tool_call_requests: Optional[List[ToolCallRequest]] = None
    if tool_calls := response.choices[0].message.tool_calls:
        tool_call_requests = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            tool_call_id = tool_call.id
            args = json.loads(tool_call.function.arguments)
            tool_call_request = ToolCallRequest(
                tool_name=tool_name, args=args, tool_call_id=tool_call_id
            )
            tool_call_requests.append(tool_call_request)

    return ModelResponse(
        response=response,
        tool_call_requests=tool_call_requests,
        output_messages=output_messages,
        finish_reasons=finish_reasons,
        usage_dict=usage,
        response_id=response.id or "",
    )