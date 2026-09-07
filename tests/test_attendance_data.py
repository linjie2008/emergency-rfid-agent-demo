import json

from industrial_tools import (
    ACCESS_RECORDS,
    ATTENDANCES,
    SCHEDULES,
    query_access_records,
    query_attendances,
    query_schedules,
)


def _invoke(tool, **args):
    return json.loads(tool.invoke(args))


def test_attendance_demo_data_has_31_days_for_every_employee():
    assert len(ATTENDANCES) == len(SCHEDULES)
    assert len({row["date"] for row in ATTENDANCES}) == 31
    assert len({row["employeeNo"] for row in ATTENDANCES}) >= 60
    assert {row["status"] for row in ATTENDANCES} >= {"正常", "迟到", "早退", "缺卡", "缺勤", "休班"}


def test_wang_qiang_today_attendance_schedule_and_access_are_consistent():
    attendance = _invoke(query_attendances, person="王强", date="今天")
    schedule = _invoke(query_schedules, person="王强", date="今天")
    access = _invoke(query_access_records, person="王强", date="今天")

    assert attendance["count"] == 1
    assert schedule["count"] == 1
    assert access["count"] == 2
    assert attendance["data"][0]["employeeNo"] == "E2001"
    assert attendance["data"][0]["status"] == "迟到"
    assert attendance["data"][0]["scheduledStart"] == schedule["data"][0]["start"]
    assert {row["direction"] for row in access["data"]} == {"进入", "离开"}


def test_attendance_supports_relative_date_and_status_filters():
    result = _invoke(query_attendances, date="近7天", status="迟到")
    assert result["count"] > 0
    assert all(row["status"] == "迟到" for row in result["data"])
    assert len({row["date"] for row in result["data"]}) <= 7


def test_access_records_are_derived_from_attendance_clock_events():
    assert ACCESS_RECORDS
    attendance_keys = {(row["employeeNo"], row["date"]) for row in ATTENDANCES}
    assert all((row["employeeNo"], row["date"]) in attendance_keys for row in ACCESS_RECORDS)
