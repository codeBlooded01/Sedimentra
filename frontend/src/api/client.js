import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1' })

// Attach token on every request
api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-refresh on 401
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401 && !err.config._retry) {
      err.config._retry = true
      const isSession = !!sessionStorage.getItem('access_token')
      const storage = isSession ? sessionStorage : localStorage
      const refresh = storage.getItem('refresh_token')

      if (refresh) {
        try {
          const { data } = await axios.post('/api/v1/auth/refresh', { refresh_token: refresh })
          storage.setItem('access_token', data.access_token)
          storage.setItem('refresh_token', data.refresh_token)
          err.config.headers.Authorization = `Bearer ${data.access_token}`
          return api(err.config)
        } catch {
          storage.clear()
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(err)
  }
)

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authApi = {
  login:   (email, password) => api.post('/auth/login', { email, password }),
  signup:  (email, password, full_name) => api.post('/auth/signup', { email, password, full_name }),
  me:      () => api.get('/auth/me'),
  verify:  (token) => api.get(`/auth/verify-email?token=${token}`),
}

// ── Admin ─────────────────────────────────────────────────────────────────────
export const adminApi = {
  setup:       (email, password, full_name) => api.post('/auth/admin/setup', { email, password, full_name }),
  listUsers:   () => api.get('/admin/users'),
  approveUser: (id) => api.post(`/admin/users/${id}/approve`),
  rejectUser:  (id) => api.post(`/admin/users/${id}/reject`),
  impersonateUser: (id) => api.post(`/admin/users/${id}/impersonate`),
  promoteUser: (id) => api.post(`/auth/admin/promote/${id}`),
}

// ── Ingest ────────────────────────────────────────────────────────────────────
export const ingestApi = {
  upload: (asvFile, taxonomyFile, onProgress) => {
    const form = new FormData()
    form.append('asv_file', asvFile)
    form.append('taxonomy_file', taxonomyFile)
    return api.post('/ingest/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => onProgress && onProgress(Math.round((e.loaded * 100) / e.total)),
    })
  },
  status:         (jobId) => api.get(`/ingest/status/${jobId}`),
  report:         (jobId) => api.get(`/ingest/report/${jobId}`),
  preprocessing:  (jobId) => api.get(`/ingest/preprocessing/${jobId}`),
  /**
   * Generate descriptive + diagnostic report from an ingest job's raw files.
   * Works for both 'ready' and partially-validated jobs (layers 1+2 passed).
   */
  reportGenerate: (jobId) => api.post(`/ingest/report-generate/${jobId}`),
  /**
   * Fetch a head slice of the raw uploaded files
   */
  previewAsv:     (jobId) => api.get(`/ingest/preview/asv/${jobId}`),
  previewTaxonomy:(jobId) => api.get(`/ingest/preview/taxonomy/${jobId}`),
}

// ── Accession ─────────────────────────────────────────────────────────────────
export const accessionApi = {
  lookup:  (accession) => api.post('/accession/lookup', { accession }),
  preview: (jobId)     => api.get(`/accession/preview/${jobId}`),
  confirm: (jobId, confirmed) => api.post(`/accession/confirm/${jobId}`, { job_id: jobId, confirmed }),
  status:  (jobId)     => api.get(`/accession/status/${jobId}`),
  validation: (jobId)  => api.get(`/accession/validation/${jobId}`),
}

export default api
