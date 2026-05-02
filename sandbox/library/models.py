from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nom de l'auteur")
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Année de naissance")

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=300, verbose_name="Titre du livre")
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    published_year = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Année de publication")

    def __str__(self):
        return self.title
