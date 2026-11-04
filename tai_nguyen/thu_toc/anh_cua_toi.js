const khu = document.getElementById("anh_cua_toi");

if (khu) {
    const el = id => document.getElementById("act_" + id);

    let trangTiep = 1;
    let dangTai = false;
    let anhHienTai = null;
    let tepChiaSe = null;
    let phien = 0;
    let dangChiaSe = false;

    function bao(text) {
        el("thong_bao").textContent = text;
    }

    function nut(ten, fn) {
        const b = document.createElement("button");

        b.type = "button";
        b.className = "act-nut act-phu";
        b.textContent = ten;
        b.onclick = fn;

        return b;
    }

    async function json(url, options = {}) {
        const r = await fetch(
            url,
            {
                credentials: "same-origin",
                cache: "no-store",
                ...options
            }
        );

        if (!r.headers.get("content-type")?.includes(
            "application/json"
        )) {
            throw Error(
                "Không tải được ảnh. Vui lòng tải lại trang."
            );
        }

        const k = await r.json();

        if (!r.ok || !k.thanh_cong) {
            throw Error(
                k.thong_bao || "Không thực hiện được."
            );
        }

        return k;
    }

    async function moAnh(anh) {
        anhHienTai = anh;
        tepChiaSe = null;

        const ma = ++phien;

        khoaChiaSe(true);

        el("ten").textContent = anh.ten;
        el("hinh_lon").src = anh.dia_chi;
        el("tai").href = anh.dia_chi + "?tai=1";
        el("chia_se_bao").textContent = "";
        el("xem").showModal();

        try {
            const r = await fetch(
                anh.dia_chi,
                {
                    credentials: "same-origin",
                    cache: "no-store"
                }
            );

            if (!r.ok) {
                throw Error("Không tải được ảnh.");
            }

            const b = await r.blob();

            if (ma === phien) {
                tepChiaSe = new File(
                    [b],
                    "anh-thu-toc.png",
                    { type: "image/png" }
                );
            }

        } catch (e) {
            if (ma === phien) {
                el("chia_se_bao").textContent = e.message;
            }

        } finally {
            if (ma === phien) {
                khoaChiaSe(false);
            }
        }
    }

    function theAnh(anh) {
        const the = document.createElement("article");
        the.className = "act-the";

        const mo = nut(
            "Xem lớn",
            () => moAnh(anh)
        );

        const img = document.createElement("img");

        img.src = anh.dia_chi;
        img.alt = anh.ten;
        img.loading = "lazy";

        const h = document.createElement("h3");
        h.textContent = anh.ten;

        const ngay = document.createElement("small");

        ngay.textContent = new Date(
            anh.tao_luc
        ).toLocaleString("vi-VN");

        const hang = document.createElement("div");
        hang.className = "act-hang";

        const tai = document.createElement("a");

        tai.className = "act-nut act-phu";
        tai.textContent = "Tải";
        tai.href = anh.dia_chi + "?tai=1";
        tai.download = "anh-thu-toc.png";

        const xoa = nut("Xóa", async () => {
            if (!confirm(
                "Xóa vĩnh viễn ảnh đã lưu này?"
            )) return;

            xoa.disabled = true;

            try {
                await json(
                    anh.dia_chi_xoa,
                    {
                        method: "POST",

                        headers: {
                            "X-CSRFToken": document.querySelector(
                                "#act_bao_ve [name=csrfmiddlewaretoken]"
                            ).value
                        }
                    }
                );

                the.remove();
                bao("Đã xóa ảnh.");

            } catch (e) {
                bao(e.message);
                xoa.disabled = false;
            }
        });

        hang.append(mo, tai, xoa);
        the.append(img, h, ngay, hang);

        return the;
    }

    async function tai() {
        if (dangTai || !trangTiep) return;

        dangTai = true;
        el("them").disabled = true;

        try {
            const k = await json(
                khu.dataset.danhSach +
                "?trang=" + trangTiep
            );

            for (const anh of k.cac_anh) {
                el("danh_sach").append(
                    theAnh(anh)
                );
            }

            trangTiep = k.trang_tiep;
            el("them").hidden = !trangTiep;

            bao(
                el("danh_sach").children.length
                    ? ""
                    : "Bạn chưa lưu ảnh nào. Chụp ảnh trong phòng thử tóc rồi chọn “Lưu vào ảnh của tôi”."
            );

        } catch (e) {
            bao(e.message);

            el("them").hidden = false;
            el("them").textContent = "Thử tải lại";

        } finally {
            dangTai = false;
            el("them").disabled = false;
        }
    }

    function khoaChiaSe(khoa) {
        for (const ten of [
            "chia_se",
            "fb",
            "ig"
        ]) {
            el(ten).disabled = khoa;

            el(ten).setAttribute(
                "aria-busy",
                String(khoa)
            );
        }
    }

    function taiVaMo(dich) {
        if (!anhHienTai) return;

        if (dich) {
            window.open(
                dich === "Facebook"
                    ? "https://www.facebook.com/"
                    : "https://www.instagram.com/",
                "_blank",
                "noopener,noreferrer"
            );
        }

        el("tai").click();

        el("chia_se_bao").textContent =
            "Đã yêu cầu tải ảnh. " +
            (
                dich
                    ? "Trong " + dich +
                      ", chọn Tạo bài viết và chọn ảnh vừa tải. Trang web không tự đính kèm ảnh."
                    : "Chọn ảnh vừa tải trong ứng dụng bạn muốn đăng."
            );
    }

    async function chiaSe(dich) {
        if (dangChiaSe) return;

        const ma = phien;
        let hoTro = false;

        try {
            hoTro =
                !!tepChiaSe &&
                !!navigator.share &&
                !!navigator.canShare?.({
                    files: [tepChiaSe]
                });

        } catch {}

        if (!hoTro) {
            taiVaMo(dich);
            return;
        }

        dangChiaSe = true;
        khoaChiaSe(true);

        el("chia_se_bao").textContent = dich
            ? "Chọn " + dich +
              " trong bảng chia sẻ nếu ứng dụng có xuất hiện."
            : "Chọn ứng dụng trong bảng chia sẻ của thiết bị.";

        try {
            await navigator.share({
                files: [tepChiaSe],
                title: "Ảnh thử tóc HAULONGHAIR"
            });

            if (ma === phien) {
                el("chia_se_bao").textContent =
                    "Đã chuyển ảnh qua bảng chia sẻ. Hoàn tất thao tác trong ứng dụng; website không xác nhận được ảnh đã đăng.";
            }

        } catch (e) {
            if (ma === phien) {
                el("chia_se_bao").textContent =
                    e.name === "AbortError"
                        ? "Chia sẻ đã đóng hoặc không có ứng dụng phù hợp. "
                        : "Thiết bị chưa chia sẻ được ảnh trực tiếp. ";

                el("chia_se_bao").append(
                    nut(
                        dich
                            ? "Tải ảnh và mở " + dich
                            : "Tải ảnh để đăng",
                        () => taiVaMo(dich)
                    )
                );
            }

        } finally {
            dangChiaSe = false;

            if (ma === phien) {
                khoaChiaSe(false);
            }
        }
    }

    el("them").onclick = tai;

    el("dong").onclick = () => {
        el("xem").close();
    };

    el("xem").addEventListener("close", () => {
        phien++;
        anhHienTai = null;
        tepChiaSe = null;
        el("hinh_lon").removeAttribute("src");
    });

    el("chia_se").onclick = () => chiaSe("");
    el("fb").onclick = () => chiaSe("Facebook");
    el("ig").onclick = () => chiaSe("Instagram");

    tai();
}