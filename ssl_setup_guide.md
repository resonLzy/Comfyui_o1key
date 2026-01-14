# SSL 证书配置指南 - api.o1key.com

## 第一步：检查服务器上的 Web 服务器

在 Vultr 服务器上执行以下命令，检查运行的是什么服务：

```bash
# 检查 Nginx
sudo systemctl status nginx

# 检查 Apache
sudo systemctl status apache2

# 检查是否有其他 Web 服务器
sudo netstat -tlnp | grep :443
sudo netstat -tlnp | grep :80
```

---

## 第二步：从 Cloudflare 下载证书

1. 在 Cloudflare 控制台点击 "Create" 生成证书
2. 复制 **Origin Certificate** 的内容
3. 复制 **Private Key** 的内容
4. 保存到本地（稍后上传到服务器）

---

## 第三步：根据 Web 服务器类型配置

### 情况 A：使用 Nginx

#### 1. 安装 Nginx（如果还没安装）
```bash
sudo apt update
sudo apt install nginx -y
```

#### 2. 创建证书目录并上传证书
```bash
# 创建目录
sudo mkdir -p /etc/nginx/ssl

# 创建证书文件（用你从 Cloudflare 复制的 Origin Certificate 内容替换）
sudo nano /etc/nginx/ssl/api.o1key.com.crt
# 粘贴 Origin Certificate 的内容，保存退出（Ctrl+X, Y, Enter）

# 创建私钥文件（用你从 Cloudflare 复制的 Private Key 内容替换）
sudo nano /etc/nginx/ssl/api.o1key.com.key
# 粘贴 Private Key 的内容，保存退出

# 设置权限
sudo chmod 600 /etc/nginx/ssl/api.o1key.com.key
sudo chmod 644 /etc/nginx/ssl/api.o1key.com.crt
```

#### 3. 配置 Nginx
```bash
sudo nano /etc/nginx/sites-available/api.o1key.com
```

粘贴以下配置（根据你的实际后端端口修改）：
```nginx
server {
    listen 443 ssl http2;
    server_name api.o1key.com;

    ssl_certificate /etc/nginx/ssl/api.o1key.com.crt;
    ssl_certificate_key /etc/nginx/ssl/api.o1key.com.key;

    # SSL 配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # 增加超时时间（重要！）
    proxy_connect_timeout 600s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;
    send_timeout 600s;

    # API 代理配置
    location / {
        proxy_pass http://localhost:你的后端端口;  # 改成你的实际后端端口
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 支持大文件上传
        client_max_body_size 100M;
    }
}

# HTTP 重定向到 HTTPS
server {
    listen 80;
    server_name api.o1key.com;
    return 301 https://$server_name$request_uri;
}
```

#### 4. 启用配置并重启
```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/api.o1key.com /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx

# 检查状态
sudo systemctl status nginx
```

---

### 情况 B：使用 Apache

#### 1. 安装 Apache（如果还没安装）
```bash
sudo apt update
sudo apt install apache2 -y
sudo apt install libapache2-mod-ssl -y
```

#### 2. 创建证书目录并上传证书
```bash
# 创建目录
sudo mkdir -p /etc/apache2/ssl

# 创建证书文件
sudo nano /etc/apache2/ssl/api.o1key.com.crt
# 粘贴 Origin Certificate 的内容

# 创建私钥文件
sudo nano /etc/apache2/ssl/api.o1key.com.key
# 粘贴 Private Key 的内容

# 设置权限
sudo chmod 600 /etc/apache2/ssl/api.o1key.com.key
sudo chmod 644 /etc/apache2/ssl/api.o1key.com.crt
```

#### 3. 配置 Apache
```bash
sudo nano /etc/apache2/sites-available/api.o1key.com.conf
```

粘贴以下配置：
```apache
<VirtualHost *:443>
    ServerName api.o1key.com

    SSLEngine on
    SSLCertificateFile /etc/apache2/ssl/api.o1key.com.crt
    SSLCertificateKeyFile /etc/apache2/ssl/api.o1key.com.key

    # SSL 配置
    SSLProtocol all -SSLv2 -SSLv3
    SSLCipherSuite HIGH:!aNULL:!MD5

    # 增加超时时间（重要！）
    Timeout 600
    ProxyTimeout 600

    # API 代理配置
    ProxyPreserveHost On
    ProxyPass / http://localhost:你的后端端口/  # 改成你的实际后端端口
    ProxyPassReverse / http://localhost:你的后端端口/

    # 支持大文件上传
    LimitRequestBody 104857600
</VirtualHost>

# HTTP 重定向到 HTTPS
<VirtualHost *:80>
    ServerName api.o1key.com
    Redirect permanent / https://api.o1key.com/
</VirtualHost>
```

#### 4. 启用配置并重启
```bash
# 启用 SSL 模块
sudo a2enmod ssl
sudo a2enmod proxy
sudo a2enmod proxy_http

# 启用站点
sudo a2ensite api.o1key.com.conf

# 测试配置
sudo apache2ctl configtest

# 重启 Apache
sudo systemctl restart apache2

# 检查状态
sudo systemctl status apache2
```

---

### 情况 C：还没有 Web 服务器

如果你还没有配置 Web 服务器，推荐使用 Nginx（更轻量，适合 API 代理）：

```bash
# 安装 Nginx
sudo apt update
sudo apt install nginx -y

# 然后按照上面的 "情况 A：使用 Nginx" 步骤继续
```

---

## 第四步：测试连接

配置完成后，测试 SSL 连接：

```bash
# 测试 HTTPS 连接
curl -v https://api.o1key.com

# 或者用浏览器访问
# https://api.o1key.com
```

如果看到 SSL 握手成功，说明配置正确！

---

## 第五步：修改代码使用 api.o1key.com

配置完成后，把代码改回使用 `api.o1key.com`：

```python
base_url = "https://api.o1key.com"
```

---

## 常见问题

### 1. 证书文件权限错误
```bash
sudo chmod 600 /etc/nginx/ssl/api.o1key.com.key
sudo chmod 644 /etc/nginx/ssl/api.o1key.com.crt
```

### 2. 端口被占用
```bash
# 检查 443 端口
sudo netstat -tlnp | grep :443
```

### 3. 防火墙未开放 443 端口
```bash
# UFW
sudo ufw allow 443/tcp

# 或者 iptables
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

---

## 需要帮助？

告诉我：
1. 你的服务器上运行的是什么 Web 服务器？
2. 你的后端服务运行在哪个端口？
3. 遇到什么错误？

我可以帮你具体配置！
