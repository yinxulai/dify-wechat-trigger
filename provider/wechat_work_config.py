from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class RobotConfigurationError(ValueError):
    pass


class RobotNotFoundError(RobotConfigurationError):
    pass


@dataclass(frozen=True, slots=True)
class RobotConfig:
    id: str
    name: str
    aibotid: str
    token: str
    encoding_aes_key: str

    def to_subscription_properties(self) -> dict[str, str]:
        return {
            "robot_id": self.id,
            "robot_name": self.name,
            "aibotid": self.aibotid,
            "token": self.token,
            "encoding_aes_key": self.encoding_aes_key,
        }


def parse_robot_configs(value: Any) -> list[RobotConfig]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise RobotConfigurationError(f"robot configuration is not valid JSON: {exc.msg}") from exc

    if isinstance(value, Mapping):
        return _parse_visual_robot_configs(value)
    if not isinstance(value, list) or not value:
        raise RobotConfigurationError("robot configuration must contain at least one robot")

    robots: list[RobotConfig] = []
    robot_ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise RobotConfigurationError(f"robot configuration[{index}] must be an object")

        fields: dict[str, str] = {}
        for field in ("id", "name", "aibotid", "token", "encoding_aes_key"):
            field_value = item.get(field)
            if not isinstance(field_value, str) or not field_value.strip():
                raise RobotConfigurationError(
                    f"robot configuration[{index}].{field} must be a non-empty string"
                )
            fields[field] = field_value.strip()

        if fields["id"] in robot_ids:
            raise RobotConfigurationError(f"duplicate robot id: {fields['id']}")
        robot_ids.add(fields["id"])

        _validate_aes_key(fields["encoding_aes_key"])
        robots.append(RobotConfig(**fields))

    return robots


def _parse_visual_robot_configs(value: Mapping[str, Any]) -> list[RobotConfig]:
    fields = ("robot_id", "robot_name", "aibotid", "token", "encoding_aes_key")
    values: dict[str, list[Any]] = {}
    for field in fields:
        raw_value = value.get(field)
        if isinstance(raw_value, list):
            values[field] = raw_value
        elif raw_value is not None:
            values[field] = [raw_value]
        else:
            raise RobotConfigurationError(f"missing robot configuration field: {field}")

    lengths = {len(items) for items in values.values()}
    if len(lengths) != 1 or not lengths or not next(iter(lengths)):
        raise RobotConfigurationError("all robot configuration fields must have the same non-zero length")

    robot_count = next(iter(lengths))
    return parse_robot_configs(
        [
            {
                "id": values["robot_id"][index],
                "name": values["robot_name"][index],
                "aibotid": values["aibotid"][index],
                "token": values["token"][index],
                "encoding_aes_key": values["encoding_aes_key"][index],
            }
            for index in range(robot_count)
        ]
    )


def find_robot(robots: list[RobotConfig], robot_id: str) -> RobotConfig:
    for robot in robots:
        if robot.id == robot_id:
            return robot
    raise RobotNotFoundError(f"configured robot not found: {robot_id}")


def _validate_aes_key(encoding_aes_key: str) -> None:
    from .wechat_work_crypto import decode_aes_key

    try:
        decode_aes_key(encoding_aes_key)
    except ValueError as exc:
        raise RobotConfigurationError(str(exc)) from exc
