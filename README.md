# 📦 FILMIUM Domain

FILMIUM is a highly optimized, smart media management platform built as a detached, autonomous functional domain for the CORE AI OS. It features a plug-and-play architecture that automatically registers with the main CORE system runtime when attached.

## 📸 Interface Preview
*(Place your Dashboard, Video Page, and Subtitle Terminator screenshots here)*

## ⚡ Technical Core & Features

*   🔌 **Plug-and-Play Storage Indexing**: Real-time monitoring and auto-detection of external drives (USB). Automates media discovery and populates metadata dynamically using the TMDB API.
*   📊 **FFmpeg Data Pipeline**: Directly hooks into media containers to extract precise real-time stream diagnostics, codecs, and structural file properties.
*   ✂️ **The Subtitle Terminator (Advanced Parser)**: A custom-built visual editor designed for deep data cleaning. It instantly repairs character encoding (ANSI to UTF-8), fixes timeline/timestamp drifts, strips out malicious script links, and allows mass-filtering of unwanted text elements.
*   🗂️ **Persistent JSON Architecture**: Generates localized structural database maps within media directories to guarantee lightning-fast subsequent directory scans.

## 🛠️ Technology Stack
*   **System Backend**: Tauri (Rust-powered environment for low-level local file-system operations and process execution)
*   **User Interface**: React, TypeScript, Tailwind CSS
*   **Media Processing**: FFmpeg binary integration
---
## 📸 Interface Preview

### Dashboard Okruženje
![Dashboard](screenshots/Filmium\1\dashboard.png)

### Terminator Prevoda (Data Parser)
![Subtitle Terminator](screenshots/Filmium\6\Terminator\Prevoda.png)

### Skeniranje i Upload Sistem
![Upload System](screenshots/Filmium\5\Uploud.png)



---
Developed by [H4K3R0S](https://github.com) as part of the CORE OS Ecosystem.
