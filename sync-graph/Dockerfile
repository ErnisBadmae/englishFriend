FROM python:3.11-slim
WORKDIR /app
COPY sync-graph/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY sync-graph/src /app
ENV PYTHONPATH="/app"
CMD ["python", "-m", "sync_graph.main"]
