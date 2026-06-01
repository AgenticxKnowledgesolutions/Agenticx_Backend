from django.db import models

class Review(models.Model):
    SOURCE_CHOICES = [
        ('google', 'Google'),
        ('internal', 'Internal'),
    ]

    name = models.CharField(max_length=255)
    rating = models.IntegerField()
    review = models.TextField()
    role = models.CharField(max_length=255, blank=True, null=True)
    image = models.URLField(blank=True, null=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='internal')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.rating})"
