FROM python:3.10

WORKDIR /workspace2
COPY . .

RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
RUN pip3 install python-multipart
RUN pip3 install -r requirement.txt

EXPOSE 8001

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]