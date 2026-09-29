<div align="center">

# 📚 Athenaeum

**A personal library collection manager with global book search,<br>JWT authentication, and star ratings.**

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![JWT](https://img.shields.io/badge/JWT_Auth-HS256-E7A500?style=for-the-badge&logo=jsonwebtokens&logoColor=white)
![Open Library](https://img.shields.io/badge/Open_Library-API-8B5CF6?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)

*Search real books · Save favorites · Rate with stars · Dark mode built in*

</div>

---

## 🖼️ Screenshots

<!-- Drop your screenshots into a /docs folder, then update the paths below -->
<!-- | Catalog | Global Search | Details & Ratings | -->
<!-- |---|---|---| -->
<!-- | ![Catalog](docs/catalog.png) | ![Search](docs/search.png) | ![Details](docs/details.png) | -->

---

## ✨ Features

| | Feature | What you get |
|:---:|---|---|
| 📖 | **Full CRUD Catalog** | Add, edit, and delete books — title, author, year, genre |
| 🔍 | **Instant Library Search** | Case-insensitive title search + sort by publication year |
| 🌐 | **Global Database Search** | Find real books via the [Open Library API](https://openlibrary.org/developers/api), filtered by genre |
| 🖼️ | **Rich Book Details** | Cover art, landscape detail view, and fetched descriptions |
| ❤️ | **Favorites** | Save any discovery with one click |
| 🗂️ | **Collections** | Group saved books into named collections with safe deletion |
| 🔐 | **JWT Authentication** | Signup / login / logout with HttpOnly cookie tokens |
| ⭐ | **Star Ratings** | Logged-in users rate 1–5; live averages shown to everyone |
| 🌗 | **Dark / Light Theme** | Persists across visits |
| ⌨️ | **Keyboard Shortcuts** | `/`, `Ctrl/Cmd+K`, `Enter`, `Esc` |
| 💬 | **Toast Notifications** | Dismissible flash messages that auto-hide |
| ♿ | **Accessible & Responsive** | ARIA labels, `aria-live` regions, reduced-motion support, flip-to-fit dropdowns |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | ![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat&logo=python&logoColor=white) ![Flask](https://img.shields.io/badge/Flask-3.x-black?style=flat&logo=flask&logoColor=white) |
| Database | ![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white) via the standard `sqlite3` module |
| Auth | ![PyJWT](https://img.shields.io/badge/PyJWT-E7A500?style=flat&logo=jsonwebtokens&logoColor=white) + Werkzeug password hashing |
| Frontend | Vanilla HTML / CSS / JS with Jinja2 — **no ORM, no framework, no build step** |
| External API | [Open Library](https://openlibrary.org) — search, covers, descriptions |

---

## 🚀 Quick Start

> 📝 **Note:**
> The SQLite database — including the `users` and `ratings` tables — is created and migrated **automatically** on first run. No manual setup required.

```bash
git clone <your-repo-url> athenaeum
cd athenaeum

python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate

pip install -r requirements.txt
python app.py

Then open http://127.0.0.1:5000 🎉