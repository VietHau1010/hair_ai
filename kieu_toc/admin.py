from django.contrib import admin

from .models import DangKhuonMat, KieuToc


@admin.register(DangKhuonMat)
class QuanTriDangKhuonMat(admin.ModelAdmin):
    list_display = ("ten_dang_mat",)

    @admin.display(description="Dạng khuôn mặt")
    def ten_dang_mat(self, doi_tuong):
        return doi_tuong.get_ma_display()


@admin.register(KieuToc)
class QuanTriKieuToc(admin.ModelAdmin):
    list_display = (
        "ten",
        "cac_dang_mat",
        "co_anh_thu_toc",
        "thu_tu",
        "hien_thi",
    )

    list_filter = (
        "hien_thi",
        "dang_mat_phu_hop",
    )

    search_fields = ("ten", "mo_ta")

    filter_horizontal = ("dang_mat_phu_hop",)

    readonly_fields = (
        "ngay_tao",
        "ngay_cap_nhat",
    )

    fieldsets = (
        (
            "Thông tin kiểu tóc",
            {
                "fields": (
                    "ten",
                    "mo_ta",
                    "anh_gioi_thieu",
                    "dang_mat_phu_hop",
                ),
            },
        ),
        (
            "Ảnh và vị trí ghép tóc",
            {
                "fields": (
                    "anh_thu_toc",
                    "diem_neo_x",
                    "diem_neo_y",
                    "ti_le_chieu_rong",
                    "do_lech_x",
                    "do_lech_y",
                ),
                "description": (
                    "Giữ thông số mặc định trước. "
                    "Sẽ chỉnh khi triển khai thử tóc trực tiếp."
                ),
            },
        ),
        (
            "Hiển thị",
            {
                "fields": (
                    "thu_tu",
                    "hien_thi",
                    "ngay_tao",
                    "ngay_cap_nhat",
                ),
            },
        ),
    )

    @admin.display(description="Dạng mặt phù hợp")
    def cac_dang_mat(self, doi_tuong):
        return ", ".join(
            str(dang_mat)
            for dang_mat in doi_tuong.dang_mat_phu_hop.all()
        )

    @admin.display(
        boolean=True,
        description="Có ảnh thử tóc",
    )
    def co_anh_thu_toc(self, doi_tuong):
        return bool(doi_tuong.anh_thu_toc)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            "dang_mat_phu_hop"
        )