// --------- Small helper functions ----------
function $(id) {
  return document.getElementById(id);
}
function showEl(el) {
  el.classList.remove("hidden");
}
function hideEl(el) {
  el.classList.add("hidden");
}

// Global state
let currentBookId = null;

// ========== BOOKS ==========

async function addBook() {
  const title = $("bookTitle").value.trim();
  const author = $("authorName").value.trim();
  const publication_year = $("publicationYear").value.trim();
  const image_url = $("imageUrl").value.trim();

  if (!title || !author) {
    $("bookList").innerText = "Title and author are required.";
    return;
  }

  try {
    const res = await fetch("/api/add_book", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, author, publication_year, image_url }),
    });

    const data = await res.json();

    if (!res.ok) {
      $("bookList").innerText = data.error || "Failed to add book.";
      return;
    }

    $("bookList").innerHTML = `<div class="text-green-700">✅ Added: <strong>${title}</strong> by ${author}</div>`;
    $("bookTitle").value = "";
    $("authorName").value = "";
    $("publicationYear").value = "";
    $("imageUrl").value = "";

    await loadAllBooks();
  } catch (err) {
    console.error(err);
    $("bookList").innerText = "Error adding book.";
  }
}

function createBookCard(book) {
  const imgHTML = book.image_url
    ? `<img src="${book.image_url}" alt="${book.title} cover" class="w-full h-56 object-cover rounded-xl shadow-sm">`
    : `<div class="w-full h-56 grid place-items-center bg-slate-100 rounded-xl text-slate-400 text-sm">No Cover</div>`;

  const card = document.createElement("article");
  card.className = "book-card p-4 rounded-2xl cursor-pointer";
  card.innerHTML = `
      ${imgHTML}
      <div class="mt-3">
        <h3 class="font-semibold line-clamp-2">${book.title}</h3>
        <p class="text-sm text-slate-600">${book.author || "Unknown"}</p>
        ${
          book.publication_year
            ? `<p class="text-xs text-slate-500 mt-1">Year: ${book.publication_year}</p>`
            : ""
        }
      </div>
  `;

  card.addEventListener("click", () => {
    openReviewModal(book);
  });

  return card;
}

function renderShelf(books) {
  const shelf = $("shelf");
  const empty = $("emptyState");
  shelf.innerHTML = "";

  if (!books || books.length === 0) {
    showEl(empty);
    return;
  }
  hideEl(empty);

  books.forEach((b) => {
    shelf.appendChild(createBookCard(b));
  });
}

async function loadAllBooks() {
  try {
    const res = await fetch("/api/books");
    const data = await res.json();
    renderShelf(data.books || []);
  } catch (err) {
    console.error(err);
  }
}

async function searchBooks() {
  const q = $("searchInput").value.trim();
  if (!q) {
    loadAllBooks();
    return;
  }
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    renderShelf(data.books || []);
  } catch (err) {
    console.error(err);
  }
}

// ========== MODAL LOGIC ==========

const modal = $("reviewModal");
const modalPanel = $("reviewModalPanel");
const modalBackdrop = $("reviewModalBackdrop");

function openReviewModal(book) {
  currentBookId = book.book_id;

  $("modalBookTitle").textContent = book.title;
  $("modalBookAuthor").textContent = book.author || "Unknown author";
  $("modalBookIdText").textContent = `Book ID: ${book.book_id}`;
  $("modalBookId").value = book.book_id;

  $("modalUser").value = "";
  $("modalRating").value = "";
  $("modalComment").value = "";

  // Show backdrop
  modalBackdrop.classList.remove("hidden");
  modalBackdrop.classList.add("opacity-100");

  // Enable pointer events and animate panel in
  modal.classList.remove("pointer-events-none");
  modalPanel.classList.remove("opacity-0", "scale-95", "translate-y-4");
  modalPanel.classList.add("opacity-100", "scale-100", "translate-y-0");

  loadReviewsForBook(book.book_id);
}

function closeReviewModal() {
  // Animate out
  modalPanel.classList.remove("opacity-100", "scale-100", "translate-y-0");
  modalPanel.classList.add("opacity-0", "scale-95", "translate-y-4");

  modalBackdrop.classList.remove("opacity-100");
  modalBackdrop.classList.add("opacity-0");

  // After animation, hide elements completely
  setTimeout(() => {
    modalBackdrop.classList.add("hidden");
    modal.classList.add("pointer-events-none");
  }, 200);
}

$("modalCloseBtn").addEventListener("click", closeReviewModal);
modalBackdrop.addEventListener("click", closeReviewModal);
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeReviewModal();
  }
});

// ========== REVIEWS (MongoDB) ==========

function renderReviews(reviews) {
  const list = $("modalReviewsList");
  list.innerHTML = "";

  if (!reviews || reviews.length === 0) {
    list.innerHTML = `<p class="text-slate-500">No reviews yet.</p>`;
    return;
  }

  reviews.forEach((r) => {
    const card = document.createElement("article");
    card.className = "p-3 rounded-xl bg-slate-50 border border-slate-200";
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <p class="font-semibold text-sm">${r.user || "Anonymous"}</p>
        <span class="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">
          ⭐ ${r.rating || "-"}
        </span>
      </div>
      ${
        r.comment
          ? `<p class="text-sm text-slate-700 mt-1">${r.comment}</p>`
          : ""
      }
    `;
    list.appendChild(card);
  });
}

async function loadReviewsForBook(bookId) {
  try {
    const res = await fetch(`/api/reviews/${bookId}`);
    const data = await res.json();
    if (data.error) {
      console.error(data.error);
      renderReviews([]);
      return;
    }
    renderReviews(data.reviews || []);
  } catch (err) {
    console.error(err);
    renderReviews([]);
  }
}

async function submitReview() {
  const book_id = $("modalBookId").value;
  const user = $("modalUser").value.trim();
  const rating = $("modalRating").value.trim();
  const comment = $("modalComment").value.trim();

  if (!book_id || !user || !rating) {
    alert("Name and rating are required.");
    return;
  }

  try {
    const res = await fetch("/api/add_review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ book_id, user, rating, comment }),
    });
    const data = await res.json();

    if (!res.ok || data.error) {
      alert(data.error || "Failed to add review.");
      return;
    }

    $("modalComment").value = "";
    await loadReviewsForBook(book_id);
  } catch (err) {
    console.error(err);
    alert("Error saving review.");
  }
}

$("modalSubmitBtn").addEventListener("click", submitReview);

// ========== INITIALIZE ==========

window.addEventListener("DOMContentLoaded", () => {
  loadAllBooks();
  $("searchInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") searchBooks();
  });
});
