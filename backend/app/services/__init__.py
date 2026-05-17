from __future__ import annotations

from app.services import ai_service, case_service, detection_service

create_record = detection_service.create_record
create_violation = detection_service.create_violation
delete_record = detection_service.delete_record
get_ai_service = ai_service.get_ai_service
get_record = detection_service.get_record
get_records = detection_service.get_records
get_records_by_date_range = detection_service.get_records_by_date_range
get_stats = detection_service.get_stats
get_violations = detection_service.get_violations
create_case = case_service.create_case
create_case_from_record = case_service.create_case_from_record
get_case = case_service.get_case
get_cases = case_service.get_cases
update_case = case_service.update_case
delete_case = case_service.delete_case

__all__ = [
    'create_record',
    'create_violation',
    'delete_record',
    'get_ai_service',
    'get_record',
    'get_records',
    'get_records_by_date_range',
    'get_stats',
    'get_violations',
    'create_case',
    'create_case_from_record',
    'get_case',
    'get_cases',
    'update_case',
    'delete_case',
]