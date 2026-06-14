import api from './index'

export interface ProfileConfig {
  models: Record<string, {
    enabled: boolean
    threshold: number
    danger_rules?: Record<string, boolean>
  }>
  frame_interval?: number
  save_screenshots?: boolean
}

export interface DetectionProfile {
  id: number
  name: string
  type: string
  description: string
  config: ProfileConfig
  created_at: string
  updated_at: string
}

export function getProfiles(type?: string) {
  const params = type ? { type } : {}
  return api.get<DetectionProfile[]>('/profiles', { params })
}

export function getProfile(id: number) {
  return api.get<DetectionProfile>(`/profiles/${id}`)
}

export function createProfile(data: {
  name: string
  type: string
  description: string
  config: ProfileConfig
}) {
  return api.post<DetectionProfile>('/profiles', data)
}

export function updateProfile(id: number, data: {
  name?: string
  description?: string
  config?: ProfileConfig
}) {
  return api.put<DetectionProfile>(`/profiles/${id}`, data)
}

export function deleteProfile(id: number) {
  return api.delete(`/profiles/${id}`)
}
