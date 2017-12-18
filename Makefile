connect:
	ssh -i ancile-studybot.pem ubuntu@ec2-54-84-36-244.compute-1.amazonaws.com

request_staging_ssl_certs:
	docker-compose exec nginx bash /usr/src/renew_certificates_staged.sh

request_ssl_certs:
	docker-compose exec nginx bash /usr/src/renew_certificates.sh

force_renew_ssl_certs:
	docker-compose exec nginx bash /usr/src/force_renew_certs.sh

use_existing_ssl:
	docker-compose exec nginx bash /usr/src/ssl_nginx_conf.sh

dev_up:
	docker-compose --file docker-compose-dev.yaml up -d

dev_build:
	docker-compose --file docker-compose-dev.yaml build

dev_logs:
	docker-compose --file docker-compose-dev.yaml logs

dev_down:
	docker-compose --file docker-compose-dev.yaml down

migrate:
	docker-compose exec app python manage.py migrate

createsuperuser:
	docker-compose exec app python manage.py createsuperuser

pg_up:
	docker-compose --file docker-compose-only-pg.yaml up -d

report:
	docker-compose exec bot python manage.py report


retrieve:
	rsync -rave "ssh -i ancile-studybot.pem" ubuntu@ec2-54-84-36-244.compute-1.amazonaws.com:/home/ubuntu/src/ancile-study-slack-bot/ancile-slackbot/retrieved /Users/matthewgriffith/ancile-study-slack-bot/archive