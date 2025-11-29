from flask import Flask, jsonify, render_template, request
import sqlite3
import os
import pymongo
from dotenv import load_dotenv

# Load .env file locally
load_dotenv()

app = Flask(__name__)

# -------------------- SQLite (Books) --------------------
DATABASE = os.path.join("db", "books.db")

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn=None):
    close_after = False
    if conn is None:
        conn = get_db()
        close_after = True

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS Books (
        book_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        publication_year INTEGER,
        image_url TEXT
    );

    CREATE TABLE IF NOT EXISTS Authors (
        author_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS book_author (
        book_id INTEGER NOT NULL,
        author_id INTEGER NOT NULL,
        PRIMARY KEY (book_id, author_id),
        FOREIGN KEY (book_id) REFERENCES Books(book_id),
        FOREIGN KEY (author_id) REFERENCES Authors(author_id)
    );
    """)
    conn.commit()
    if close_after:
        conn.close()


# -------------------- MongoDB (Reviews) --------------------
MONGO_URI = os.environ.get("MONGO_URI")

if not MONGO_URI:
    print("⚠ WARNING: MONGO_URI not found in environment variables!")

client = pymongo.MongoClient(MONGO_URI)
mongo_db = client["book_database"]
reviews_collection = mongo_db["reviews"]


# -------------------- HOME PAGE --------------------
@app.route("/")
def index():
    init_db()
    return render_template("index.html")


# -------------------- GET ALL BOOKS --------------------
@app.route("/api/books")
def get_all_books():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT B.book_id, B.title, B.publication_year, B.image_url,
                   COALESCE(GROUP_CONCAT(A.name, ', '), 'Unknown') AS authors
            FROM Books B
            LEFT JOIN book_author BA ON B.book_id = BA.book_id
            LEFT JOIN Authors A ON BA.author_id = A.author_id
            GROUP BY B.book_id
            ORDER BY LOWER(B.title)
        """)
        rows = cursor.fetchall()
        conn.close()

        books = []
        for r in rows:
            books.append({
                "book_id": r[0],
                "title": r[1],
                "publication_year": r[2],
                "image_url": r[3],
                "author": r[4]
            })

        return jsonify({"books": books})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------- ADD BOOK --------------------
@app.route("/api/add_book", methods=["POST"])
def add_book():
    try:
        data = request.get_json(force=True)
        title = (data.get("title") or "").strip()
        author_name = (data.get("author") or "").strip()
        publication_year = data.get("publication_year")
        image_url = (data.get("image_url") or "").strip()

        if not title or not author_name:
            return jsonify({"error": "title and author are required"}), 400

        conn = get_db()
        cur = conn.cursor()

        # Insert book
        cur.execute(
            "INSERT INTO Books (title, publication_year, image_url) VALUES (?, ?, ?)",
            (title, publication_year, image_url)
        )
        book_id = cur.lastrowid

        # Insert/find author
        cur.execute("SELECT author_id FROM Authors WHERE name = ?", (author_name,))
        row = cur.fetchone()
        if row:
            author_id = row[0]
        else:
            cur.execute("INSERT INTO Authors (name) VALUES (?)", (author_name,))
            author_id = cur.lastrowid

        # Link book and author
        cur.execute(
            "INSERT OR IGNORE INTO book_author (book_id, author_id) VALUES (?, ?)",
            (book_id, author_id)
        )

        conn.commit()
        conn.close()

        return jsonify({"message": "Book added", "book_id": book_id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------- SEARCH BOOKS --------------------
@app.route("/api/search")
def search_books():
    try:
        q = (request.args.get("q") or "").strip()
        if not q:
            return jsonify({"books": []})

        pattern = f"%{q}%"
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT B.book_id, B.title, B.publication_year, B.image_url,
                   COALESCE(GROUP_CONCAT(A.name, ', '), 'Unknown') AS authors
            FROM Books B
            LEFT JOIN book_author BA ON B.book_id = BA.book_id
            LEFT JOIN Authors A ON BA.author_id = A.author_id
            WHERE LOWER(B.title) LIKE LOWER(?) OR LOWER(A.name) LIKE LOWER(?)
            GROUP BY B.book_id
        """, (pattern, pattern))

        rows = cursor.fetchall()
        conn.close()

        books = []
        for r in rows:
            books.append({
                "book_id": r[0],
                "title": r[1],
                "publication_year": r[2],
                "image_url": r[3],
                "author": r[4]
            })

        return jsonify({"books": books})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------- GET REVIEWS FOR SPECIFIC BOOK --------------------
@app.route("/api/reviews/<int:book_id>", methods=["GET"])
def get_reviews_for_book(book_id):
    try:
        reviews = list(reviews_collection.find({"book_id": str(book_id)}, {"_id": 0}))
        return jsonify({"reviews": reviews})
    except Exception as e:
        return jsonify({"error": str(e)})


# -------------------- ADD REVIEW --------------------
@app.route("/api/add_review", methods=["POST"])
def add_review():
    try:
        data = request.get_json()

        review = {
            "book_id": str(data.get("book_id")),
            "user": data.get("user"),
            "rating": data.get("rating"),
            "comment": data.get("comment")
        }

        reviews_collection.insert_one(review)

        return jsonify({"message": "Review added"})
    except Exception as e:
        return jsonify({"error": str(e)})


# -------------------- RUN --------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0")
