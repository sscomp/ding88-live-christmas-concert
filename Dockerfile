# 用輕量版 Nginx
FROM nginx:alpine

# 刪掉預設頁面與預設設定
RUN rm -rf /usr/share/nginx/html/* \
    && rm /etc/nginx/conf.d/default.conf

# 放入我們自己的設定，讓 Nginx 聽 8080 port
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 把靜態檔案複製進去
COPY . /usr/share/nginx/html

# 告訴外界這個容器用 8080
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
