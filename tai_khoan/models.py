from django.contrib.auth.models import AbstractUser
from django.db import models


class TaiKhoan(AbstractUser):
    email = models.EmailField(
        "Địa chỉ thư điện tử",
        unique=True,
    )

    class Meta:
        verbose_name = "Tài khoản"
        verbose_name_plural = "Tài khoản"

    def __str__(self):
        return self.get_full_name() or self.username