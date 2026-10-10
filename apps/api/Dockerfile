# study-club api 镜像
# 构建上下文 = 仓库根（见 deploy/api/docker-compose.yml 的 context: ../..），
# 因此 COPY 路径以仓库根为基准。
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖，利用镜像层缓存
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码与内容包（内容 JSON 保留为可版本管理的导入种子，运行时真源是 MongoDB）
COPY apps/api/app ./app
COPY content ./content
COPY scripts/seed ./scripts/seed

# 非 root 运行
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
# 素材存储目录（ASSET_DIR）：必须在切用户前建好并授权，
# 否则首次挂载命名卷时卷会以 root 属主创建，appuser 写不进去（上传素材直接 500）。
RUN mkdir -p /app/data/assets && chown -R appuser:appuser /app/data
USER appuser

ENV ASSET_DIR=/app/data/assets

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('API_PORT','8000')+os.environ.get('API_PREFIX','/api/v1')+'/health',timeout=3)" || exit 1

# 端口由 API_PORT 控制（默认 8000）；compose 亦可覆盖 command
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${API_PORT:-8000}"]
