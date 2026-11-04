export function khoiTaoChupAnh({
    nguon,
    sanSang,
    conKieuToc = sanSang
}) {
    const phong = document.getElementById("phong_chup_anh");
    const nutMo = document.getElementById("nut_mo_chup_anh");

    if (!phong || !nutMo) return;

    const el = ten => document.getElementById("ca_" + ten);
    const xem = el("xem_camera");
    const ketQua = el("ket_qua");
    const banXuat = document.createElement("canvas");

    const mauSac = {
        xanh: ["#edf4e9", "#284d39", "HAULONGHAIR"],
        hong: ["#ffe8ef", "#9e4668", "SWEET MOMENTS"],
        xanh_duong: ["#e0edff", "#355f91", "STAR MOMENTS"],
        trang: ["#ffffff", "#29352e", "HAULONGHAIR"]
    };

    const khung = [
        { ma: "hai_doc", ten: "2 ảnh dọc", so: 2, cot: 1 },
        { ma: "ba_doc", ten: "3 ảnh dọc", so: 3, cot: 1 },
        { ma: "bon_o", ten: "4 ảnh lưới", so: 4, cot: 2 },
        { ma: "bon_doc", ten: "4 ảnh dọc", so: 4, cot: 1 },
        { ma: "sau_o", ten: "6 ảnh lưới", so: 6, cot: 2 }
    ];

    let cheDo = "don";
    let boCuc = khung[2];
    let cacO = Array(4).fill(null);
    let oChon = 0;

    let cacAnh = [];
    let anhDon = null;
    let dangChup = false;
    let luot = 0;
    let vong = 0;
    let coTheXuat = false;

    let soHien = 24;
    let dangLuu = false;
    let lanVe = 0;
    let maBanXuat = 0;
    let anhDaLuu = -1;

    let cacVung = [];
    let boNho = null;
    let tieuDiemCu = null;
    let urls = [];
    let chanTro = null;
    let anhKeo = null;

    let tepChiaSeSanSang = null;
    let dangChiaSe = false;
    let henChiaSe = null;
    let biKhoa = false;

    function bao(text) {
        el("thong_bao").textContent = text;
    }

    const doi = ms => new Promise(resolve => {
        setTimeout(resolve, ms);
    });

    function taoNut(text, fn) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "ca-nut ca-phu";
        b.textContent = text;
        b.onclick = fn;
        return b;
    }

    function blobCanvas(c, type = "image/png") {
        return new Promise((resolve, reject) => {
            try {
                c.toBlob(
                    blob => blob
                        ? resolve(blob)
                        : reject(Error("Không tạo được ảnh.")),
                    type,
                    .94
                );
            } catch (e) {
                reject(e);
            }
        });
    }

    function loi(e) {
        bao(
            e?.name === "QuotaExceededError"
                ? "Bộ nhớ trình duyệt đã đầy. Lưu ảnh cần giữ rồi xóa bớt ảnh trong khay."
                : (e.message || "Chưa thực hiện được. Vui lòng thử lại.")
        );
    }

    const moKho = new Promise(resolve => {
        if (!window.indexedDB) {
            resolve(null);
            return;
        }

        const r = indexedDB.open(
            "haul_toc_khay_anh_" + phong.dataset.taiKhoan,
            1
        );

        r.onupgradeneeded = () => {
            r.result.createObjectStore("anh", {
                keyPath: "ma"
            });
        };

        r.onsuccess = () => resolve(r.result);
        r.onerror = () => resolve(null);
    });

    async function ghiKho(anh) {
        if (!boNho) return;

        return new Promise((resolve, reject) => {
            const tx = boNho.transaction("anh", "readwrite");

            tx.objectStore("anh").put(anh);
            tx.oncomplete = resolve;
            tx.onerror = () => reject(tx.error);
            tx.onabort = () => reject(
                tx.error || Error("Không lưu được khay ảnh.")
            );
        });
    }

    async function xoaKho(ma) {
        if (!boNho) return;

        return new Promise((resolve, reject) => {
            const tx = boNho.transaction("anh", "readwrite");

            tx.objectStore("anh").delete(ma);
            tx.oncomplete = resolve;
            tx.onerror = () => reject(tx.error);
        });
    }

    const anhSanSang = moKho.then(async db => {
        boNho = db;

        if (db) {
            cacAnh = await new Promise(resolve => {
                const r = db.transaction("anh")
                    .objectStore("anh")
                    .getAll();

                r.onsuccess = () => resolve(
                    r.result.sort((a, b) => b.luc - a.luc)
                );

                r.onerror = () => resolve([]);
            });
        }

        veKhay();
    });

    async function napHinh(anh) {
        const url = URL.createObjectURL(anh.tep);
        const img = new Image();

        try {
            img.src = url;
            await img.decode();
            return img;
        } finally {
            URL.revokeObjectURL(url);
        }
    }

    function datO(index) {
        if (cheDo !== "khung") return;

        oChon = (index + cacO.length) % cacO.length;

        const o = cacO[oChon];

        el("phong").value = o?.phong || 1;
        el("ngang").value = o?.ngang || 0;
        el("doc").value = o?.doc || 0;
        el("can_anh").disabled = !o;

        veAnh();
    }

    async function chonAnh(anh, index = oChon) {
        const stamp = ++lanVe;

        try {
            const img = await napHinh(anh);

            if (stamp !== lanVe) return;

            if (cheDo === "don") {
                anhDon = { anh, img };
            } else {
                cacO[index] = {
                    anh,
                    img,
                    phong: 1,
                    ngang: 0,
                    doc: 0
                };
            }

            datO(index);
            veAnh();

        } catch (e) {
            loi(e);
        }
    }

    function veKhay() {
        urls.forEach(url => URL.revokeObjectURL(url));
        urls = [];

        const khay = el("khay");
        khay.replaceChildren();

        el("so_anh").textContent = String(cacAnh.length);

        if (!cacAnh.length) {
            const p = document.createElement("p");
            p.textContent = "Chưa có ảnh. Bấm Chụp ảnh để bắt đầu.";
            khay.append(p);
        }

        for (const anh of cacAnh.slice(0, soHien)) {
            const the = document.createElement("article");
            the.className = "ca-o-anh";

            const img = document.createElement("img");
            const url = URL.createObjectURL(anh.nho || anh.tep);

            urls.push(url);

            img.src = url;
            img.alt = "Ảnh chụp " +
                new Date(anh.luc).toLocaleTimeString("vi-VN");

            img.loading = "lazy";
            img.draggable = true;
            img.tabIndex = 0;

            img.setAttribute("role", "button");
            img.setAttribute("aria-label", "Chọn " + img.alt);

            img.onclick = () => chonAnh(anh);

            img.onkeydown = e => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    chonAnh(anh);
                }
            };

            img.ondragstart = e => {
                anhKeo = anh;
                e.dataTransfer.setData("text/plain", anh.ma);
            };

            const hang = document.createElement("div");
            hang.className = "ca-hang";

            hang.append(
                taoNut("Xem lớn", () => {
                    if (chanTro) {
                        URL.revokeObjectURL(chanTro);
                    }

                    chanTro = URL.createObjectURL(anh.tep);

                    el("anh_lon_hinh").src = chanTro;
                    el("anh_lon").hidden = false;
                }),

                taoNut("Lưu", async () => {
                    try {
                        await luuLenMay(
                            anh.tep,
                            "don",
                            "Ảnh thử tóc"
                        );

                        bao(
                            "Đã lưu ảnh vào Ảnh của tôi trên trang chủ."
                        );
                    } catch (e) {
                        loi(e);
                    }
                }),

                taoNut("Xóa", async () => {
                    if (!confirm(
                        "Xóa ảnh này khỏi khay? Ảnh đã lưu trên trang chủ vẫn được giữ."
                    )) return;

                    try {
                        await xoaKho(anh.ma);

                        cacAnh = cacAnh.filter(
                            a => a.ma !== anh.ma
                        );

                        veKhay();

                    } catch (e) {
                        loi(e);
                    }
                })
            );

            the.append(img, hang);
            khay.append(the);
        }

        if (cacAnh.length > soHien) {
            khay.append(
                taoNut("Xem thêm ảnh", () => {
                    soHien += 24;
                    veKhay();
                })
            );
        }
    }

    function catAnh(ctx, img, r, o) {
        const scale = Math.max(
            r.w / img.width,
            r.h / img.height
        ) * (o.phong || 1);

        const dw = img.width * scale;
        const dh = img.height * scale;

        const x = r.x - (dw - r.w) / 2 +
            (o.ngang || 0) * (dw - r.w) / 2;

        const y = r.y - (dh - r.h) / 2 +
            (o.doc || 0) * (dh - r.h) / 2;

        ctx.save();
        ctx.beginPath();
        ctx.rect(r.x, r.y, r.w, r.h);
        ctx.clip();
        ctx.drawImage(img, x, y, dw, dh);
        ctx.restore();
    }

    function veAnh() {
        maBanXuat++;

        const c = banXuat;
        const ctx = c.getContext("2d");

        cacVung = [];

        if (cheDo === "don") {
            c.width = anhDon?.img.width || 960;
            c.height = anhDon?.img.height || 540;

            ctx.fillStyle = "#edf0e9";
            ctx.fillRect(0, 0, c.width, c.height);

            if (anhDon) {
                ctx.drawImage(anhDon.img, 0, 0);
            }

            coTheXuat = !!anhDon;

            el("goi_y_o").textContent = anhDon
                ? "Ảnh đã có tóc và thông số bạn đã chỉnh."
                : "Chọn ảnh trong khay hoặc chụp ảnh mới.";

            el("can_anh").hidden = true;

        } else {
            const cot = boCuc.cot;
            const hang = Math.ceil(boCuc.so / cot);
            const le = 48;
            const khe = 24;

            c.width = cot === 1 ? 800 : 1200;

            const rong = (
                c.width - le * 2 - khe * (cot - 1)
            ) / cot;

            const cao = rong * 3 / 4;

            c.height = Math.round(
                120 +
                hang * cao +
                (hang - 1) * khe +
                110
            );

            const [nen, chu, ten] = mauSac[el("mau").value];

            ctx.fillStyle = nen;
            ctx.fillRect(0, 0, c.width, c.height);

            ctx.fillStyle = chu;
            ctx.textAlign = "center";
            ctx.font = "bold 30px Arial";
            ctx.fillText(ten, c.width / 2, 64);

            if (el("mau").value !== "trang") {
                ctx.font = "22px Arial";
                ctx.fillText("✦", 32, 64);
                ctx.fillText("✦", c.width - 32, 64);
            }

            for (let i = 0; i < boCuc.so; i++) {
                const r = {
                    x: le + (i % cot) * (rong + khe),
                    y: 120 + Math.floor(i / cot) * (cao + khe),
                    w: rong,
                    h: cao
                };

                cacVung.push(r);

                ctx.fillStyle = "#fff";
                ctx.fillRect(r.x, r.y, r.w, r.h);

                if (cacO[i]) {
                    catAnh(
                        ctx,
                        cacO[i].img,
                        r,
                        cacO[i]
                    );
                } else {
                    ctx.fillStyle = chu;
                    ctx.font = "24px Arial";

                    ctx.fillText(
                        "Chọn ảnh " + (i + 1),
                        r.x + r.w / 2,
                        r.y + r.h / 2
                    );
                }
            }

            ctx.fillStyle = chu;
            ctx.font = "20px Arial";

            ctx.fillText(
                "HAULONGHAIR · " +
                new Date().toLocaleDateString("vi-VN"),
                c.width / 2,
                c.height - 35
            );

            coTheXuat = cacO.every(Boolean);

            el("goi_y_o").textContent =
                "Đang chọn ô " +
                (oChon + 1) + "/" + boCuc.so +
                " · Đã ghép " +
                cacO.filter(Boolean).length + "/" + boCuc.so +
                " ảnh. Chọn ảnh trong khay để thay.";

            el("can_anh").hidden = false;
        }

        ketQua.width = c.width;
        ketQua.height = c.height;

        const k = ketQua.getContext("2d");
        k.drawImage(c, 0, 0);

        // Viền chọn chỉ hiện trong bản xem.
        if (cheDo === "khung" && cacVung[oChon]) {
            const r = cacVung[oChon];

            k.strokeStyle = "#b8882c";
            k.lineWidth = 6;
            k.strokeRect(r.x, r.y, r.w, r.h);
        }

        chuanBiChiaSe();
        capNhatNut();
    }

    function chuanBiChiaSe() {
        clearTimeout(henChiaSe);

        tepChiaSeSanSang = null;

        if (!coTheXuat) return;

        const phien = maBanXuat;
        const dinhDang = el("dinh_dang").value;

        // Chuẩn bị file trước khi người dùng bấm chia sẻ.
        henChiaSe = setTimeout(async () => {
            try {
                const blob = await blobCanvas(
                    banXuat,
                    "image/" + dinhDang
                );

                if (
                    phien !== maBanXuat ||
                    dinhDang !== el("dinh_dang").value
                ) {
                    return;
                }

                tepChiaSeSanSang = new File(
                    [blob],
                    tenTep(),
                    { type: blob.type }
                );

                capNhatNut();

            } catch (e) {
                if (phien === maBanXuat) {
                    loi(e);
                }
            }
        }, 150);
    }

    function capNhatNut() {
        for (const ten of [
            "tai",
            "luu",
            "chia_se",
            "facebook",
            "instagram"
        ]) {
            el(ten).disabled = !coTheXuat || dangLuu;
        }

        el("luu").disabled =
            !coTheXuat ||
            dangLuu ||
            anhDaLuu === maBanXuat;

        for (const ten of [
            "chia_se",
            "facebook",
            "instagram"
        ]) {
            el(ten).disabled =
                !coTheXuat ||
                !tepChiaSeSanSang ||
                dangLuu ||
                dangChiaSe;

            el(ten).setAttribute(
                "aria-busy",
                String(dangChiaSe)
            );
        }
    }

    function doiCheDo(mode) {
        cheDo = mode;
        lanVe++;

        el("don").setAttribute(
            "aria-pressed",
            String(mode === "don")
        );

        el("khung").setAttribute(
            "aria-pressed",
            String(mode === "khung")
        );

        el("tuy_chon_khung").hidden = mode !== "khung";

        el("ten_xem").textContent = mode === "khung"
            ? "Khung ảnh của bạn"
            : "Ảnh đang chọn";

        el("chup").textContent = mode === "khung"
            ? "📷 Chụp thêm " + boCuc.so + " ảnh"
            : "📷 Chụp ảnh";

        datO(oChon);
        veAnh();
    }

    function toaDo(e) {
        const r = ketQua.getBoundingClientRect();

        return {
            x: (e.clientX - r.left) * ketQua.width / r.width,
            y: (e.clientY - r.top) * ketQua.height / r.height
        };
    }

    function oTai(p) {
        return cacVung.findIndex(r =>
            p.x >= r.x &&
            p.x <= r.x + r.w &&
            p.y >= r.y &&
            p.y <= r.y + r.h
        );
    }

    ketQua.onclick = e => {
        const i = oTai(toaDo(e));
        if (i >= 0) datO(i);
    };

    ketQua.ondragover = e => {
        e.preventDefault();
    };

    ketQua.ondrop = e => {
        e.preventDefault();

        const i = oTai(toaDo(e));

        const anh = cacAnh.find(
            a => a.ma === e.dataTransfer.getData("text/plain")
        ) || anhKeo;

        if (i >= 0 && anh) {
            datO(i);
            chonAnh(anh, i);
        }

        anhKeo = null;
    };

    ketQua.onpointerdown = e => {
        const i = oTai(toaDo(e));

        if (i >= 0) {
            datO(i);
            ketQua.setPointerCapture(e.pointerId);
            ketQua.dataset.keo = String(i);
        }
    };

    ketQua.onpointerup = e => {
        if (ketQua.dataset.keo === undefined) return;

        const tu = Number(ketQua.dataset.keo);
        const den = oTai(toaDo(e));

        delete ketQua.dataset.keo;

        if (den >= 0 && tu !== den) {
            [cacO[tu], cacO[den]] = [
                cacO[den],
                cacO[tu]
            ];

            datO(den);
        }
    };

    ketQua.onkeydown = e => {
        if (
            cheDo === "khung" &&
            ["ArrowRight", "ArrowLeft"].includes(e.key)
        ) {
            e.preventDefault();

            datO(
                oChon +
                (e.key === "ArrowRight" ? 1 : -1)
            );
        }
    };

    el("truoc").onclick = () => datO(oChon - 1);
    el("sau").onclick = () => datO(oChon + 1);

    for (const ten of ["phong", "ngang", "doc"]) {
        el(ten).oninput = () => {
            if (cacO[oChon]) {
                cacO[oChon][ten] = Number(
                    el(ten).value
                );

                veAnh();
            }
        };
    }

    el("mau").onchange = veAnh;
    el("don").onclick = () => doiCheDo("don");
    el("khung").onclick = () => doiCheDo("khung");

    for (const item of khung) {
        const b = taoNut(item.ten, () => {
            const cu = cacO;

            boCuc = item;

            cacO = Array.from(
                { length: item.so },
                (_, i) => cu[i] || null
            );

            oChon = 0;

            for (const nut of el("cac_khung").children) {
                nut.setAttribute(
                    "aria-pressed",
                    String(nut === b)
                );
            }

            doiCheDo("khung");
        });

        b.setAttribute(
            "aria-pressed",
            String(item === boCuc)
        );

        el("cac_khung").append(b);
    }

    async function demNguoc(so, ma) {
        for (let n = so; n > 0; n--) {
            let con = 1000;
            let truoc = performance.now();

            while (con > 0) {
                if (ma !== luot || !phong.open) {
                    throw Error("Đã dừng chụp.");
                }

                const now = performance.now();

                if (sanSang() && !document.hidden) {
                    el("dem").textContent = String(n);
                    con -= Math.min(now - truoc, 150);

                } else {
                    el("dem").textContent = "";

                    bao(
                        "Đang tạm dừng. Đưa người đã thử tóc trở lại khung để tiếp tục, hoặc bấm Dừng chụp."
                    );
                }

                truoc = now;
                await doi(80);
            }
        }

        while (!sanSang() || document.hidden) {
            if (ma !== luot || !phong.open) {
                throw Error("Đã dừng chụp.");
            }

            bao("Đang chờ nhìn thấy người đã thử tóc…");

            await doi(100);
        }

        if (ma !== luot || !phong.open) {
            throw Error("Đã dừng chụp.");
        }
    }

    async function chup() {
        if (dangChup) return;

        await anhSanSang;

        if (dangChup) return;

        dangChup = true;

        const ma = ++luot;
        const so = cheDo === "khung"
            ? boCuc.so
            : 1;

        el("chup").disabled = true;
        el("huy").disabled = false;

        for (const ten of ["don", "khung", "hen_gio"]) {
            el(ten).disabled = true;
        }

        for (const b of el("cac_khung").children) {
            b.disabled = true;
        }

        try {
            for (let i = 0; i < so; i++) {
                bao(
                    "Lượt " + (i + 1) + "/" + so +
                    " · Sẵn sàng tạo dáng."
                );

                await demNguoc(
                    Number(el("hen_gio").value),
                    ma
                );
                                if (biKhoa || !conKieuToc()) {
                    khoaPhongChup();

                    throw Error(
                        "Đã mất kiểu tóc. Thoát về phòng thử tóc để quét lại."
                    );
                }

                const goc = nguon();

                if (!goc.width || !goc.height) {
                    throw Error(
                        "Camera chưa có hình ảnh."
                    );
                }

                const c = document.createElement("canvas");

                c.width = Math.min(1280, goc.width);
                c.height = Math.round(
                    c.width * goc.height / goc.width
                );

                const ctx = c.getContext("2d");

                ctx.translate(c.width, 0);
                ctx.scale(-1, 1);

                ctx.drawImage(
                    goc,
                    0,
                    0,
                    c.width,
                    c.height
                );

                const tep = await blobCanvas(
                    c,
                    "image/jpeg"
                );

                const nho = document.createElement("canvas");

                nho.width = 200;
                nho.height = Math.round(
                    200 * c.height / c.width
                );

                nho.getContext("2d").drawImage(
                    c,
                    0,
                    0,
                    nho.width,
                    nho.height
                );

                const anh = {
                    ma: crypto.randomUUID
                        ? crypto.randomUUID()
                        : Date.now() + "-" + Math.random(),

                    luc: Date.now(),
                    tep,

                    nho: await blobCanvas(
                        nho,
                        "image/jpeg"
                    )
                };

                await ghiKho(anh);

                cacAnh.unshift(anh);
                veKhay();

                if (cheDo === "don") {
                    await chonAnh(anh);
                }

                el("dem").textContent = "✓";

                el("xem_camera").parentElement
                    .classList.add("ca-nhay");

                await doi(220);

                el("xem_camera").parentElement
                    .classList.remove("ca-nhay");
            }

            bao(
                "Đã chụp xong. Bạn có thể chụp thêm hoặc chọn ảnh trong khay để ghép."
            );

        } catch (e) {
            loi(e);

        } finally {
            dangChup = false;

            el("chup").disabled = false;
            el("huy").disabled = true;
            el("dem").textContent = "";

            for (const ten of ["don", "khung", "hen_gio"]) {
                el(ten).disabled = false;
            }

            for (const b of el("cac_khung").children) {
                b.disabled = false;
            }
        }
    }

    el("chup").onclick = chup;

    el("huy").onclick = () => {
        luot++;
    };

    function taiBlob(blob, ten) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");

        a.href = url;
        a.download = ten;
        a.click();

        setTimeout(
            () => URL.revokeObjectURL(url),
            30000
        );
    }

    async function tepXuat() {
        if (!coTheXuat) {
            throw Error(
                "Hãy chọn đủ ảnh trước khi xuất."
            );
        }

        return blobCanvas(
            banXuat,
            "image/" + el("dinh_dang").value
        );
    }

    function tenTep() {
        return "haul-toc-" + Date.now() + "." +
            (
                el("dinh_dang").value === "jpeg"
                    ? "jpg"
                    : "png"
            );
    }

    async function luuLenMay(blob, kieu, ten) {
        const form = new FormData();

        form.append("anh", blob, "anh.png");
        form.append("kieu", kieu);
        form.append("ten", ten);

        const token = document.querySelector(
            "#bao_ve_quet [name=csrfmiddlewaretoken]"
        )?.value;

        const r = await fetch(
            phong.dataset.luu,
            {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-CSRFToken": token || ""
                },
                body: form
            }
        );

        if (!r.headers.get("content-type")?.includes(
            "application/json"
        )) {
            throw Error(
                "Chưa lưu được ảnh. Kiểm tra phiên đăng nhập và giới hạn tải lên."
            );
        }

        const k = await r.json();

        if (!r.ok || !k.thanh_cong) {
            throw Error(
                k.thong_bao || "Không lưu được ảnh."
            );
        }

        return k;
    }

    el("tai").onclick = async () => {
        try {
            taiBlob(
                await tepXuat(),
                tenTep()
            );

        } catch (e) {
            loi(e);
        }
    };

    el("luu").onclick = async () => {
        if (dangLuu) return;

        dangLuu = true;
        capNhatNut();

        const phien = maBanXuat;

        try {
            await luuLenMay(
                await tepXuat(),
                cheDo === "khung" ? "khung" : "don",
                cheDo === "khung"
                    ? "Khung ảnh thử tóc"
                    : "Ảnh thử tóc"
            );

            anhDaLuu = phien;

            bao(
                "Đã lưu vào Ảnh của tôi trên trang chủ."
            );

        } catch (e) {
            loi(e);

        } finally {
            dangLuu = false;
            capNhatNut();
        }
    };

    function taiVaMo(dich) {
        if (!tepChiaSeSanSang) {
            bao(
                "Ảnh đang được chuẩn bị. Vui lòng thử lại sau giây lát."
            );
            return;
        }

        if (dich) {
            window.open(
                dich === "Facebook"
                    ? "https://www.facebook.com/"
                    : "https://www.instagram.com/",
                "_blank",
                "noopener,noreferrer"
            );
        }

        taiBlob(
            tepChiaSeSanSang,
            tepChiaSeSanSang.name
        );

        bao(
            "Đã yêu cầu tải ảnh. " +
            (
                dich
                    ? "Trong " + dich +
                      ", chọn Tạo bài viết rồi chọn ảnh vừa tải. Trang web không tự đính kèm ảnh."
                    : "Mở ứng dụng bạn muốn và chọn ảnh vừa tải để đăng."
            )
        );
    }

    async function chiaSe(dich) {
        if (dangChiaSe) return;

        const file = tepChiaSeSanSang;

        if (!file) {
            bao(
                "Ảnh đang được chuẩn bị. Vui lòng thử lại sau giây lát."
            );
            return;
        }

        let hoTro = false;

        try {
            hoTro =
                !!navigator.share &&
                !!navigator.canShare?.({
                    files: [file]
                });
        } catch {}

        if (!hoTro) {
            taiVaMo(dich);
            return;
        }

        dangChiaSe = true;
        capNhatNut();

        bao(
            dich
                ? "Chọn " + dich +
                  " trong bảng chia sẻ nếu ứng dụng có xuất hiện."
                : "Chọn ứng dụng trong bảng chia sẻ của thiết bị."
        );

        try {
            // Gọi trực tiếp trong thao tác bấm.
            await navigator.share({
                files: [file],
                title: "Ảnh thử tóc HAULONGHAIR"
            });

            bao(
                "Đã chuyển ảnh qua bảng chia sẻ. Hoàn tất thao tác trong ứng dụng; website không xác nhận được ảnh đã đăng."
            );

        } catch (e) {
            if (e.name === "AbortError") {
                bao(
                    "Chia sẻ đã đóng hoặc không có ứng dụng phù hợp. Bạn vẫn có thể tải ảnh để đăng."
                );
            } else {
                bao(
                    "Thiết bị chưa chia sẻ được ảnh trực tiếp. "
                );
            }

            el("thong_bao").append(
                taoNut(
                    dich
                        ? "Tải ảnh và mở " + dich
                        : "Tải ảnh để đăng",
                    () => taiVaMo(dich)
                )
            );

        } finally {
            dangChiaSe = false;
            capNhatNut();
        }
    }

    el("dinh_dang").onchange = () => {
        chuanBiChiaSe();
        capNhatNut();
    };

    el("chia_se").onclick = () => chiaSe("");
    el("facebook").onclick = () => chiaSe("Facebook");
    el("instagram").onclick = () => chiaSe("Instagram");

    el("dong_anh_lon").onclick = () => {
        el("anh_lon").hidden = true;

        if (chanTro) {
            URL.revokeObjectURL(chanTro);
        }

        chanTro = null;
    };
        function khoaPhongChup() {
        if (biKhoa) return;

        biKhoa = true;

        // Dừng lượt chụp và việc chuẩn bị ảnh chia sẻ.
        luot++;
        clearTimeout(henChiaSe);
        tepChiaSeSanSang = null;

        el("dem").textContent = "";

        // Khóa toàn bộ khu vực chức năng.
        el("noi_dung").hidden = true;
        el("noi_dung").inert = true;

        // Chỉ để thông báo và nút thoát.
        el("bao_mat_toc").hidden = false;
        el("dong").disabled = false;
        el("dong").focus();
    }

    function xemTrucTiep() {
                if (!phong.open) return;

        if (!conKieuToc()) {
            khoaPhongChup();
            return;
        }

        const c = nguon();
        

        if (c.width && c.height) {
            if (
                xem.width !== c.width ||
                xem.height !== c.height
            ) {
                xem.width = c.width;
                xem.height = c.height;
            }

            const ctx = xem.getContext("2d");

            ctx.setTransform(
                -1,
                0,
                0,
                1,
                xem.width,
                0
            );

            ctx.drawImage(c, 0, 0);
            ctx.resetTransform();
        }

        vong = requestAnimationFrame(
            xemTrucTiep
        );
    }

    nutMo.onclick = async () => {
        if (!sanSang()) {
            alert(
                "Chọn kiểu tóc và giữ người đã quét trong khung trước khi mở chụp ảnh."
            );
            return;
        }
                // Chỉ mở lại chức năng khi đã có tóc hợp lệ.
        biKhoa = false;

        el("noi_dung").hidden = false;
        el("noi_dung").inert = false;
        el("bao_mat_toc").hidden = true;

        tieuDiemCu = document.activeElement;

        phong.showModal();

        
        doiCheDo(cheDo);
        xemTrucTiep();

        await anhSanSang;

        if (!boNho) {
            bao(
                "Trình duyệt không hỗ trợ lưu khay ảnh lâu dài. Hãy lưu hoặc tải ảnh trước khi đóng trang."
            );
        }
    };

    el("dong").onclick = () => {
        phong.close();
    };

    phong.addEventListener("close", () => {
        luot++;
        cancelAnimationFrame(vong);
        el("dem").textContent = "";
        tieuDiemCu?.focus();
    });

    veAnh();
}