import warnings

from PIL import Image

from django import forms

from kieu_toc.models import NguoiNoiTieng


class BieuMauThemToc(forms.Form):
    ten_nguoi = forms.CharField(
        label="Tên người nổi tiếng",
        max_length=150,
    )

    ten_kieu_toc = forms.CharField(
        label="Tên kiểu tóc",
        max_length=150,
    )

    anh_goc = forms.ImageField(
        label="Ảnh chân dung",
        widget=forms.ClearableFileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp",
            }
        ),
        help_text=(
            "JPEG, PNG hoặc WEBP; "
            "tối đa 8 MB, 20 triệu điểm ảnh."
        ),
    )

    def __init__(self, *args, nguoi=None, **kwargs):
        super().__init__(*args, **kwargs)

        if nguoi is not None:
            self.fields["ten_nguoi"].initial = nguoi.ten
            self.fields["ten_nguoi"].disabled = True

    def clean_anh_goc(self):
        tep = self.cleaned_data["anh_goc"]

        try:
            if tep.size > 8 * 1024 * 1024:
                raise forms.ValidationError(
                    "Ảnh vượt quá 8 MB."
                )

            with warnings.catch_warnings():
                warnings.simplefilter(
                    "error",
                    Image.DecompressionBombWarning,
                )

                tep.seek(0)

                with Image.open(tep) as anh:
                    if anh.format not in {"JPEG", "PNG", "WEBP"}:
                        raise forms.ValidationError(
                            "Chỉ nhận JPEG, PNG hoặc WEBP."
                        )

                    if getattr(anh, "is_animated", False):
                        raise forms.ValidationError(
                            "Hãy chọn ảnh tĩnh."
                        )

                    if (
                        min(anh.size) < 128
                        or anh.width * anh.height > 20_000_000
                    ):
                        raise forms.ValidationError(
                            "Mỗi chiều từ 128 pixel, "
                            "tối đa 20 triệu điểm ảnh."
                        )

                    anh.verify()

        except (
            OSError,
            ValueError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as loi:
            raise forms.ValidationError(
                "Ảnh lỗi hoặc kích thước không phù hợp."
            ) from loi

        finally:
            tep.seek(0)

        return tep


class BieuMauNguoiNoiTieng(forms.ModelForm):
    class Meta:
        model = NguoiNoiTieng

        fields = [
            "ten",
            "ten_khac",
            "thu_tu",
            "hien_thi",
        ]

        widgets = {
            "ten_khac": forms.Textarea(
                attrs={"rows": 3}
            ),
        }