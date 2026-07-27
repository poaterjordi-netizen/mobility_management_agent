const STORAGE_KEY = "mobilityAgentRuntimeConfig"
const CONFIG_VERSION = 2

const ENVIRONMENTS = {
  production: {
    id: "production",
    label: "阿里云正式入口",
    apiBaseUrl: "https://metro.9m-zx.com/mobility",
    requestDomain: "https://metro.9m-zx.com",
  },
  local: {
    id: "local",
    label: "本机调试",
    apiBaseUrl: "http://127.0.0.1:8000",
    requestDomain: "http://127.0.0.1:8000",
  },
}

const DEFAULT_ENVIRONMENT = "production"

function environmentFor(value) {
  return ENVIRONMENTS[value] || ENVIRONMENTS[DEFAULT_ENVIRONMENT]
}

function getRuntimeConfig() {
  const stored = wx.getStorageSync(STORAGE_KEY) || {}
  const environment = Number(stored.configVersion || 0) === CONFIG_VERSION
    ? environmentFor(stored.environment)
    : environmentFor(DEFAULT_ENVIRONMENT)
  return {
    configVersion: CONFIG_VERSION,
    environment: environment.id,
    label: environment.label,
    apiBaseUrl: environment.apiBaseUrl,
    requestDomain: environment.requestDomain,
    dataScope: "mixed",
  }
}

function saveEnvironment(environment) {
  const selected = environmentFor(environment)
  const value = {
    configVersion: CONFIG_VERSION,
    environment: selected.id,
  }
  wx.setStorageSync(STORAGE_KEY, value)
  return getRuntimeConfig()
}

function clearRuntimeConfig() {
  wx.removeStorageSync(STORAGE_KEY)
  return getRuntimeConfig()
}

module.exports = {
  CONFIG_VERSION,
  DEFAULT_ENVIRONMENT,
  ENVIRONMENTS,
  STORAGE_KEY,
  clearRuntimeConfig,
  environmentFor,
  getRuntimeConfig,
  saveEnvironment,
}
