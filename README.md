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

## Hosting (important)

**GitHub Pages cannot run this project.**  
GitHub Pages only serves static HTML/CSS/JS. This app is **Django** (Python, database, login, forms, uploads), so it needs a real web host.

Use this flow instead:

1. **Push the code to GitHub** (source control / backup)
2. **Deploy from that GitHub repo to [Render](https://render.com)** (runs Django live)

The live site URL will look like `https://your-service.onrender.com`, not `*.github.io`.

## Push to GitHub

Do **not** commit secrets. `.env`, `.venv/`, and `*.sqlite3` are gitignored.

```bash
# from the project root
git add -A
git status   # confirm .env and .venv are NOT listed
git commit -m "Initial ScholarHub Django app"

# create an empty repo on GitHub, then:
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

Or with GitHub CLI:

```bash
gh repo create scholar-hub --public --source=. --remote=origin --push
```

## Render deployment (live site)

This repo includes a [render.yaml](./render.yaml) Blueprint for a Python web service plus a managed Postgres database.

### What the deployment uses

- Gunicorn for the Django app server
- WhiteNoise for production static files
- Postgres in production through `DATABASE_URL`
- A persistent disk mounted at `/opt/render/project/src/media` for uploaded files

### Deploy steps

1. Push this repo to GitHub (see above).
2. Sign up / log in at [https://render.com](https://render.com) (GitHub login works).
3. Click **New** → **Blueprint**.
4. Select this repository and apply the Blueprint.
5. Wait for the first deploy (build runs `migrate` + `collectstatic`).
6. Open the Render service URL to use the live site.
7. Create a superuser from the Render **Shell** tab:

```bash
python manage.py createsuperuser
```

8. Optional seed data from the same shell:

```bash
python manage.py seed_scholarships
```

### Important environment behavior

- `SECRET_KEY` must be set in production. The Blueprint generates one automatically.
- `DEBUG` is set to `false` in production.
- `ALLOWED_HOSTS` automatically includes Render's hostname when `RENDER_EXTERNAL_HOSTNAME` is present.
- `CSRF_TRUSTED_ORIGINS` automatically includes Render's external URL when `RENDER_EXTERNAL_URL` is present.
- Configure the email variables above in Render as well if you want newsletter welcome emails to reach real inboxes.
- Free Render web services may sleep after idle time; the first request can be slow to wake up.

## Notes

- Local SQLite (`db.sqlite3`) is for development only and is not pushed to GitHub.
- Uploaded files need the persistent disk to survive redeploys on Render.
