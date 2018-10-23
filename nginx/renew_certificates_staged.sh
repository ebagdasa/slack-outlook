#!/bin/sh

certbot --config /usr/src/roomparking.cornelltech.io.staged.conf certonly --non-interactive --keep-until-expiring --agree-tos

if [ $? -ne 0 ]
 then
        ERRORLOG=`tail /var/log/letsencrypt/letsencrypt.log`
        echo -e "The Let's Encrypt cert has not been renewed! \n \n" \
                 $ERRORLOG
 else
        yes | cp -rf /etc/nginx/nginx-https.conf /etc/nginx/nginx.conf;
        nginx -s reload;
fi

exit 0