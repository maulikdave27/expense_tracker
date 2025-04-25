# YouTube Transcript Summarizer

A powerful and user-friendly web application that simplifies YouTube video transcripts into concise summaries. Built using Flask and the Gemini API, with a sleek Material You-inspired UI.

---

## 🌟 Features

- 🔍 Search YouTube video transcripts by URL  
- 📝 Generate concise and accurate summaries  
- 🕓 View search history with timestamps  
- 🌐 Translate summaries into multiple languages (via Google Translate)  
- 📁 Download summaries as `.txt` files  
- 🌙 Light/Dark mode toggle  
- ⚡ Fast and responsive UI using Material 3 Web Components  

---

## 🧰 Tech Stack

**Frontend:**  
- HTML, CSS, JS  
- [Material 3 Web Components (via CDN)](https://m3.material.io/)  

**Backend:**  
- Python  
- Flask  
- Gemini API (for summarization)  
- Google Translate API (for translations)  

**Deployment:**  
- Frontend: Cloudflare Pages  
- Backend: Render (FastAPI optional upgrade)  

---

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- `pip`
- Google Gemini API key

### Installation
```bash
git clone https://github.com/your-username/youtube-transcript-summarizer.git
cd youtube-transcript-summarizer
pip install -r requirements.txt
