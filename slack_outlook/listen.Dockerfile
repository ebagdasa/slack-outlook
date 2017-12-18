FROM python:3.6

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		postgresql-client \
		libxmlsec1 \
		xmlsec1 \
		libxmlsec1-dev \
	&& rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app
COPY ./requirements.txt ./
RUN pip install -r requirements.txt
COPY . .

CMD ["python", "manage.py", "listen"]

