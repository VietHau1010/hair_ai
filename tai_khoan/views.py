from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .bieu_mau import BieuMauDangKy, BieuMauDangNhap


def dang_ky(request):
    if request.user.is_authenticated:
        return redirect("thu_toc:trang_chu")

    bieu_mau = BieuMauDangKy(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and bieu_mau.is_valid():
        tai_khoan = bieu_mau.save(commit=False)

        # Tài khoản đăng ký trên web luôn là người dùng thông thường.
        tai_khoan.is_staff = False
        tai_khoan.is_superuser = False
        tai_khoan.save()

        messages.success(
            request,
            "Đăng ký thành công. Bạn có thể đăng nhập ngay.",
        )
        return redirect("tai_khoan:dang_nhap")

    return render(request, "tai_khoan/bieu_mau_tai_khoan.html", {
        "bieu_mau": bieu_mau,
        "tieu_de": "Tạo tài khoản",
        "ten_nut": "Đăng ký",
        "la_dang_ky": True,
    })


def dang_nhap(request):
    if request.user.is_authenticated:
        return redirect("thu_toc:trang_chu")

    bieu_mau = BieuMauDangNhap(
        request=request,
        data=request.POST if request.method == "POST" else None,
    )

    if request.method == "POST" and bieu_mau.is_valid():
        login(request, bieu_mau.get_user())
        messages.success(request, "Đăng nhập thành công.")
        return redirect("thu_toc:trang_chu")

    return render(request, "tai_khoan/bieu_mau_tai_khoan.html", {
        "bieu_mau": bieu_mau,
        "tieu_de": "Chào mừng bạn trở lại",
        "ten_nut": "Đăng nhập",
        "la_dang_ky": False,
    })


@require_POST
def dang_xuat(request):
    logout(request)
    messages.success(request, "Bạn đã đăng xuất.")
    return redirect("thu_toc:trang_chu")
from django.contrib.auth.decorators import login_required

from .bieu_mau import BieuMauThongTin


@login_required(login_url="tai_khoan:dang_nhap")
def thong_tin_tai_khoan(request):
    bieu_mau = BieuMauThongTin(
        request.POST if request.method == "POST" else None,
        instance=request.user,
    )

    if request.method == "POST" and bieu_mau.is_valid():
        bieu_mau.save()

        messages.success(
            request,
            "Đã cập nhật thông tin tài khoản.",
        )

        return redirect("tai_khoan:thong_tin")

    return render(
        request,
        "tai_khoan/thong_tin_tai_khoan.html",
        {"bieu_mau": bieu_mau},
    )
from django.contrib.auth import update_session_auth_hash

from .bieu_mau import BieuMauDoiMatKhau


@login_required(login_url="tai_khoan:dang_nhap")
def doi_mat_khau(request):
    bieu_mau = BieuMauDoiMatKhau(
        user=request.user,
        data=request.POST if request.method == "POST" else None,
    )

    if request.method == "POST" and bieu_mau.is_valid():
        tai_khoan = bieu_mau.save()

        # Giữ phiên đăng nhập sau khi đổi mật khẩu.
        update_session_auth_hash(request, tai_khoan)

        messages.success(
            request,
            "Đổi mật khẩu thành công.",
        )

        return redirect("tai_khoan:thong_tin")

    return render(
        request,
        "tai_khoan/doi_mat_khau.html",
        {"bieu_mau": bieu_mau},
    )