# Stage 1: Use Python 3.11 to meet the framework's requirements
FROM python:3.11-slim

# Stage 2: Set the working directory in the container
WORKDIR /app

# Stage 3: Set environment variables
ENV IBM_QUANTUM_API_TOKEN=""
ENV GROQ_API_KEY=""
ENV ARXIV_API_BASE="http://export.arxiv.org/api/query"

# Add the agent's path to PYTHONPATH
ENV PYTHONPATH="${PYTHONPATH}:/app/beeai-platform-agent-starter"

# Stage 4: Copy and install all dependencies from PyPI
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 5: Copy the application code into the container
COPY ./beeai-platform-agent-starter/ ./beeai-platform-agent-starter/
COPY app.py .

# Stage 6: Expose the port your app runs on
EXPOSE 5000

# Stage 7: Define the command to run your application
CMD ["python", "-u", "app.py"]