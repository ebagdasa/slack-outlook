FROM nginx:1.13.0

RUN apt-get update --assume-yes
RUN apt-get install certbot --assume-yes

RUN mkdir -p /var/www/letsencrypt
RUN mkdir -p /var/www/rooms
RUN mkdir -p /etc/letsencrypt/configs/
RUN mkdir -p /var/log/letsencrypt/
RUN mkdir -p /usr/src

# COPY nginx-http.conf /etc/nginx/nginx-http.conf
COPY nginx-https.conf /etc/nginx/nginx.conf
# COPY nginx-http.conf /etc/nginx/nginx.conf

COPY serve /etc/nginx/html/

COPY roomparking.cornelltech.io.conf /usr/src/roomparking.cornelltech.io.conf
COPY roomparking.cornelltech.io.staged.conf /usr/src/roomparking.cornelltech.io.staged.conf
COPY force_renew_certs.sh /usr/src/force_renew_certs.sh
COPY renew_certificates.sh /usr/src/renew_certificates.sh
COPY renew_certificates_staged.sh /usr/src/renew_certificates_staged.sh
COPY ssl_nginx_conf.sh /usr/src/ssl_nginx_conf.sh

COPY rooms /var/www/rooms

WORKDIR /usr/src