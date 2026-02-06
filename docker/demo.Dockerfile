FROM rayproject/ray:2.9.0-py310-gpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set up work directory
WORKDIR /app

# Copy source code
COPY src /app/src

# Add /app to PYTHONPATH so src/demo/main.py can be found easily
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Default command (can be overridden)
CMD ["python", "src/demo/main.py"]
