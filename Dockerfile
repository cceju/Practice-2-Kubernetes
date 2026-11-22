# RPC server from Practice 1. Standard library only: no pip install needed.
FROM python:3.12-slim

WORKDIR /app

# Logs straight to stdout/stderr so `kubectl logs` shows them immediately
ENV PYTHONUNBUFFERED=1

# Do not run as root inside the container
RUN useradd --create-home --uid 10001 rpc

# Only what the server needs (client/tests stay out of the image).
# --chown so the non-root user can read the code whatever the host permissions.
COPY --chown=rpc:rpc common/ common/
COPY --chown=rpc:rpc server/ server/

USER rpc

EXPOSE 5000

CMD ["python", "server/server.py"]
