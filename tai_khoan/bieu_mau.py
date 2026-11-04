from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import TaiKhoan


class BieuMauDangKy(UserCreationForm):
    email = forms.EmailField(
        label="Địa chỉ thư điện tử",
        required=True,
        widget=forms.EmailInput(attrs={
            "autocomplete": "email",
            "placeholder": "Nhập địa chỉ thư điện tử",
        }),
    )

    class Meta(UserCreationForm.Meta):
        model = TaiKhoan
        fields = ("username", "email")
        labels = {
            "username": "Tên đăng nhập",
        }
        error_messages = {
            "username": {
                "unique": "Tên đăng nhập này đã được sử dụng.",
                "invalid": (
                    "Tên đăng nhập chỉ gồm chữ, số "
                    "và các ký tự @ . + - _"
                ),
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].label = "Tên đăng nhập"
        self.fields["username"].help_text = (
            "Tối đa 150 ký tự. Dùng chữ, số và các ký tự @ . + - _"
        )
        self.fields["username"].widget.attrs.update({
            "autocomplete": "username",
            "placeholder": "Nhập tên đăng nhập",
        })

        self.fields["password1"].label = "Mật khẩu"
        self.fields["password1"].help_text = (
            "Ít nhất 8 ký tự; tránh mật khẩu phổ biến "
            "hoặc quá giống thông tin tài khoản."
        )
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"

        self.fields["password2"].label = "Nhập lại mật khẩu"
        self.fields["password2"].help_text = "Nhập lại đúng mật khẩu phía trên."
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"

        self.error_messages["password_mismatch"] = (
            "Hai mật khẩu không khớp nhau."
        )

        for truong in self.fields.values():
            truong.error_messages["required"] = "Vui lòng nhập thông tin này."

        self.fields["email"].error_messages["invalid"] = (
            "Địa chỉ thư điện tử không hợp lệ."
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if TaiKhoan.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Địa chỉ thư điện tử này đã được sử dụng."
            )

        return email


class BieuMauDangNhap(AuthenticationForm):
    error_messages = {
        "invalid_login": "Tên đăng nhập hoặc mật khẩu không đúng.",
        "inactive": "Tài khoản này đã bị vô hiệu hóa.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].label = "Tên đăng nhập"
        self.fields["username"].widget.attrs.update({
            "autocomplete": "username",
            "placeholder": "Nhập tên đăng nhập",
        })

        self.fields["password"].label = "Mật khẩu"
        self.fields["password"].widget.attrs.update({
            "autocomplete": "current-password",
            "placeholder": "Nhập mật khẩu",
        })

        for truong in self.fields.values():
            truong.error_messages["required"] = "Vui lòng nhập thông tin này."
class BieuMauThongTin(forms.ModelForm):
    class Meta:
        model = TaiKhoan
        fields = ("first_name", "last_name", "email")

        labels = {
            "first_name": "Tên",
            "last_name": "Họ và tên đệm",
            "email": "Địa chỉ thư điện tử",
        }

        widgets = {
            "first_name": forms.TextInput(attrs={
                "autocomplete": "given-name",
            }),
            "last_name": forms.TextInput(attrs={
                "autocomplete": "family-name",
            }),
            "email": forms.EmailInput(attrs={
                "autocomplete": "email",
            }),
        }

        error_messages = {
            "email": {
                "required": "Vui lòng nhập địa chỉ thư điện tử.",
                "invalid": "Địa chỉ thư điện tử không hợp lệ.",
                "unique": "Địa chỉ thư điện tử này đã được sử dụng.",
            },
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        da_ton_tai = (
            TaiKhoan.objects
            .filter(email__iexact=email)
            .exclude(pk=self.instance.pk)
            .exists()
        )

        if da_ton_tai:
            raise forms.ValidationError(
                "Địa chỉ thư điện tử này đã được sử dụng."
            )

        return email
from django.contrib.auth.forms import PasswordChangeForm


class BieuMauDoiMatKhau(PasswordChangeForm):
    error_messages = {
        "password_incorrect": "Mật khẩu hiện tại không đúng.",
        "password_mismatch": "Hai mật khẩu mới không khớp nhau.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["old_password"].label = "Mật khẩu hiện tại"
        self.fields["new_password1"].label = "Mật khẩu mới"
        self.fields["new_password2"].label = "Nhập lại mật khẩu mới"

        self.fields["new_password1"].help_text = (
            "Ít nhất 8 ký tự; tránh mật khẩu phổ biến, "
            "chỉ gồm số hoặc quá giống thông tin tài khoản."
        )

        self.fields["new_password2"].help_text = (
            "Nhập lại đúng mật khẩu mới phía trên."
        )

        for truong in self.fields.values():
            truong.error_messages["required"] = (
                "Vui lòng nhập thông tin này."
            )

    def clean_new_password1(self):
        mat_khau_moi = self.cleaned_data["new_password1"]

        if self.user.check_password(mat_khau_moi):
            raise forms.ValidationError(
                "Mật khẩu mới phải khác mật khẩu hiện tại."
            )

        return mat_khau_moi