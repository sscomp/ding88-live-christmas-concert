FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 複製專案檔案
COPY . .

# 環境變數
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# 對外開放的 Port（實際仍以 Zeabur 注入的 PORT 為準）
EXPOSE 8080

# 啟動你的後端（同時負責前端 + API + admin）
CMD ["python", "app.py"]