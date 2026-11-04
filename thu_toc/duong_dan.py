from django.urls import path

from . import views, xu_ly_anh
from .views_xoa_toc import xoa_toc_camera


app_name = "thu_toc"


urlpatterns = [
    path(
        "",
        views.trang_chu,
        name="trang_chu",
    ),

    path(
        "phong-thu-toc/",
        views.phong_thu_toc,
        name="phong_thu_toc",
    ),

    path(
        "api/health/",
        views.trang_thai_ai,
        name="trang_thai_ai",
    ),

    path(
        "api/face/predict/",
        views.quet_khuon_mat,
        name="quet_khuon_mat",
    ),

    path(
        "api/hair/remove/",
        xoa_toc_camera,
        name="xoa_toc_camera",
    ),

    path(
        "anh-da-chup/",
        xu_ly_anh.danh_sach_anh_da_chup,
        name="danh_sach_anh_da_chup",
    ),

    path(
        "anh-da-chup/luu/",
        xu_ly_anh.luu_anh_da_chup,
        name="luu_anh_da_chup",
    ),

    path(
        "anh-da-chup/<int:ma>/",
        xu_ly_anh.xem_anh_da_chup,
        name="xem_anh_da_chup",
    ),

    path(
        "anh-da-chup/<int:ma>/xoa/",
        xu_ly_anh.xoa_anh_da_chup,
        name="xoa_anh_da_chup",
    ),
]