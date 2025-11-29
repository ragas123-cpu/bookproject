import json
import pytest
import app as flask_app

# -------------------------------------------------
# ✅ Flask test client with temp SQLite DB
# -------------------------------------------------
@pytest.fixture()
def client(tmp_path):
    # Use a fresh, temporary SQLite database for each test
    flask_app.DATABASE = str(tmp_path / "test.db")
    conn = flask_app.get_db()
    flask_app.init_db(conn)
    conn.close()

    # Use test client for HTTP routes
    with flask_app.app.test_client() as c:
        yield c

# -------------------------------------------------
# 📚 Existing Book Functionality Tests
# -------------------------------------------------

def test_add_book_stores_title_author_image(client):
    data = {
        "title": "Clean Code",
        "author": "Robert C. Martin",
        "publication_year": 2008,
        "image_url": "https://covers.openlibrary.org/b/isbn/9780132350884-L.jpg"
    }
    r = client.post("/api/add_book", data=json.dumps(data), content_type="application/json")
    assert r.status_code in (200, 201)

    res = client.get("/api/books")
    books = res.get_json()["books"]

    found = any(
        b["title"] == "Clean Code" and
        "Robert C. Martin" in b["author"] and
        b["image_url"].endswith("9780132350884-L.jpg")
        for b in books
    )
    assert found, "Book title/author/image not stored correctly"

def test_search_by_title_returns_correct_result(client):
    client.post("/api/add_book", data=json.dumps({
        "title": "Refactoring",
        "author": "Martin Fowler",
        "image_url": "https://covers.openlibrary.org/b/isbn/9780134757599-L.jpg"
    }), content_type="application/json")

    r = client.get("/api/search?q=Refactoring")
    data = r.get_json()
    assert any(b["title"] == "Refactoring" for b in data["books"])

def test_search_by_author_returns_correct_result(client):
    client.post("/api/add_book", data=json.dumps({
        "title": "Clean Architecture",
        "author": "Robert C. Martin",
        "image_url": "https://covers.openlibrary.org/b/isbn/9780134494166-L.jpg"
    }), content_type="application/json")

    r = client.get("/api/search?q=Robert C. Martin")
    data = r.get_json()
    assert any("Robert C. Martin" in b["author"] for b in data["books"])

def test_search_nonexistent_returns_empty(client):
    r = client.get("/api/search?q=DoesNotExist12345")
    data = r.get_json()
    assert data["books"] == []

# -------------------------------------------------
# 🟡 New Tests — MongoDB Reviews Integration
# -------------------------------------------------

def test_add_review_and_fetch_from_mongodb(client):
    """
    Tests that adding a review stores it in MongoDB and /api/reviews returns it.
    """
    # 1️⃣ Add a book first, to have a valid book_id
    book_data = {
        "title": "Test Book for Reviews",
        "author": "Jane Doe",
        "publication_year": 2024,
        "image_url": "http://example.com/test.jpg"
    }
    r = client.post("/api/add_book", data=json.dumps(book_data), content_type="application/json")
    assert r.status_code in (200, 201)

    # Fetch books to get the actual book_id
    res = client.get("/api/books")
    books = res.get_json()["books"]
    book_id = books[0]["book_id"]

    # 2️⃣ Add a review to MongoDB
    review_data = {
        "book_id": str(book_id),
        "user": "TestUser",
        "rating": 5,
        "comment": "Excellent book!"
    }
    r2 = client.post("/api/add_review", data=json.dumps(review_data), content_type="application/json")
    assert r2.status_code in (200, 201)
    msg = r2.get_json()
    assert "successfully" in msg["message"].lower()

    # 3️⃣ Fetch all reviews to verify it was stored
    r3 = client.get("/api/reviews")
    assert r3.status_code == 200
    reviews = r3.get_json()["reviews"]

    found = any(
        rev["book_id"] == str(book_id) and
        rev["user"] == "TestUser" and
        rev["rating"] == 5 and
        "Excellent book!" in rev["comment"]
        for rev in reviews
    )
    assert found, "Review not stored/retrieved correctly from MongoDB"

def test_multiple_reviews_for_same_book(client):
    """
    Tests that multiple reviews for the same book are stored and retrieved correctly.
    """
    # Add a book
    r = client.post("/api/add_book", data=json.dumps({
        "title": "Multi-Review Book",
        "author": "John Writer",
        "publication_year": 2025
    }), content_type="application/json")
    assert r.status_code in (200, 201)

    res = client.get("/api/books")
    book_id = res.get_json()["books"][0]["book_id"]

    # Add two reviews
    reviews_to_add = [
        {"book_id": str(book_id), "user": "UserA", "rating": 4, "comment": "Good read."},
        {"book_id": str(book_id), "user": "UserB", "rating": 5, "comment": "Loved it!"}
    ]
    for rev in reviews_to_add:
        client.post("/api/add_review", data=json.dumps(rev), content_type="application/json")

    # Fetch all reviews and check both exist
    r3 = client.get("/api/reviews")
    all_reviews = r3.get_json()["reviews"]

    users_found = {rev["user"] for rev in all_reviews if rev["book_id"] == str(book_id)}
    assert {"UserA", "UserB"}.issubset(users_found), "Multiple reviews not retrieved correctly"
