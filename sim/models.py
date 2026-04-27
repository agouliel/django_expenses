from django.db import models

class User(models.Model):
    id = models.TextField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    google_calendar_token = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "tbl_users"

    def __str__(self):
        return self.username

class Expense(models.Model):
    id = models.TextField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="expenses",
        db_column="user_id",
        blank=True,
        null=True,
    )
    date_start = models.TextField(blank=True, null=True)
    hashtag = models.TextField(blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    amount = models.FloatField(blank=True, null=True)
    url = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "tbl_expenses"

    def __str__(self):
        return f"{self.summary} ({self.amount})"
