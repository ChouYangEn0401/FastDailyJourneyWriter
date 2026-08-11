# PWA — 加到手機主畫面

> **狀態：已經寫好，但還沒有在任何一支真的手機上測過。**
> 下面每一段都是「照設計應該這樣」，不是「試過確實這樣」。

這是 [roadmap](../../docs/roadmap.md) 路線 A 的殼。不用 Mac、不用 Xcode、
不用 Android Studio、不用上架費——但也還不是完整的離線 app，原因在最後一節。

## 這個資料夾裡有什麼

| 檔案 | 做什麼 |
|---|---|
| `make_icons.py` | 畫圖示，輸出到 `web/` |

只有圖示產生器。真正被瀏覽器抓走的三個檔案住在 `web/`，
因為它們是**由伺服器送出去的**，不是打包產物：

| 檔案 | 送到哪個網址 |
|---|---|
| `web/manifest.webmanifest` | `/manifest.webmanifest` |
| `web/sw.js` | `/sw.js` |
| `web/icon.svg`、`icon-180.png`、`icon-512.png` | `/static/…` |

前兩個**一定要從網站根目錄送出**，路由寫在 `backend/main.py`：
service worker 只能管到自己網址底下的路徑，manifest 的 scope 也要蓋得住它
宣稱的頁面。放在 `/static/` 底下的話，兩個都只會對 `/static/` 生效。

## 圖示

```bash
python platforms/pwa/make_icons.py
```

圖示有進 repo，所以平常不用跑。改了圖案再跑。

沒有用 Pillow 或 cairosvg——為了一年畫兩次圖示，
在一個相依套件只有一個網頁伺服器的專案裡多裝一套影像函式庫並不划算。
所以那支腳本自己寫 PNG（`zlib` 是標準函式庫）。圖案本身也定義在裡面。

`icon-180.png` 只為了 iOS 存在。Safari 的「加入主畫面」不吃 SVG，
沒有這張就會拿網頁截圖當圖示。

## 現在就能在手機上打開

不需要上架，同一個 Wi-Fi 就好：

```bash
# 在電腦上
JOURNAL_HOST=0.0.0.0 python run.py     # Windows: set JOURNAL_HOST=0.0.0.0
```

然後在手機瀏覽器打 `http://<電腦的區網 IP>:8888`。

**會動的**：整個介面、寫、存、輸出頁面與卡片。
**不會動的**：service worker。瀏覽器只在 HTTPS 或 localhost 才肯註冊，
區網 IP 是 `http://`，所以會被跳過（`app.js` 的 `registerServiceWorker()`
有擋，不會噴錯）。也就是說電腦關掉，手機上就打不開了。

Android 的 Chrome 在 http 下仍然可以「加到主畫面」，
只是那是個捷徑，不是安裝好的 app。

## 驗過什麼

在無頭 Chrome（DevTools protocol）上確認過的：

- `/manifest.webmanifest` 與 `/sw.js` 都從根目錄送出，
  MIME 型別正確，`Service-Worker-Allowed: /` 有帶上
- manifest 是合法 JSON；三個圖示都拿得到
- `navigator.serviceWorker.register("/sw.js")` 會 resolve，scope 是 `/`
- `sw.js` 與 `app.js` 語法沒問題

**沒能驗到的：service worker 有沒有真的裝起來、有沒有快取到東西。**
無頭 Chrome 在這台機器上不會讓 worker 進入 active 狀態
（`register()` 成功，但 `getRegistrations()` 一直是空的），
所以 install 那段、快取內容、以及「`/api/` 真的沒被快取」這三件事
**只是照著寫的，沒有跑起來看過。**

## 還沒做的

- [ ] **在真的手機上開一次。** 目前只在無頭 Chrome 的 390／320／768／1440
      四種寬度看過版面，沒碰過真的裝置
- [ ] **service worker 實際裝起來跑一次**（在真的瀏覽器裡看 DevTools →
      Application → Service Workers），確認：install 有完成、
      shell 有進快取、`/api/` 沒有進快取
- [ ] iOS Safari 實測——安全區域、鍵盤、`dvh` 都是最容易出事的地方
- [ ] 「加到主畫面」實測（Android 與 iOS 各一次）
- [ ] HTTPS。沒有它就沒有 service worker，也就沒有真正的離線
- [ ] **離線寫作。** 這是最大的一塊，而且不是設定問題：
      現在資料在 Python 後端，`sw.js` 刻意不快取 `/api/`——
      日記顯示成昨天的答案，比明白地打不開更糟。
      要真的離線，得先把 `backend/storage.py` 搬到 `core/`，見
      [core/README.md](../../core/README.md)

## 提醒一件事

roadmap 提過：**iOS 的 PWA 長期不用時，儲存空間有被系統清掉的風險。**
對日記來說這件事很嚴重。真的走 PWA 這條路，
「匯出全部」的提醒必須做得比現在更明顯。
