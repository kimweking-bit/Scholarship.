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

## Notes

- The repository still has a stale `Dashboard/db.sqlite3` file locked by another process. The live app now uses the root-level `db.sqlite3`.
- Uploaded files need the persistent disk to survive redeploys on Render.
