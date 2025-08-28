# Use an official Python runtime as a parent image
FROM python:3.8-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code to the working directory
COPY . .

# Make port 5000 available to the world outside this container
#EXPOSE 8080

RUN mkdir -p /app/certs
COPY certs/ca.pem /app/certs/ca-pem

# Define environment variable
ENV FLASK_APP run.py
ENV FLASK_ENV production

# Run the app. gunicorn is a production-ready WSGI server.

CMD ["gunicorn", "--bind", "0.0.0.0:${PORT}", "run:app"] 