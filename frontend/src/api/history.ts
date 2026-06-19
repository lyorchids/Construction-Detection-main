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
  violations: Record<string, number>
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
  violation_by_type_detail?: Record<string, number>
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
  analysis_period?: string
  total_records?: number
}

export interface AISummary {
  total_violations: number
  risk_level: string
}

export interface AISafetyAssessment {
  overall_evaluation: string
  risk_factors: string[]
  key_findings: string
}

export interface DailyOverview {
  dates: string[]
  daily_counts: Record<string, Record<string, number>>
  trend: 'increasing' | 'decreasing' | 'stable'
  record_breakdown: {
    filename: string
    detect_time: string
    date: string
    time: string
    violation_count: number
    type_counts: Record<string, number>
  }[]
}

export interface AIReport {
  report_title: string
  basic_info: AIBasicInfo
  summary: AISummary
  violation_details: AIReportViolation[]
  daily_overview?: DailyOverview | null
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

export function generateAIReportByDate(startDate: string, endDate: string) {
  return api.post<AIReport>('/report/ai-analysis', {
    start_date: startDate,
    end_date: endDate,
  })
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

export function downloadAIReportWord(recordId: number) {
  return api.post('/report/ai-analysis/download', { record_id: recordId }, {
    responseType: 'blob',
  })
}

export function downloadAIReportWordByDate(startDate: string, endDate: string) {
  return api.post('/report/ai-analysis/download', {
    start_date: startDate,
    end_date: endDate,
  }, {
    responseType: 'blob',
  })
}
