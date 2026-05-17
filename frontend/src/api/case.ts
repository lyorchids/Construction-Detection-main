import api from './index'

export interface CaseItem {
  id: number
  title: string
  case_type: string
  severity: string
  scene_description: string
  recommended_actions: string
  process_info: string
  images: string[]
  source_record_id: number | null
  source_filename: string | null
  created_at: string
  updated_at: string
}

export interface CaseListData {
  items: CaseItem[]
  total: number
  page: number
  page_size: number
}

export interface CaseCreateData {
  title: string
  case_type: string
  severity: string
  scene_description?: string
  recommended_actions?: string
  process_info?: string
  images?: string[]
  source_record_id?: number | null
}

export function getCases(params: {
  page: number
  page_size: number
  case_type?: string
  severity?: string
  keyword?: string
}) {
  return api.get<CaseListData>('/cases', { params })
}

export function getCase(id: number) {
  return api.get<CaseItem>(`/cases/${id}`)
}

export function createCase(data: CaseCreateData) {
  return api.post<CaseItem>('/cases', data)
}

export function createCaseFromRecord(recordId: number) {
  return api.post<CaseItem>(`/cases/from-record/${recordId}`)
}

export function updateCase(id: number, data: Partial<CaseCreateData>) {
  return api.put<CaseItem>(`/cases/${id}`, data)
}

export function deleteCase(id: number) {
  return api.delete(`/cases/${id}`)
}
