from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path


urlpatterns = [
    path(
        "admin/",
        include("thu_toc.duong_dan_quan_tri"),
    ),

    path(
        "tai-khoan/",
        include("tai_khoan.duong_dan"),
    ),

    path(
        "kieu-toc/",
        include("kieu_toc.duong_dan"),
    ),

    path(
        "",
        include("thu_toc.duong_dan"),
    ),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )