# Android — 規劃中

**目前是空的，而且應該保持是空的**，直到 `core/` 做出來為止。

## 為什麼還不能開始

跟 [iOS](../ios/README.md) 一樣：輸出核心現在是 Python，寫在 `backend/render/`，
而 Python 上不了手機商店。要先有 `core/`（JavaScript 版的輸出核心）。

細節見 **[docs/roadmap.md](../../docs/roadmap.md)**。

## 但 Android 值得先做

如果要在兩個手機平台之間挑一個先做，**選 Android**：

- **Android Studio 在 Windows 上就能跑**，不用先買一台 Mac
- Google Play 的上架費是**一次性**約 US$25，Apple 是**每年**約 US$99
  （以官方公告為準）
- 審查通常比 App Store 快

也就是說，你現在這台 Windows 就能把 Android 版從頭做到上架，
iOS 則卡在硬體上。試水溫從這裡開始成本最低。

## 真的要開始的時候

前置條件：

- [ ] `core/` 已完成，`web/` 已經改用它（roadmap 的「路線 A」）
- [ ] Android Studio
- [ ] Google Play Console 帳號

然後：

```bash
npm install @capacitor/core @capacitor/cli @capacitor/android
npx cap init
npx cap add android      # 產生的東西放進這個資料夾
npx cap open android     # 用 Android Studio 開
```

## 這個資料夾能放什麼

- Gradle 設定（`build.gradle`、`settings.gradle`）
- `AndroidManifest.xml`、權限宣告
- 圖示（`res/mipmap-*`）、啟動畫面
- 簽章設定（**keystore 本身絕對不要進 repo**）
- Google Play 的截圖與文案

**不要放任何功能邏輯。** 理由見 [platforms/README.md](../README.md)。

## 先知道的兩個雷

1. **`local.properties` 含有你這台電腦的 SDK 路徑**，不能 commit。
   `.gitignore` 已經先擋好了，連同 `.gradle/`、`build/`、`*.apk`、`*.aab`。
2. **簽章用的 keystore 弄丟就再也無法更新那個 app。**
   Google Play 上架後只認同一把 key。要離線備份，而且不要放在 repo 裡。
