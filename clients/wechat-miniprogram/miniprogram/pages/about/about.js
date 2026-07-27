Page({
  data: {
    website: "https://metro.9m-zx.com/mobility/",
  },

  copyWebsite() {
    wx.setClipboardData({
      data: this.data.website,
      success() {
        wx.showToast({ title: "网站地址已复制", icon: "success" })
      },
    })
  },
})
