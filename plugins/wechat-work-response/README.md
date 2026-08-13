# WeCom Response Plugin

This plugin is the asynchronous response side of the WeCom integration. It is
packaged separately from the trigger because Dify does not allow trigger and
endpoint providers in the same plugin manifest.

The response endpoints accept a workflow result and deliver it through the
unique `response_url` emitted by the trigger event. The URL is carried in each
workflow request, so the response plugin has no static backend URL or copy of
the trigger's callback secrets. WeCom authorizes the outbound request through
the HTTPS response URL itself.

`POST /wechat-work/reply` accepts `response_url`, `message_id`, `content`, and
optional message metadata. `POST /wechat-work/status` requires the same fields
plus a non-empty `status` field. Call the endpoint from a workflow HTTP Request
node using the `response_url` output from the trigger.
