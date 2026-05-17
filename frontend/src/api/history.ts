import api from './index'

export interface RecordItem {
  id: number
  filename: string
  file_type: string
  file_path: string
  detect_time: string
  total_objects: number
  violation_count: number
  duration: number
  v_no_hardhat?: number
  v_no_safety_vest?: number
  v_close_to_machinery?: number
  v_close_to_vehicle?: number
  v_in_controlled_area?: number
  v_in_pole_area?: number
}

export interface PaginatedRecords {
  items: RecordItem[]
  total: number
  page: number
  page_size: number
}

export interface StatsDayItem {
  date: string
  count: number
}

export interface Stats {
  total_records: number
  total_violations: number
  today_records: number
  today_violations: number
  violation_by_type: Record<string, number>
  last_7_days: StatsDayItem[]
  violation_by_type_detail?: {
    no_hardhat: number
    no_safety_vest: number
    close_to_machinery: number
    close_to_vehicle: number
    in_controlled_area: number
    in_pole_area: number
  }
}

export interface AIReportViolation {
  type: string
  count: number
  first_time: string
  severity: string
  description: string
  suggestion: string
}

export interface AIBasicInfo {
  report_id: string
  report_time: string
  file_name: string
  detection_type: string
  detection_duration: number
  total_targets: number
}

export interface AISummary {
  total_violations: number
  risk_level: string
  violation_rate: string
}

export interface AISafetyAssessment {
  ppe_compliance: string
  proximity_compliance: string
  restricted_area_compliance: string
}

export interface AIReport {
  report_title: string
  basic_info: AIBasicInfo
  summary: AISummary
  violation_details: AIReportViolation[]
  safety_assessment: AISafetyAssessment
  overall_suggestion: string
  expert_signature: string
}

export function getStats() {
  return api.get<Stats>('/stats')
}

export function generateAIReport(recordId?: number) {
  const params = recordId ? { record_id: recordId } : {}
  return api.post<AIReport>('/report/ai-analysis', params)
}

export function getRecords(params: {
  page: number
  page_size: number
  file_type?: string
  start_date?: string
  end_date?: string
}) {
  return api.get<PaginatedRecords>('/records', { params })
}

export function getRecord(id: number) {
  return api.get<RecordItem>(`/records/${id}`)
}

export function getViolations(recordId: number) {
  return api.get(`/records/${recordId}/violations`)
}

export function deleteRecord(id: number) {
  return api.delete(`/records/${id}`)
}
