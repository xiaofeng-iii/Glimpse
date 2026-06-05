import axios from 'axios'
import { getApiBaseUrl, getBackendAuthToken } from '@/config/runtime'

const api = axios.create({
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  config.baseURL = getApiBaseUrl()
  const token = getBackendAuthToken()
  if (token) {
    (config.headers as Record<string, string>)['X-Glimpse-Auth'] = token
  }
  return config
})

// Types
export interface Memory {
  id: string
  created_at: string
  image_path: string
  ai_summary: string
  app_name: string
  text_content?: string
  extra_images?: string
  sync_status: string
  match_sources: string[]
}

export interface Settings {
  hotkeys: Record<string, string>
  screenshot: Record<string, any>
  ai: Record<string, any>
  ocr: Record<string, string>
  ui: Record<string, any>
  cluster: Record<string, any>
}

// Memories API
export const memoriesApi = {
  list: async (limit = 100, offset = 0): Promise<{ memories: Memory[], total: number }> => {
    const response = await api.get(`/memories?limit=${limit}&offset=${offset}`)
    return response.data
  },

  get: async (id: string): Promise<Memory> => {
    const response = await api.get(`/memories/${id}`)
    return response.data
  },

  delete: async (id: string): Promise<{ success: boolean }> => {
    const response = await api.delete(`/memories/${id}`)
    return response.data
  },
}

// Search API
export const searchApi = {
  search: async (query: string, source = 'all', limit = 20): Promise<{ memories: Memory[], query: string, source: string }> => {
    const response = await api.get(`/search?q=${encodeURIComponent(query)}&source=${source}&limit=${limit}`)
    return response.data
  },
}

// Screenshot API
export const screenshotApi = {
  trigger: async (force = false): Promise<{ success: boolean, message: string, image_path?: string }> => {
    const response = await api.post('/screenshot', { force })
    return response.data
  },

  triggerAndAnalyze: async (
    force = false,
  ): Promise<{
    success: boolean
    accepted?: boolean
    memory_id?: string
    message?: string
    image_path?: string
    source?: string
    clustered?: boolean
    cluster_count?: number
  }> => {
    const response = await api.post('/screenshot/analyze', { force })
    return response.data
  },
}

// Settings API
export const settingsApi = {
  get: async (): Promise<Settings> => {
    const response = await api.get('/settings')
    return response.data
  },

  update: async (settings: Partial<Settings>): Promise<{ success: boolean }> => {
    const response = await api.put('/settings', settings)
    return response.data
  },

  reset: async (): Promise<{ success: boolean }> => {
    const response = await api.post('/settings/reset')
    return response.data
  },

  testAi: async (apiKey?: string, baseUrl?: string, model?: string): Promise<{ success: boolean, message: string }> => {
    const response = await api.post('/settings/ai/test', { api_key: apiKey, base_url: baseUrl, model })
    return response.data
  },
}

// Cluster API
export const clusterApi = {
  status: async (): Promise<{ state: string, count: number, max_count: number, images: string[], remaining_seconds: number }> => {
    const response = await api.get('/cluster/status')
    return response.data
  },

  submit: async (): Promise<{ success: boolean, message: string, images?: string[] }> => {
    const response = await api.post('/cluster/submit')
    return response.data
  },

  cancel: async (): Promise<{ success: boolean, message: string }> => {
    const response = await api.post('/cluster/cancel')
    return response.data
  },
}

// Stats API
export const statsApi = {
  get: async (): Promise<{ sqlite_count: number, chroma_count: number, synced: boolean }> => {
    const response = await api.get('/stats')
    return response.data
  },
}

// Health check
export const healthApi = {
  check: async (): Promise<{ status: string, app?: string, role?: string, version?: string, pid?: number }> => {
    const response = await api.get('/health', {
      timeout: 2000,
    })
    return response.data
  },
}
