FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖 (jieba 可能需要 C++ 编译器, pdfplumber 需要 libstdc++)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data/chroma /app/data/uploads

EXPOSE 8000

CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8000", "--no-reload"]
