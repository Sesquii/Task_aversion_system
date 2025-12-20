# v0.1.0 - Docker Release: Easy Installation for Everyone

## 🚀 Quick Start

**New users:** Download the ZIP file from this release, extract it, and follow the instructions in `Install_instructions.txt`. No Python knowledge required!

This release adds Docker support, making it possible for anyone to run the Task Aversion System without installing Python or managing dependencies. Just install Docker Desktop and run one command.

## ✨ What's New

- **Docker Support**: Complete containerization with Dockerfile and docker-compose.yml
- **One-Command Setup**: Run `docker-compose up` and you're done
- **Fresh Data for Each User**: Each installation starts with clean, empty data files automatically
- **Beginner-Friendly Guide**: New `Install_instructions.txt` with step-by-step instructions for non-technical users
- **Updated Documentation**: README now includes Docker installation options alongside traditional Python setup

## 📦 Installation Options

**For Non-Technical Users (Recommended):**
1. Download the ZIP from this release
2. Follow `Install_instructions.txt` - it's that simple!

**For Developers:**
- Traditional Python installation still works (see README.md)
- Docker setup available for consistent environments

## 🔧 Technical Details

- Docker image based on Python 3.11-slim
- Data stored in Docker volumes (persists between restarts)
- Excludes developer data from image (users get fresh start)
- Port 8080 (configurable in docker-compose.yml)

## 📝 Notes

This is the first Docker release. The core application functionality remains the same - this release focuses on making installation easier for non-technical users. All existing features work as before.

---

**Need help?** Check `Install_instructions.txt` or open an issue on GitHub.

