from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import Any

from werkzeug import Request, Response

from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.trigger import EventDispatch, Subscription, UnsubscribeResult
from dify_plugin.errors.trigger import SubscriptionError, TriggerDispatchError, TriggerValidationError
from dify_plugin.interfaces.trigger import Trigger, TriggerSubscriptionConstructor

from .wechat_work_crypto import WechatWorkCrypto, WechatWorkCryptoError, find_robot, parse_robot_configs


class WechatWorkTrigger(Trigger):
    def _dispatch_event(self, subscription: Subscription, request: Request) -> EventDispatch:
        robot_id = subscription.parameters.get("robot_id") if subscription.parameters else None
        robot = find_robot(parse_robot_configs(subscription.properties), str(robot_id))
        crypto = WechatWorkCrypto(robot.token, robot.encoding_aes_key, robot.aibotid)

        timestamp = request.args.get("timestamp", "")
        nonce = request.args.get("nonce", "")
        encrypted = request.args.get("echostr") if request.method == "GET" else None
        if request.method == "GET":
            if not encrypted:
                raise TriggerValidationError("Missing echostr")
            crypto.verify_signature(request.args.get("msg_signature", ""), timestamp, nonce, encrypted)
            return EventDispatch(events=[], response=Response(crypto.decrypt(encrypted), status=200))

        raw_body = request.get_data()
        try:
            envelope = json.loads(raw_body or b"{}")
            encrypted = envelope.get("encrypt")
            if not isinstance(encrypted, str):
                raise TriggerDispatchError("Missing encrypt field")
            crypto.verify_signature(request.args.get("msg_signature", ""), timestamp, nonce, encrypted)
            payload = json.loads(crypto.decrypt(encrypted))
        except (WechatWorkCryptoError, json.JSONDecodeError) as exc:
            raise TriggerDispatchError(str(exc)) from exc
        if not isinstance(payload, Mapping):
            raise TriggerDispatchError("Decrypted payload must be a JSON object")
        if payload.get("aibotid") != robot.aibotid:
            raise TriggerValidationError("Callback robot does not match the selected robot")
        if not payload.get("msgid"):
            raise TriggerDispatchError("Missing msgid")

        return EventDispatch(
            events=["message_received"],
            response=Response('{"status":"ok"}', status=200, mimetype="application/json"),
            payload=dict(payload),
        )


class WechatWorkSubscriptionConstructor(TriggerSubscriptionConstructor):
    def _create_subscription(
        self,
        endpoint: str,
        parameters: Mapping[str, Any],
        credentials: Mapping[str, Any],
        credential_type: CredentialType,
    ) -> Subscription:
        del credential_type
        robots = parse_robot_configs(credentials)
        robot_id = parameters.get("robot_id")
        if not isinstance(robot_id, str) or not robot_id:
            raise SubscriptionError("robot_id is required", error_code="missing_robot_id")
        robot = find_robot(robots, robot_id)
        return Subscription(
            expires_at=-1,
            endpoint=endpoint,
            parameters={"robot_id": robot_id},
            properties={
                "robot_id": robot.id,
                "robot_name": robot.name,
                "aibotid": robot.aibotid,
                "token": robot.token,
                "encoding_aes_key": robot.encoding_aes_key,
            },
        )

    def _delete_subscription(self, subscription: Subscription, credentials: Mapping[str, Any], credential_type: CredentialType) -> UnsubscribeResult:
        del subscription, credentials, credential_type
        return UnsubscribeResult(success=True, message="Webhook subscription removed from Dify.")

    def _refresh_subscription(self, subscription: Subscription, credentials: Mapping[str, Any], credential_type: CredentialType) -> Subscription:
        del credentials, credential_type
        return subscription

    def _fetch_parameter_options(self, parameter: str, credentials: Mapping[str, Any], credential_type: CredentialType) -> list[ParameterOption]:
        del credential_type
        if parameter != "robot_id":
            return []
        return [
            ParameterOption(value=robot.id, label=I18nObject(en_US=f"{robot.name} ({robot.id})"))
            for robot in parse_robot_configs(credentials)
        ]

    def _validate_api_key(self, credentials: Mapping[str, Any]) -> None:
        parse_robot_configs(credentials)
