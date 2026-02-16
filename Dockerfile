FROM public.ecr.aws/lambda/python:3.11

# Prevent Python from writing .pyc files and buffer logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy requirements first (better caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy function code
COPY aws_lambda.py .
COPY src/ src/

# Lambda handler
CMD ["aws_lambda.lambda_handler"]

