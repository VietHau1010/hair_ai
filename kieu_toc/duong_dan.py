from django.urls import path

from . import kham_pha, views


app_name = "kieu_toc"


urlpatterns = [
    path(
        "",
        views.danh_sach_kieu_toc,
        name="danh_sach",
    ),

    path(
        "nguoi-noi-tieng/",
        kham_pha.nguoi_noi_tieng,
        name="nguoi_noi_tieng",
    ),

    path(
        "nguoi-noi-tieng/du-lieu/",
        kham_pha.du_lieu_nguoi_noi_tieng,
        name="du_lieu_nguoi_noi_tieng",
    ),

    path(
        "yeu-thich/",
        views.danh_sach_yeu_thich,
        name="yeu_thich",
    ),

    path(
        "<int:ma_toc>/luu/",
        views.luu_yeu_thich,
        name="luu_yeu_thich",
    ),

    path(
        "<int:ma_toc>/bo-luu/",
        views.bo_yeu_thich,
        name="bo_yeu_thich",
    ),
]