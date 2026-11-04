(() => {
    const form = document.getElementById("nt_bieu_mau");
    const tep = document.getElementById("id_anh_goc");
    const anh = document.getElementById("nt_xem_anh");

    let diaChiAnh = null;

    tep?.addEventListener("change", () => {
        if (diaChiAnh) {
            URL.revokeObjectURL(diaChiAnh);
        }

        diaChiAnh = null;

        if (!anh) return;

        anh.hidden = true;
        anh.removeAttribute("src");

        const chon = tep.files?.[0];

        if (!chon || chon.size > 8 * 1024 * 1024) {
            return;
        }

        diaChiAnh = URL.createObjectURL(chon);

        anh.src = diaChiAnh;
        anh.hidden = false;
    });

    form?.addEventListener("submit", () => {
        const nut = document.getElementById("nt_gui");

        if (nut) {
            nut.disabled = true;
            nut.textContent = "Đang lưu…";
        }

        form.setAttribute("aria-busy", "true");
    });

    window.addEventListener("pageshow", () => {
        if (!form) return;

        form.removeAttribute("aria-busy");

        const nut = document.getElementById("nt_gui");

        if (nut) {
            nut.disabled = false;

            nut.textContent = tep
                ? "Lưu và tự tách tóc"
                : "Lưu thay đổi";
        }
    });

    const theoDoi = document.getElementById("nt_theo_doi");

    if (!theoDoi) return;

    async function capNhat() {
        const dieuKhien = new AbortController();

        const han = setTimeout(
            () => dieuKhien.abort(),
            10000
        );

        try {
            const phanHoi = await fetch(
                theoDoi.dataset.url,
                {
                    credentials: "same-origin",
                    cache: "no-store",
                    signal: dieuKhien.signal,
                    headers: {
                        Accept: "application/json",
                    },
                }
            );

            if (!phanHoi.ok || phanHoi.redirected) {
                throw new Error();
            }

            const ketQua = await phanHoi.json();

            document.getElementById(
                "nt_trang_thai"
            ).textContent = ketQua.nhan;

            document.getElementById(
                "nt_buoc"
            ).textContent = ketQua.buoc || "Đang chờ xử lý";

            if (ketQua.ket_thuc) {
                window.location.reload();
                return;
            }

            setTimeout(capNhat, 3000);

        } catch {
            theoDoi.textContent =
                "Tạm ngừng cập nhật. " +
                "Tải lại trang để xem kết quả hoặc đăng nhập lại.";

        } finally {
            clearTimeout(han);
        }
    }

    setTimeout(capNhat, 2000);
})();