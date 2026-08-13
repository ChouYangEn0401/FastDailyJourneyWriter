# iOS（iPhone / iPad）— 規劃中

**目前是空的，而且應該保持是空的**，直到 `core/` 做出來為止。

## 為什麼還不能開始

這個 app 的輸出核心（把日記變成 HTML 與卡片）現在是 **Python**，
寫在 `backend/render/`。**Python 上不了 App Store。**

所以 iOS 版不是一個「打包工作」，是一次**移植**：
要先有 `core/`——同一套輸出邏輯的 JavaScript 版本。
在那之前，這個資料夾裡沒有任何東西可以放。

[`core/`](../../core/README.md) 已經開始了，做了富文字、主題、文件組裝三塊，
跟 Python 端逐案對照測過。**還沒動的是卡片排版和存檔**，
而存檔沒搬完就沒有離線，沒有離線就沒有可以上架的 app。

工作量估算、哪些檔案要搬、哪一塊最難，都在
**[docs/roadmap.md](../../docs/roadmap.md)** 的「二、手機版真正的難處」。

## 想先看看手機上長什麼樣

不用等這個資料夾。介面已經為手機重新排過了
（[docs/mobile-ui.md](../../docs/mobile-ui.md)），
開著電腦上的伺服器，用 iPhone 的 Safari 連過去就看得到——
做法在 [platforms/pwa/](../pwa/README.md)。
**那份介面目前還沒有在任何一支真的手機上開過**，
所以第一個回報的人就是在幫忙。

## 真的要開始的時候

前置條件，缺一不可：

- [ ] `core/` 已完成，`web/` 已經改用它（也就是 roadmap 的「路線 A」做完了）
- [ ] **一台 Mac**。沒有替代方案，雲端 CI 也要租 Mac runner
- [ ] Xcode
- [ ] Apple Developer Program 帳號（約每年 US$99，以官方公告為準）

然後：

```bash
npm install @capacitor/core @capacitor/cli @capacitor/ios
npx cap init
npx cap add ios          # 產生的東西放進這個資料夾
npx cap open ios         # 用 Xcode 開
```

## 這個資料夾能放什麼

只有這些：

- Xcode 專案檔（`.xcodeproj` / `.xcworkspace`）
- `Info.plist`、權限宣告
- 圖示、啟動畫面
- 簽章與 provisioning 設定
- App Store 的截圖與文案

**不要放任何功能邏輯。** 一旦某個功能寫進這裡，Android 就得抄一份，
兩邊立刻開始分岔。理由見 [platforms/README.md](../README.md)。

## 先知道的兩個雷

1. **`.pbxproj` 幾乎無法 merge。** 如果之後有第二個人一起做，
   同一時間只能一個人動 iOS 設定。用 SPM / CocoaPods 管相依，不要手改那個檔。
2. **`xcuserdata/`、`DerivedData/` 是機器專屬的垃圾檔。**
   `.gitignore` 已經先擋好了。
