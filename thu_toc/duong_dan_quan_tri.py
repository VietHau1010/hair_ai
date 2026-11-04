from django.urls import path

from . import can_chinh_toc
from . import quan_tri
from . import quan_tri_nguoi_noi_tieng as nguoi
from . import quan_tri_thu_cong as thu_cong


app_name = "admin"


urlpatterns = [
    path(
        "can-toc/<int:ma_toc>/",
        can_chinh_toc.can_toc,
        name="can_chinh_toc",
    ),

    path(
        "nguoi-noi-tieng/them-ho-so/",
        thu_cong.them_nguoi,
        name="them_ho_so_nguoi_noi_tieng",
    ),

    path(
        "nguoi-noi-tieng/<int:ma>/them-png/",
        thu_cong.toc_thu_cong,
        name="them_png_nguoi_noi_tieng",
    ),

    path(
        "nguoi-noi-tieng/<int:ma>/toc/<int:ma_toc>/sua/",
        thu_cong.toc_thu_cong,
        name="sua_toc_nguoi_noi_tieng",
    ),

    path(
        "nguoi-noi-tieng/<int:ma>/toc/<int:ma_toc>/xoa/",
        thu_cong.xoa_toc,
        name="xoa_toc_nguoi_noi_tieng",
    ),

    path(
        "nguoi-noi-tieng/<int:ma>/xoa-toan-bo/",
        thu_cong.xoa_ho_so,
        name="xoa_toan_bo_nguoi_noi_tieng",
    ),

    path(
        "",
        quan_tri.tong_quan,
        name="index",
    ),

    path(
        "tai-khoan/",
        quan_tri.danh_sach,
        {"muc": "tai-khoan"},
        name="auth_user_changelist",
    ),

    path(
        "nguoi-noi-tieng/",
        nguoi.danh_sach,
        name="nguoi_noi_tieng",
    ),

    path(
        "nguoi-noi-tieng/them-toc/",
        nguoi.them_toc,
        name="them_toc_nguoi_noi_tieng",
    ),

    path(
        "nguoi-noi-tieng/<int:ma>/",
        nguoi.chi_tiet,
        name="chi_tiet_nguoi_noi_tieng",
    ),

    path(
        "nguoi-noi-tieng/<int:ma>/them-toc/",
        nguoi.them_toc,
        name="them_toc_cho_nguoi",
    ),

    path(
        "nguoi-noi-tieng/<int:ma>/sua/",
        nguoi.sua,
        name="sua_nguoi_noi_tieng",
    ),

    path(
        "nguoi-noi-tieng/<int:ma>/xoa/",
        nguoi.xoa,
        name="xoa_nguoi_noi_tieng",
    ),

    path(
        "tach-toc/<int:ma>/",
        nguoi.ket_qua,
        name="ket_qua_tach_toc",
    ),

    path(
        "tach-toc/<int:ma>/trang-thai/",
        nguoi.trang_thai,
        name="trang_thai_tach_toc",
    ),

    path(
        "tach-toc/<int:ma>/thu-lai/",
        nguoi.thu_lai,
        name="thu_lai_tach_toc",
    ),

    path(
        "<slug:muc>/",
        quan_tri.danh_sach,
        name="danh_sach",
    ),

    path(
        "<slug:muc>/them/",
        quan_tri.bieu_mau,
        name="them",
    ),

    path(
        "<slug:muc>/<int:ma>/sua/",
        quan_tri.bieu_mau,
        name="sua",
    ),

    path(
        "<slug:muc>/<int:ma>/xoa/",
        quan_tri.xoa,
        name="xoa",
    ),
]