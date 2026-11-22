# Deploying PandoraV2 on PythonAnywhere

PandoraV2 is a separate copy of Pandora. It has its own database, its own `.env` and its own Git repository, so nothing here touches the original Pandora.

## Why SQLite on PythonAnywhere

Django 6.1 only works with MySQL 8.4 or newer. Check PythonAnywhere's version in a MySQL console with `SELECT VERSION();`. If it is older than 8.4, use SQLite, which needs no setup: set `PANDORA_DB_ENGINE=sqlite`. Locally you can keep using MySQL.

Backups work on PythonAnywhere too: an admin clicks **Back up now** in **Settings** (the gear icon), and copies are kept in `~/pandora-backups` (last seven days). For a daily backup, add a scheduled task in the **Tasks** tab: `cd ~/PandoraV2/projectsite && ~/.virtualenvs/pandorav2/bin/python manage.py backup_pandora` (adjust the path to where you cloned it). For a copy off the server, download a backup from `~/pandora-backups` in the Files tab.

## 1. Put the code on GitHub

Create a new, empty GitHub repository (for example `PandoraV2`), then on your computer:

```powershell
cd C:\Users\daven\OneDrive\Desktop\GithubRepos\PandoraV2
git add .
git commit -m "PandoraV2: REST API, OpenStreetMap geocoding and Leaflet map"
git remote add origin https://github.com/<you>/PandoraV2.git
git push -u origin main
```

## 2. Clone and install on PythonAnywhere

Open a **Bash console** on PythonAnywhere:

```bash
git clone https://github.com/<you>/PandoraV2.git
cd PandoraV2
mkvirtualenv pandorav2 --python=python3.13
pip install -r projectsite/requirements.txt
```

Use Python 3.12 or newer (Django 6.1 requires it). Pick the newest version PythonAnywhere offers.

## 3. Create the `.env` file

```bash
cd ~/PandoraV2/projectsite
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(50))"
nano .env
```

Uncomment the PythonAnywhere lines, paste the random string after `PANDORA_SECRET_KEY=`, and replace `yourusername` with your PythonAnywhere username.

## 4. Create the database and accounts

```bash
cd ~/PandoraV2/projectsite
python manage.py migrate
python manage.py configure_pandora_roles
python manage.py createsuperuser
python manage.py create_demo_accounts
python manage.py collectstatic --noinput
```

## 5. Set up the web app

On the **Web** tab: *Add a new web app* → *Manual configuration* → the same Python version.

- **Source code:** `/home/<you>/PandoraV2/projectsite`
- **Virtualenv:** `/home/<you>/.virtualenvs/pandorav2`
- **Static files:** URL `/static/` → directory `/home/<you>/PandoraV2/projectsite/staticfiles`
- **Force HTTPS:** on

Open the **WSGI configuration file** link, delete everything in it, and paste:

```python
import os
import sys

path = '/home/<you>/PandoraV2/projectsite'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'projectsite.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Click **Reload**, then open `https://<you>.pythonanywhere.com`.

## 6. Updating later

```bash
cd ~/PandoraV2 && git pull
workon pandorav2
cd projectsite && python manage.py migrate && python manage.py collectstatic --noinput
```

Then click **Reload** on the Web tab.

## Installing as an app (PWA)

Pandora can be installed like an app. It needs HTTPS, so keep **Force HTTPS** on. Open the site in Chrome or Edge and choose **Install** from the address bar or menu. On iPhone, open it in Safari and choose **Share → Add to Home Screen**.

Don't add a PythonAnywhere static mapping for `/sw.js` or `/manifest.webmanifest`. Django serves both from the site root, so the service worker covers every page. The icons are in `/static/` and get collected by `collectstatic`. Store pages are never cached, so the app still needs a connection; when offline it shows a "You are offline" page.

## Lab requirements: where to find each one

| Requirement | Where |
| --- | --- |
| CRUD on 7+ tables | `/api/` — categories, products, suppliers, expense-categories, branches, customers, warranty-claims (also in `/admin/`) |
| RESTful API | Django REST Framework, `pandoraapp/api.py`. Open `/api/` while signed in to use the browsable API, or use Basic auth from Postman. `?q=` searches. |
| External API | OpenStreetMap Nominatim geocoding, `pandoraapp/geocode.py`. When a supplier, branch or customer is saved with a new address, its latitude and longitude are looked up. |
| Leaflet.js + OpenStreetMap | `/map/` (sidebar → **Map**), `templates/pandoraapp/map.html` |

**Free-account note:** free PythonAnywhere accounts can only reach websites on their allowlist. If addresses never get coordinates on the live site, check that `nominatim.openstreetmap.org` is on the [allowlist](https://www.pythonanywhere.com/whitelist/). You can still type the latitude and longitude by hand. Map tiles load in the visitor's browser, so the map works either way.
