# YouTube & TikTok Video Downloader

A beautiful Python-based video downloader supporting YouTube and TikTok with single & bulk download capabilities.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | Python + Flask |
| **Frontend** | HTML/CSS/JS (Premium dark UI with glassmorphism) |
| **YouTube Downloads** | yt-dlp |
| **TikTok Downloads** | yt-dlp (watermark-free) |
| **Video Processing** | ffmpeg (for merging audio+video) |

## Features

### Core Features
- **Single Download**: Paste a single URL and download
- **Bulk Download**: Paste multiple URLs (one per line) or playlist URL
- **Platform Detection**: Auto-detect YouTube vs TikTok from URL
- **Quality Selection**: 1080p preferred, best available if source is lower
- **TikTok Watermark-Free**: Downloads without watermark using yt-dlp
- **Format Support**: Videos, Shorts, Long videos, TikTok clips

### UI Features
- Dark glassmorphism theme with gradient accents
- Real-time download progress bars
- Download history
- Platform badges (YouTube/TikTok)
- Responsive design
- Animated transitions and micro-interactions

## Proposed Changes

### Backend

#### [NEW] [app.py](file:///d:/yt%20and%20tik%20downloader/app.py)
- Flask server with routes for:
  - `GET /` - Serve the UI
  - `POST /api/info` - Fetch video info (title, thumbnail, quality options)
  - `POST /api/download` - Start download
  - `GET /api/progress/<id>` - SSE endpoint for download progress
  - `GET /api/downloads` - List downloaded files
  - `GET /api/file/<filename>` - Serve downloaded file

#### [NEW] [downloader.py](file:///d:/yt%20and%20tik%20downloader/downloader.py)
- Core download engine using yt-dlp
- YouTube download with quality selection
- TikTok watermark-free download
- Progress tracking with callbacks
- Bulk download queue management

### Frontend

#### [NEW] [templates/index.html](file:///d:/yt%20and%20tik%20downloader/templates/index.html)
- Main HTML page with all UI components
- Single/Bulk mode toggle
- URL input, video preview cards, quality selector
- Download progress indicators
- Download history section

#### [NEW] [static/style.css](file:///d:/yt%20and%20tik%20downloader/static/style.css)
- Premium dark theme with glassmorphism
- Gradient accents (purple/blue/pink)
- Smooth animations and transitions
- Responsive grid layout

#### [NEW] [static/script.js](file:///d:/yt%20and%20tik%20downloader/static/script.js)
- Frontend logic for URL submission
- Real-time progress updates via SSE
- Mode switching (single/bulk)
- Download management

### Configuration

#### [NEW] [requirements.txt](file:///d:/yt%20and%20tik%20downloader/requirements.txt)
- flask, yt-dlp, ffmpeg-python

## Verification Plan

### Automated Tests
- Run the Flask server and test with browser
- Test YouTube video URL
- Test TikTok video URL
- Test bulk download with multiple URLs
