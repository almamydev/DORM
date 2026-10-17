import random
from library.models import Author, Book

random.seed(7)
classics = {
    ("J.R.R. Tolkien", 1892): [("The Hobbit", 1937), ("The Fellowship of the Ring", 1954), ("The Two Towers", 1954), ("The Return of the King", 1955)],
    ("Ursula K. Le Guin", 1929): [("A Wizard of Earthsea", 1968), ("The Left Hand of Darkness", 1969), ("The Dispossessed", 1974)],
    ("Isaac Asimov", 1920): [("I, Robot", 1950), ("Foundation", 1951), ("The Caves of Steel", 1954), ("The Gods Themselves", 1972)],
    ("Jane Austen", 1775): [("Sense and Sensibility", 1811), ("Pride and Prejudice", 1813), ("Emma", 1815)],
    ("Victor Hugo", 1802): [("Notre-Dame de Paris", 1831), ("Les Misérables", 1862)],
    ("Albert Camus", 1913): [("L'Étranger", 1942), ("La Peste", 1947)],
    ("Chinua Achebe", 1930): [("Things Fall Apart", 1958), ("Arrow of God", 1964)],
    ("Octavia E. Butler", 1947): [("Kindred", 1979), ("Parable of the Sower", 1993)],
}
authors = []
for (name, born), books in classics.items():
    a = Author.objects.create(name=name, birth_year=born)
    authors.append(a)
    Book.objects.bulk_create(Book(title=t, author=a, published_year=y) for t, y in books)

adj  = ["Silent", "Hidden", "Last", "Burning", "Distant", "Golden", "Broken", "Northern", "Iron", "Quiet", "Endless", "Crimson"]
noun = ["Harbor", "Archive", "Garden", "River", "Empire", "Lantern", "Orchard", "Signal", "Kingdom", "Atlas", "Tide", "Citadel"]
tail = ["", " II", " III", ": A Novel", " Stories", " Revisited"]
Book.objects.bulk_create(
    Book(title=f"The {random.choice(adj)} {random.choice(noun)}{random.choice(tail)}",
         author=random.choice(authors), published_year=random.randint(1900, 2024))
    for _ in range(1800)
)
print(Author.objects.count(), "authors,", Book.objects.count(), "books")
