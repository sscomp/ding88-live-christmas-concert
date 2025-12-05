# 使用輕量版 Nginx
FROM nginx:alpine

# 刪掉預設網頁
RUN rm -rf /usr/share/nginx/html/*

# 把目前資料夾的檔案複製進去
COPY . /usr/share/nginx/html

# Nginx 預設對外是 80 port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
