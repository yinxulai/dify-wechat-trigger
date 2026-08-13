# WeCom Response Plugin

This plugin is the asynchronous response side of the WeCom integration. It is
packaged separately from the trigger because Dify does not allow trigger and
endpoint providers in the same plugin manifest.

The response endpoints accept a workflow result and deliver it through the
configured `response_backend_url`. The backend owns the shared state and the
WeCom credentials, then sends the reply or status update to WeCom. This split is
required because the trigger and response plugins do not share process memory.

`POST /wechat-work/reply` accepts `message_id`, `content`, and optional message
metadata. `POST /wechat-work/status` requires the same fields plus a non-empty
`status` field.
Configure the endpoint setting in Dify, then call the endpoint from a workflow
HTTP Request node.
