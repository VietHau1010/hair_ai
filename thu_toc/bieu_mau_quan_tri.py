import warnings

from PIL import Image

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password

from kieu_toc.models import DangKhuonMat, KieuToc


class BieuMauToc(forms.ModelForm):
    class Meta:
        model = KieuToc

        fields = [
            "ten",
            "mo_ta",
            "anh_gioi_thieu",
            "anh_thu_toc",
            "dang_mat_phu_hop",
            "diem_neo_x",
            "diem_neo_y",
            "ti_le_chieu_rong",
            "do_lech_x",
            "do_lech_y",
            "thu_tu",
            "hien_thi",
        ]

        widgets = {
            "mo_ta": forms.Textarea(attrs={"rows": 4}),
            "dang_mat_phu_hop": forms.CheckboxSelectMultiple(),
        }

    def clean(self):
        du_lieu = super().clean()

        for ten in ("anh_gioi_thieu", "anh_thu_toc"):
            tep = self.files.get(ten)

            if not tep or ten in self.errors:
                continue

            try:
                if tep.size > 8 * 1024 * 1024:
                    raise ValueError(
                        "Ảnh không được vượt quá 8 MB."
                    )

                tep.seek(0)

                with warnings.catch_warnings():
                    warnings.simplefilter(
                        "error",
                        Image.DecompressionBombWarning,
                    )

                    with Image.open(tep) as anh:
                        if anh.width * anh.height > 20_000_000:
                            raise ValueError(
                                "Ảnh vượt quá 20 triệu điểm ảnh."
                            )

                        if ten == "anh_thu_toc":
                            if anh.format != "PNG":
                                raise ValueError(
                                    "Ảnh thử tóc phải là PNG nền trong suốt."
                                )

                            alpha = (
                                anh.convert("RGBA")
                                .getchannel("A")
                                .getextrema()
                            )

                            if alpha[0] == 255:
                                raise ValueError(
                                    "Ảnh PNG này chưa có vùng trong suốt."
                                )

            except (
                ValueError,
                OSError,
                Image.DecompressionBombError,
                Image.DecompressionBombWarning,
            ) as loi:
                self.add_error(ten, str(loi))

            finally:
                tep.seek(0)

        return du_lieu


class BieuMauDangMat(forms.ModelForm):
    class Meta:
        model = DangKhuonMat
        fields = ["ma"]


class BieuMauTaiKhoan(forms.ModelForm):
    mat_khau = forms.CharField(
        label="Mật khẩu mới",
        required=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"}
        ),
        help_text=(
            "Bắt buộc khi tạo tài khoản. "
            "Khi sửa, để trống để giữ mật khẩu."
        ),
    )

    nhap_lai = forms.CharField(
        label="Nhập lại mật khẩu",
        required=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"}
        ),
    )

    class Meta:
        model = get_user_model()

        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        ]

        widgets = {
            "groups": forms.CheckboxSelectMultiple(),
        }

        labels = {
            "username": "Tên đăng nhập",
            "email": "Email",
            "first_name": "Tên",
            "last_name": "Họ",
            "is_active": "Tài khoản hoạt động",
            "is_staff": "Cho phép vào quản trị",
            "is_superuser": "Quản trị viên cấp cao",
            "groups": "Nhóm quyền",
            "user_permissions": "Quyền bổ sung trực tiếp",
        }

    def clean(self):
        du_lieu = super().clean()
        mat_khau = du_lieu.get("mat_khau", "")

        if not self.instance.pk and not mat_khau:
            self.add_error(
                "mat_khau",
                "Nhập mật khẩu cho tài khoản mới.",
            )

        if mat_khau != du_lieu.get("nhap_lai", ""):
            self.add_error(
                "nhap_lai",
                "Hai mật khẩu chưa giống nhau.",
            )

        if mat_khau:
            nguoi_dung = get_user_model()(
                username=du_lieu.get("username", ""),
                email=du_lieu.get("email", ""),
                first_name=du_lieu.get("first_name", ""),
                last_name=du_lieu.get("last_name", ""),
            )

            try:
                validate_password(mat_khau, nguoi_dung)

            except forms.ValidationError as loi:
                self.add_error("mat_khau", loi)

        if (
            du_lieu.get("is_superuser")
            and not du_lieu.get("is_staff")
        ):
            self.add_error(
                "is_staff",
                "Quản trị viên cấp cao phải được phép vào quản trị.",
            )

        return du_lieu

    def save(self, commit=True):
        tai_khoan = super().save(commit=False)

        if self.cleaned_data.get("mat_khau"):
            tai_khoan.set_password(
                self.cleaned_data["mat_khau"]
            )

        if commit:
            tai_khoan.save()
            self.save_m2m()

        return tai_khoan


class QuyenTiengViet(forms.ModelMultipleChoiceField):
    def label_from_instance(self, quyen):
        dong_tu = {
            "add": "Thêm",
            "change": "Sửa",
            "delete": "Xóa",
            "view": "Xem",
        }

        hanh_dong = quyen.codename.split("_", 1)[0]

        return (
            f"{quyen.content_type.app_label} · "
            f"{dong_tu.get(hanh_dong, quyen.name)} "
            f"{quyen.content_type.name}"
        )


class BieuMauNhomQuyen(forms.ModelForm):
    permissions = QuyenTiengViet(
        label="Các quyền của nhóm",
        required=False,
        queryset=Permission.objects.select_related(
            "content_type"
        ).order_by(
            "content_type__app_label",
            "content_type__model",
            "codename",
        ),
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = Group
        fields = ["name", "permissions"]

        labels = {
            "name": "Tên nhóm quyền",
        }