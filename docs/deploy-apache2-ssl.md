# AvaPharmacy Apache2 SSL Deployment

This guide deploys the Django backend to a DigitalOcean Ubuntu droplet using Apache2 with `mod_wsgi` as the Django application server and Certbot for Let's Encrypt SSL.

## Domains

Create DNS `A` records pointing to the droplet public IPv4 address:

```text
app-staging.avapharmacy.co.ke      -> DROPLET_PUBLIC_IP
api-staging.avapharmacy.co.ke      -> DROPLET_PUBLIC_IP
app-production.avapharmacy.co.ke   -> DROPLET_PUBLIC_IP
api-production.avapharmacy.co.ke   -> DROPLET_PUBLIC_IP
```

Wait until all required names resolve before requesting SSL certificates.

## Server Packages

```bash
sudo apt update
sudo apt install -y apache2 libapache2-mod-wsgi-py3 python3-venv python3-pip postgresql postgresql-contrib git certbot python3-certbot-apache
sudo a2enmod wsgi headers rewrite ssl
sudo systemctl restart apache2
```

If UFW is enabled:

```bash
sudo ufw allow OpenSSH
sudo ufw allow "Apache Full"
sudo ufw enable
```

## App User And Folders

```bash
sudo adduser --disabled-password --gecos "" ava
sudo usermod -aG sudo ava
sudo mkdir -p /home/ava/staging /home/ava/production
sudo chown -R ava:ava /home/ava/staging /home/ava/production
```

Clone the repo twice, once per environment:

```bash
sudo -iu ava
git clone git@github.com:YOUR_ORG/YOUR_REPO.git /home/ava/staging/backend
git clone git@github.com:YOUR_ORG/YOUR_REPO.git /home/ava/production/backend
```

If either repo was cloned or copied with `sudo`, fix ownership before deploying:

```bash
sudo chown -R ava:ava /home/ava/staging/backend
sudo chown -R ava:ava /home/ava/production/backend
```

Create virtual environments:

```bash
cd /home/ava/staging/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

cd /home/ava/production/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

## Environment Files

Create separate `.env` files:

```bash
nano /home/ava/staging/backend/.env
nano /home/ava/production/backend/.env
```

Minimum staging values:

```env
DEBUG=False
DJANGO_SETTINGS_MODULE=avapharmacy.settings.production
SECRET_KEY=replace-with-staging-secret
FIELD_ENCRYPTION_KEY=replace-with-staging-fernet-key
DATABASE_NAME=avapharmacy_staging
DATABASE_USER=avapharmacy_staging
DATABASE_PASSWORD=replace-with-db-password
DATABASE_HOST=localhost
DATABASE_PORT=5432
ALLOWED_HOSTS=app-staging.avapharmacy.co.ke,api-staging.avapharmacy.co.ke
CSRF_TRUSTED_ORIGINS=https://app-staging.avapharmacy.co.ke,https://api-staging.avapharmacy.co.ke
CORS_ALLOWED_ORIGINS=https://app-staging.avapharmacy.co.ke,https://api-staging.avapharmacy.co.ke
BACKEND_BASE_URL=https://api-staging.avapharmacy.co.ke
```

Minimum production values:

```env
DEBUG=False
DJANGO_SETTINGS_MODULE=avapharmacy.settings.production
SECRET_KEY=replace-with-production-secret
FIELD_ENCRYPTION_KEY=replace-with-production-fernet-key
DATABASE_NAME=avapharmacy_production
DATABASE_USER=avapharmacy_production
DATABASE_PASSWORD=replace-with-db-password
DATABASE_HOST=localhost
DATABASE_PORT=5432
ALLOWED_HOSTS=app-production.avapharmacy.co.ke,api-production.avapharmacy.co.ke
CSRF_TRUSTED_ORIGINS=https://app-production.avapharmacy.co.ke,https://api-production.avapharmacy.co.ke
CORS_ALLOWED_ORIGINS=https://app-production.avapharmacy.co.ke,https://api-production.avapharmacy.co.ke
BACKEND_BASE_URL=https://api-production.avapharmacy.co.ke
```

Add your payment, email, POS, and frontend URL values from `.env.example`.

## Databases

```bash
sudo -u postgres psql
```

```sql
CREATE USER avapharmacy_staging WITH PASSWORD 'replace-with-db-password';
CREATE DATABASE avapharmacy_staging OWNER avapharmacy_staging;

CREATE USER avapharmacy_production WITH PASSWORD 'replace-with-db-password';
CREATE DATABASE avapharmacy_production OWNER avapharmacy_production;

\q
```

## Deploy Scripts

Allow the deploy user to validate and reload Apache without an interactive password:

```bash
sudo visudo -f /etc/sudoers.d/avapharmacy-deploy
```

Add:

```text
ava ALL=(root) NOPASSWD: /usr/sbin/apache2ctl configtest
ava ALL=(root) NOPASSWD: /bin/systemctl reload apache2
```

Run the first deploy manually:

```bash
sudo -iu ava /home/ava/staging/backend/deploy/scripts/deploy-staging-backend.sh
sudo -iu ava /home/ava/production/backend/deploy/scripts/deploy-production-backend.sh
```

## Apache

```bash
sudo cp /home/ava/staging/backend/deploy/apache/avapharmacy-staging.conf /etc/apache2/sites-available/
sudo cp /home/ava/production/backend/deploy/apache/avapharmacy-production.conf /etc/apache2/sites-available/
sudo a2ensite avapharmacy-staging.conf
sudo a2ensite avapharmacy-production.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

At this point, HTTP should work:

```bash
curl -I http://app-staging.avapharmacy.co.ke
curl -I http://app-production.avapharmacy.co.ke
```

The Apache templates run Django through separate `mod_wsgi` daemon process groups for staging and production. They also send `X-Forwarded-Proto: https`, which matches `SECURE_PROXY_SSL_HEADER` in `avapharmacy.settings.production` and prevents Django HTTPS redirect loops after SSL is enabled.

## SSL

Request certificates and let Certbot update the Apache virtual hosts:

```bash
sudo certbot --apache -d app-staging.avapharmacy.co.ke -d api-staging.avapharmacy.co.ke
sudo certbot --apache -d app-production.avapharmacy.co.ke -d api-production.avapharmacy.co.ke
```

Choose the redirect option so HTTP redirects to HTTPS.

After Certbot finishes, inspect the generated SSL virtual host files:

```bash
sudo grep -R "X-Forwarded-Proto" /etc/apache2/sites-available/
```

For the SSL virtual hosts, the value must be:

```apache
RequestHeader set X-Forwarded-Proto "https"
```

Test renewal:

```bash
sudo certbot renew --dry-run
```

## GitHub Actions Secrets

Create GitHub environments named `staging` and `production`.

For each environment, set:

```text
DROPLET_HOST      droplet public IP or hostname
DROPLET_USER      ava
DROPLET_SSH_KEY   private key allowed to SSH as ava
```

The workflow deploys:

```text
develop       -> staging     -> https://api-staging.avapharmacy.co.ke
main          -> production  -> https://api-production.avapharmacy.co.ke
```

## Useful Logs

```bash
sudo tail -f /var/log/apache2/avapharmacy-staging-error.log
sudo tail -f /var/log/apache2/avapharmacy-production-error.log
```
