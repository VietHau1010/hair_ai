from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import TaiKhoan


@admin.register(TaiKhoan)
class QuanTriTaiKhoan(UserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
    )

    search_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
    )

    add_fieldsets = (
        (
            "Tạo tài khoản",
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


admin.site.site_header = "Quản trị HAULONGHAIR"
admin.site.site_title = "HAULONGHAIR"
admin.site.index_title = "Quản lý hệ thống"