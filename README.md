# ComicTra (漫画翻訳) 🎨

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs)](https://nextjs.org/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-00FFFF?style=for-the-badge)](https://github.com/ultralytics/ultralytics)

**ComicTra** 是一個端對端的自動漫畫翻譯系統，旨在將日文漫畫自動轉譯為高品質的繁體中文版本。系統結合了深度學習視覺模型、專用的漫畫 OCR 以及 AI 圖像修補技術，力求保持原始漫畫的藝術完整性。

---

## 🚀 核心功能

- 🔍 **智慧文字偵測**: 使用 **YOLOv8** 專屬 Manga 模型，精準識別對話氣泡，避免誤傷背景藝術。
- 📖 **漫畫專用 OCR**: 整合 **Manga-OCR**，專門處理漫畫中複雜的字體與排版（如垂直書寫、手寫體）。
- 🖌️ **無感圖像修補**: 採用 **Big-Lama** 模型進行 Inpainting，完美移除原文並修復背景。
- ✍️ **專業排版**: 自動將翻譯後的中文進行**垂直排版**，並根據氣泡形狀動態調整縮放與位置。
- 🌐 **多端支持**: 包含 **Next.js 網頁前端**與 **Android 行動端**，隨時隨地閱讀翻譯漫畫。

---

## 🏗️ 系統架構

專案採用微服務思維，將處理管線（Pipeline）與執行介面分離：

1.  **Backend (Python/FastAPI)**: 處理所有重型 AI 運算。
2.  **Frontend (Next.js/TS)**: 提供現代化的網頁介面。
3.  **Android App**: 方便在行動裝置上進行操作。

### 翻譯流水線 (Pipeline)
`Crawler (抓取)` ➔ `Detector (YOLOv8)` ➔ `OCR (Manga-OCR)` ➔ `Translator (AI)` ➔ `Inpainter (Big-Lama)` ➔ `Typesetter (豎排中文)`

---

## ⚙️ 快速上手

### 1. 後端 (Backend)
需要具備 NVIDIA GPU (建議) 以獲得最佳處理速度。
```bash
cd backend
pip install -r requirements.txt
python main.py
```
*註：首次執行會自動下載 YOLOv8 與相關權重模型。*

### 2. 前端 (Frontend)
```bash
cd frontend
npm install
npm run dev
```

### 3. Android 端
使用 Android Studio 打開 `android_app` 目錄進行編譯與安裝。

---

## 🛠️ 技術組件

- **框架**: FastAPI (後端), Next.js (前端), Kotlin/Java (Android)
- **AI 模型**:
    - **文字偵測**: YOLOv8-manga-text
    - **OCR**: Manga-OCR (Transformers Based)
    - **修補**: Big-Lama-Cleaning
- **排版引擎**: Pillow (自定義繁體中文豎排邏輯)

---

## 📝 授權與說明
本專案僅供學術研究與個人學習使用。請尊重原作版權，勿用於商業用途。
