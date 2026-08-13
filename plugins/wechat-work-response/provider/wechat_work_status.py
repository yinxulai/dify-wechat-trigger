from collections.abc import Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from .wechat_work_response_common import invoke_response


class WechatWorkStatusTool(Tool):
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage, None, None]:
        result = invoke_response(tool_parameters, require_status=True)
        yield self.create_json_message(result)
