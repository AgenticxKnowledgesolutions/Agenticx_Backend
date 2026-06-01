from django.db import models

class Activity(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    image = models.CharField(max_length=500, blank=True, null=True) # supports URLs or paths
    duration = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_free = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Activities"
        ordering = ['-created_at']

    def __str__(self):
        return self.title
