from django.conf import settings
from django.db import models


class AnhDaChup(models.Model):
    chu_so_huu = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="anh_da_chup",
    )

    ten = models.CharField(
        max_length=120,
        default="Ảnh thử tóc",
    )

    ten_tep = models.CharField(
        max_length=40,
        unique=True,
    )

    kieu = models.CharField(
        max_length=16,
        default="don",
    )

    chieu_rong = models.PositiveIntegerField()
    chieu_cao = models.PositiveIntegerField()

    tao_luc = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-tao_luc", "-pk"]
        verbose_name = "Ảnh đã chụp"
        verbose_name_plural = "Ảnh đã chụp"

    def __str__(self):
        return self.ten