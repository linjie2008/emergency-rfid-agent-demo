"""RFID 进出记录客户端：默认走 mock，配置 RFID_API_BASE 后走真实接口。"""

from __future__ import annotations

import os
from typing import Any

import httpx

from rfid_data import filter_records


def get_in_out_merge_list(
    hospital_no: str | None = None,
    epc: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    base = os.getenv("RFID_API_BASE", "").rstrip("/")
    if not base:
        data = filter_records(hospital_no, epc, start_time, end_time)
        return {"code": 200, "message": "操作成功", "data": data}

    params: dict[str, str] = {}
    if hospital_no:
        params["hospitalNo"] = hospital_no
    if epc:
        params["epc"] = epc
    if start_time and end_time:
        params["startTime"] = start_time
        params["endTime"] = end_time

    headers = {
        "buildId": os.getenv("RFID_BUILD_ID", "1"),
    }
    token = os.getenv("RFID_API_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{base}/emergency/rfidInOutArea/getInOutMergeList"
    resp = httpx.get(url, params=params, headers=headers, timeout=20.0)
    resp.raise_for_status()
    return resp.json()
