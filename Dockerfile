# Stage 1: Use a specific, slim Python version
FROM python:3.11-slim

# Stage 2: Set the working directory in the container
WORKDIR /app

# Stage 3: Copy and install dependencies first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 4: Copy your application code
COPY app.py .

# Stage 5: Expose the port your app runs on
EXPOSE 5000

# Stage 6: Define the command to run your application
CMD ["python", "-u", "app.py"]