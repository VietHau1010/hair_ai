"""Nạp giao diện quản trị từ thư mục hiện có của dự án."""

from copy import deepcopy

from django.template.loaders.filesystem import Loader as BoNapTep


class BoNapGiaoDien(BoNapTep):
    CAC_TEN_THAY_THE = {
        "admin/base_site.html": (
            "thu_toc/quan_tri/khung_quan_tri.html"
        ),
        "admin/index.html": (
            "thu_toc/quan_tri/tong_quan.html"
        ),
        "admin/app_index.html": (
            "thu_toc/quan_tri/nhom_du_lieu.html"
        ),

        # Các lệnh extends bên trong HTML quản trị.
        "quan_tri/khung_quan_tri.html": (
            "thu_toc/quan_tri/khung_quan_tri.html"
        ),
        "quan_tri/tong_quan.html": (
            "thu_toc/quan_tri/tong_quan.html"
        ),
        "quan_tri/nhom_du_lieu.html": (
            "thu_toc/quan_tri/nhom_du_lieu.html"
        ),
    }

    def get_template_sources(self, template_name):
        ten_tep = self.CAC_TEN_THAY_THE.get(
            template_name,
            template_name,
        )

        yield from super().get_template_sources(ten_tep)


def cai_dat_bo_nap(cac_cau_hinh):
    ket_qua = deepcopy(cac_cau_hinh)

    for cau_hinh in ket_qua:
        if (
            cau_hinh.get("BACKEND")
            != "django.template.backends.django.DjangoTemplates"
        ):
            continue

        tuy_chon = cau_hinh.setdefault("OPTIONS", {})
        cac_bo_nap = tuy_chon.get("loaders")

        if cac_bo_nap is None:
            cac_bo_nap = [
                "django.template.loaders.filesystem.Loader",
            ]

            if cau_hinh.get("APP_DIRS", False):
                cac_bo_nap.append(
                    "django.template.loaders.app_directories.Loader"
                )

        # Tránh thêm trùng nếu hàm được gọi lại.
        ten_bo_nap = "config.bo_nap_giao_dien.BoNapGiaoDien"

        cac_bo_nap = [
            bo_nap
            for bo_nap in cac_bo_nap
            if bo_nap != ten_bo_nap
        ]

        cau_hinh["APP_DIRS"] = False
        tuy_chon["loaders"] = [
            ten_bo_nap,
            *cac_bo_nap,
        ]

    return ket_qua