import axios from 'axios'

const client = axios.create()
let tokenPromise = null

client.interceptors.request.use(async config => {
  if (!window.electronAPI?.getLocalApiToken) return config
  tokenPromise ||= window.electronAPI.getLocalApiToken()
  const token = await tokenPromise
  if (token) {
    config.headers ||= {}
    config.headers['X-Kaltsit-Token'] = token
  }
  return config
})

export default client
