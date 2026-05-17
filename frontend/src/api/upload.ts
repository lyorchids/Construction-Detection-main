import api from './index'

export function uploadImage(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/upload/image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function uploadVideo(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/upload/video', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
