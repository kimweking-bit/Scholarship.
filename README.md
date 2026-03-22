# Scholarship Dashboard

This project is a Django application for browsing scholarships, applying online, and managing student and admin dashboards.

## Local run

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run migrations:

```bash
python manage.py migrate
```

4. Start the development server:

```bash
python manage.py runserver
```

The app uses SQLite locally unless you set `DATABASE_URL`.

### Email and newsletter setup

Newsletter subscriptions now store subscriber emails in Django and send a branded welcome email. To make delivery work outside local development, configure SMTP-style environment variables:

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.your-provider.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-smtp-user
EMAIL_HOST_PASSWORD=your-smtp-password
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=ScholarHub <hello@your-domain.com>
SUPPORT_EMAIL=support@your-domain.com
SITE_URL=https://your-live-domain.com
```

For local testing, you can keep `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` so emails print to the terminal instead of going out to a real inbox.
The app now auto-loads a root `.env` file, so copying `.env.example` to `.env` is enough for local email setup.

To verify delivery after you add real SMTP credentials, run:

```bash
python manage.py email_doctor --connect
python manage.py send_test_email --to you@example.com
```

If you want the email to include a real dashboard link for an existing account, add:

```bash
python manage.py send_test_email --to you@example.com --user your_username
```

## Render deployment

This repo includes a [render.yaml](./render.yaml) Blueprint for a Python web service plus a managed Postgres database.

### What the deployment uses

- Gunicorn for the Django app server
- WhiteNoise for production static files
- Postgres in production through `DATABASE_URL`
- A persistent disk mounted at `/opt/render/project/src/media` for uploaded files

### Deploy steps

1. Push this repo to GitHub.
2. In Render, click `New` -> `Blueprint`.
3. Select this repository and apply the Blueprint.
4. The Blueprint build runs migrations and collects static files automatically.
5. After the first deploy, create a superuser from the Render shell:

```bash
python manage.py createsuperuser
```

6. If you want seed data, run your preferred management commands from the Render shell, for example:

```bash
python manage.py seed_scholarships
```

### Important environment behavior

- `SECRET_KEY` must be set in production. The Blueprint generates one automatically.
- `DEBUG` is set to `false` in production.
- `ALLOWED_HOSTS` automatically includes Render's hostname when `RENDER_EXTERNAL_HOSTNAME` is present.
- `CSRF_TRUSTED_ORIGINS` automatically includes Render's external URL when `RENDER_EXTERNAL_URL` is present.
- Configure the email variables above in Render as well if you want newsletter welcome emails to reach real inboxes.

## Notes

- The repository still has a stale `Dashboard/db.sqlite3` file locked by another process. The live app now uses the root-level `db.sqlite3`.
- Uploaded files need the persistent disk to survive redeploys on Render.
