# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install the dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on. Cloud Run will automatically use this port.
EXPOSE 8080

# Define the command to run the application.
# Cloud Run will set the PORT environment variable, but uvicorn doesn't directly use it in this CMD format.
# We are hardcoding the port to 8080, which is a common practice for Cloud Run.
# Make sure to configure your Cloud Run service to send requests to container port 8080.
CMD ["uvicorn", "api:api", "--host", "0.0.0.0", "--port", "8080"]
