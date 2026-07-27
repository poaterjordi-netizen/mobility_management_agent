const test = require("node:test")
const assert = require("node:assert/strict")

let stored = {}
global.wx = {
  getStorageSync() {
    return stored
  },
  setStorageSync(_key, value) {
    stored = value
  },
  removeStorageSync() {
    stored = {}
  },
}

const {
  ENVIRONMENTS,
  clearRuntimeConfig,
  getRuntimeConfig,
  saveEnvironment,
} = require("../miniprogram/config")

test("defaults to the fixed Alibaba Cloud ingress", () => {
  stored = {}
  const config = getRuntimeConfig()
  assert.equal(config.environment, "production")
  assert.equal(config.apiBaseUrl, "https://metro.9m-zx.com/mobility")
  assert.equal(config.requestDomain, "https://metro.9m-zx.com")
  assert.equal(config.dataScope, "synthetic")
})

test("stores only a versioned non-sensitive environment choice", () => {
  saveEnvironment("local")
  assert.deepEqual(Object.keys(stored).sort(), ["configVersion", "environment"])
  assert.equal(getRuntimeConfig().apiBaseUrl, ENVIRONMENTS.local.apiBaseUrl)
  assert.equal(clearRuntimeConfig().environment, "production")
})
