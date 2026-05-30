import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import os
import winreg
import tempfile
import shutil
import json


class MiniPDF:
    def __init__(self, root):
        self.root = root
        self.root.title("mini-pdf")
        self.root.geometry("1200x800")

        self.doc = None
        self.current_path = None
        self.current_page = 0
        self.zoom = 1.5
        self.selected_font = None
        self.page_images = {}
        self.system_fonts = self._load_system_fonts()
        self._drag_origin = None
        self._selection = None
        self._config_path = os.path.join(os.environ.get("APPDATA", ""), "mini-pdf", "config.json")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        # 툴바
        toolbar = tk.Frame(self.root, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        tk.Button(toolbar, text="열기", command=self.open_pdf).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(toolbar, text="저장", command=self.save_pdf).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(toolbar, text="다른 이름으로 저장", command=self.save_pdf_as).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        tk.Button(toolbar, text="텍스트 교체", command=self.replace_text_mode).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(toolbar, text="이미지 삽입", command=self.insert_image).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        tk.Button(toolbar, text="폰트 선택", command=self.choose_font).pack(side=tk.LEFT, padx=2, pady=2)
        self.font_label = tk.Label(toolbar, text="폰트: 기본", fg="gray")
        self.font_label.pack(side=tk.LEFT, padx=4)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        tk.Button(toolbar, text="◀", command=self.prev_page).pack(side=tk.LEFT, padx=2, pady=2)
        self.page_label = tk.Label(toolbar, text="0 / 0")
        self.page_label.pack(side=tk.LEFT, padx=4)
        tk.Button(toolbar, text="▶", command=self.next_page).pack(side=tk.LEFT, padx=2, pady=2)

        # 줌
        tk.Label(toolbar, text="  줌:").pack(side=tk.LEFT)
        self.zoom_var = tk.StringVar(value="150%")
        zoom_cb = ttk.Combobox(toolbar, textvariable=self.zoom_var, values=["75%", "100%", "125%", "150%", "200%"], width=6)
        zoom_cb.pack(side=tk.LEFT, padx=2)
        zoom_cb.bind("<<ComboboxSelected>>", self.change_zoom)

        # 메인 영역
        main = tk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True)

        # 캔버스 + 스크롤
        self.canvas = tk.Canvas(main, bg="#888")
        vscroll = ttk.Scrollbar(main, orient=tk.VERTICAL, command=self.canvas.yview)
        hscroll = ttk.Scrollbar(self.root, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)

        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        hscroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)

        # 상태바
        self.status = tk.Label(self.root, text="PDF 파일을 열어주세요.", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    # ── 파일 ──────────────────────────────────────────
    def open_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not path:
            return
        self.doc = fitz.open(path)
        self.current_path = path
        self.current_page = 0
        self.page_images.clear()
        self.render_page()
        self.root.title(f"mini-pdf — {os.path.basename(path)}")
        self.status.config(text=f"열림: {path}")

    def save_pdf(self):
        if not self.doc:
            return
        if not self.current_path:
            self.save_pdf_as()
            return
        self._save_to(self.current_path)

    def save_pdf_as(self):
        if not self.doc:
            return
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if not path:
            return
        self._save_to(path)

    def _save_to(self, path):
        """임시 파일에 저장 후 대상 경로로 교체 — 열린 파일에 덮어쓰기 가능."""
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(tmp_fd)
        try:
            self.doc.save(tmp_path, garbage=4, deflate=True)
            self.doc.close()
            shutil.move(tmp_path, path)
            self.doc = fitz.open(path)
            self.current_path = path
            self.page_images.clear()
            self.render_page()
            self.root.title(f"mini-pdf — {os.path.basename(path)}")
            self.status.config(text=f"저장됨: {path}")
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            messagebox.showerror("저장 오류", str(e))

    # ── 렌더링 ─────────────────────────────────────────
    def render_page(self):
        if not self.doc:
            return
        page = self.doc[self.current_page]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.tk_img = ImageTk.PhotoImage(img)
        self.page_images[self.current_page] = self.tk_img

        self.canvas.delete("all")
        self.canvas.create_image(10, 10, anchor=tk.NW, image=self.tk_img)
        self.canvas.configure(scrollregion=(0, 0, pix.width + 20, pix.height + 20))
        self.page_label.config(text=f"{self.current_page + 1} / {len(self.doc)}")

    def change_zoom(self, _=None):
        val = self.zoom_var.get().replace("%", "")
        try:
            self.zoom = int(val) / 100
            self.page_images.clear()
            self.render_page()
        except ValueError:
            pass

    # ── 페이지 이동 ────────────────────────────────────
    def prev_page(self):
        if self.doc and self.current_page > 0:
            self.current_page -= 1
            self.render_page()

    def next_page(self):
        if self.doc and self.current_page < len(self.doc) - 1:
            self.current_page += 1
            self.render_page()

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    # ── 폰트 ──────────────────────────────────────────
    def _load_system_fonts(self):
        fonts = {}
        font_dirs = [
            r"C:\Windows\Fonts",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Windows\Fonts"),
        ]
        for d in font_dirs:
            if not os.path.isdir(d):
                continue
            for f in os.listdir(d):
                if f.lower().endswith(".ttf"):
                    name = os.path.splitext(f)[0]
                    fonts[name] = os.path.join(d, f)
        return dict(sorted(fonts.items(), key=lambda x: x[0].lower()))

    def _load_config(self):
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            font_path = cfg.get("font")
            if font_path and os.path.exists(font_path):
                self.selected_font = font_path
                name = os.path.splitext(os.path.basename(font_path))[0]
                self.font_label.config(text=f"폰트: {name}", fg="black")
        except Exception:
            pass

    def _save_config(self):
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump({"font": self.selected_font}, f)
        except Exception:
            pass

    def _on_close(self):
        self._save_config()
        self.root.destroy()

    def choose_font(self):
        dialog = FontPickerDialog(self.root, self.system_fonts)
        self.root.wait_window(dialog.top)
        if dialog.result:
            self.selected_font = dialog.result
            name = os.path.splitext(os.path.basename(dialog.result))[0]
            self.font_label.config(text=f"폰트: {name}", fg="black")
            self.status.config(text=f"폰트 설정: {dialog.result}")
            self._save_config()

    # ── 드래그 선택 ────────────────────────────────────
    def _drag_start(self, event):
        if not self.doc:
            return
        self._drag_origin = (event.x, event.y)
        self._selection = None
        self.canvas.delete("selection")

    def _drag_move(self, event):
        if not self._drag_origin:
            return
        x0, y0 = self._drag_origin
        x1, y1 = event.x, event.y
        self.canvas.delete("selection")
        self.canvas.create_rectangle(
            x0, y0, x1, y1,
            outline="#1a7fd4", width=2,
            fill="#1a7fd4", stipple="gray25",
            tags="selection"
        )

    def _drag_end(self, event):
        if not self._drag_origin:
            return
        x0, y0 = self._drag_origin
        x1, y1 = event.x, event.y
        self._drag_origin = None

        # 너무 작은 드래그는 무시
        if abs(x1 - x0) < 5 and abs(y1 - y0) < 5:
            self.canvas.delete("selection")
            self._selection = None
            return

        self._selection = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

        # 선택 영역 내 텍스트 추출해서 상태바에 미리보기
        page = self.doc[self.current_page]
        rect = self._canvas_to_pdf_rect(*self._selection)
        text = page.get_text("text", clip=rect).strip()
        preview = text[:60].replace("\n", " ") + ("…" if len(text) > 60 else "")
        if preview:
            self.status.config(text=f"선택됨: \"{preview}\"  →  텍스트 교체 버튼을 눌러주세요.")
        else:
            self.status.config(text="선택 영역에 텍스트가 없습니다.")

    def _canvas_to_pdf_rect(self, cx0, cy0, cx1, cy1):
        def c2p(v): return (v - 10) / self.zoom
        return fitz.Rect(c2p(cx0), c2p(cy0), c2p(cx1), c2p(cy1))

    # ── 텍스트 교체 ────────────────────────────────────
    def replace_text_mode(self):
        if not self.doc:
            messagebox.showwarning("알림", "먼저 PDF를 열어주세요.")
            return
        if not self._selection:
            self.status.config(text="먼저 문서에서 교체할 영역을 드래그로 선택하세요.")
            return

        page = self.doc[self.current_page]
        rect = self._canvas_to_pdf_rect(*self._selection)
        orig_text = page.get_text("text", clip=rect).strip()

        # 원본 폰트 크기 감지
        detected_size = 11.0
        try:
            blocks = page.get_text("dict", clip=rect)["blocks"]
            sizes = [
                span["size"]
                for b in blocks if b.get("type") == 0
                for line in b["lines"]
                for span in line["spans"]
                if span["text"].strip()
            ]
            if sizes:
                detected_size = round(sum(sizes) / len(sizes), 1)
        except Exception:
            pass

        dialog = ReplaceDialog(self.root, orig_text, detected_size)
        self.root.wait_window(dialog.top)
        if not dialog.result:
            return

        new_text, font_size, line_height, align = dialog.result

        try:
            # redact으로 원본 텍스트 스트림에서 물리적 제거
            page.add_redact_annot(rect, fill=(1, 1, 1))
            page.apply_redacts(images=fitz.PDF_REDACT_IMAGE_NONE)

            if self.selected_font:
                fontname = f"F{page.number}_{abs(hash(str(rect)))}"[:16]
                page.insert_font(fontname=fontname, fontfile=self.selected_font)
            else:
                fontname = "helv"

            rc = page.insert_textbox(
                rect,
                new_text,
                fontsize=font_size,
                fontname=fontname,
                color=(0, 0, 0),
                align=align,
                lineheight=line_height,
            )
            if rc < 0:
                self.status.config(text="경고: 텍스트가 영역을 벗어났습니다. 폰트 크기를 줄여보세요.")
                return
        except Exception as e:
            messagebox.showerror("텍스트 삽입 오류", str(e))
            return

        self._selection = None
        self.canvas.delete("selection")
        self.page_images.clear()
        self.render_page()
        self.status.config(text="텍스트 교체 완료.")

    # ── 이미지 삽입 ────────────────────────────────────
    def insert_image(self):
        if not self.doc:
            messagebox.showwarning("알림", "먼저 PDF를 열어주세요.")
            return
        img_path = filedialog.askopenfilename(
            title="삽입할 이미지 선택",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All files", "*.*")]
        )
        if not img_path:
            return

        dialog = ImagePlaceDialog(self.root)
        self.root.wait_window(dialog.top)
        if not dialog.result:
            return

        x0, y0, x1, y1 = dialog.result
        page = self.doc[self.current_page]
        rect = fitz.Rect(x0, y0, x1, y1)
        page.insert_image(rect, filename=img_path)

        self.page_images.clear()
        self.render_page()
        self.status.config(text=f"이미지 삽입 완료: {os.path.basename(img_path)}")


# ── 다이얼로그 ──────────────────────────────────────────

class FontPickerDialog:
    def __init__(self, parent, system_fonts):
        self.result = None
        self.system_fonts = system_fonts

        self.top = tk.Toplevel(parent)
        self.top.title("폰트 선택")
        self.top.geometry("400x500")
        self.top.grab_set()

        # 검색창
        search_frame = tk.Frame(self.top)
        search_frame.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(search_frame, text="검색:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._filter)
        tk.Entry(search_frame, textvariable=self.search_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # 리스트
        list_frame = tk.Frame(self.top)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, selectmode=tk.SINGLE, font=("", 10))
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.bind("<Double-Button-1>", lambda e: self._ok())

        self._all_names = list(system_fonts.keys())
        self._populate(self._all_names)

        btn_frame = tk.Frame(self.top)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="선택", command=self._ok, width=10).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="취소", command=self.top.destroy, width=10).pack(side=tk.LEFT, padx=4)

    def _populate(self, names):
        self.listbox.delete(0, tk.END)
        for name in names:
            self.listbox.insert(tk.END, name)

    def _filter(self, *_):
        q = self.search_var.get().lower()
        filtered = [n for n in self._all_names if q in n.lower()]
        self._populate(filtered)

    def _ok(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        q = self.search_var.get().lower()
        visible = [n for n in self._all_names if q in n.lower()]
        name = visible[sel[0]]
        self.result = self.system_fonts[name]
        self.top.destroy()


class ReplaceDialog:
    ALIGN_OPTIONS = [("왼쪽", 0), ("가운데", 1), ("오른쪽", 2), ("양쪽", 3)]

    def __init__(self, parent, orig_text, detected_size=11.0):
        self.result = None
        self.top = tk.Toplevel(parent)
        self.top.title("텍스트 교체")
        self.top.grab_set()

        tk.Label(self.top, text="원본 텍스트:", anchor=tk.W).pack(fill=tk.X, padx=10, pady=(10, 0))
        orig = tk.Text(self.top, height=4, width=60, state=tk.NORMAL, bg="#f0f0f0")
        orig.insert(tk.END, orig_text)
        orig.config(state=tk.DISABLED)
        orig.pack(padx=10, pady=4)

        tk.Label(self.top, text="교체할 한글 텍스트:", anchor=tk.W).pack(fill=tk.X, padx=10)
        self.new_text = tk.Text(self.top, height=4, width=60)
        self.new_text.pack(padx=10, pady=4)

        opts = tk.Frame(self.top)
        opts.pack(fill=tk.X, padx=10, pady=4)

        # 폰트 크기 (원본 감지값 기본)
        tk.Label(opts, text="폰트 크기:").grid(row=0, column=0, sticky=tk.W, padx=(0, 4))
        self.font_size = tk.Spinbox(opts, from_=6, to=72, width=5, format="%.1f", increment=0.5)
        self.font_size.delete(0, tk.END)
        self.font_size.insert(0, str(detected_size))
        self.font_size.grid(row=0, column=1, sticky=tk.W, padx=(0, 16))

        # 행간
        tk.Label(opts, text="행간:").grid(row=0, column=2, sticky=tk.W, padx=(0, 4))
        self.line_height = tk.Spinbox(opts, from_=1.0, to=3.0, width=5, format="%.1f", increment=0.1)
        self.line_height.delete(0, tk.END)
        self.line_height.insert(0, "1.4")
        self.line_height.grid(row=0, column=3, sticky=tk.W, padx=(0, 16))

        # 정렬
        tk.Label(opts, text="정렬:").grid(row=0, column=4, sticky=tk.W, padx=(0, 4))
        self.align_var = tk.IntVar(value=3)
        for label, val in self.ALIGN_OPTIONS:
            tk.Radiobutton(opts, text=label, variable=self.align_var, value=val).grid(
                row=0, column=5 + val, sticky=tk.W
            )

        btn_frame = tk.Frame(self.top)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="교체", command=self._ok, width=10).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="취소", command=self.top.destroy, width=10).pack(side=tk.LEFT, padx=4)

    def _ok(self):
        text = self.new_text.get("1.0", tk.END).strip()
        try:
            size = float(self.font_size.get())
        except ValueError:
            size = 11.0
        try:
            lh = float(self.line_height.get())
        except ValueError:
            lh = 1.4
        if text:
            self.result = (text, size, lh, self.align_var.get())
        self.top.destroy()


class ImagePlaceDialog:
    def __init__(self, parent):
        self.result = None
        self.top = tk.Toplevel(parent)
        self.top.title("이미지 배치 (PDF 좌표, pt)")
        self.top.grab_set()

        fields = [("왼쪽 (x0)", "50"), ("위 (y0)", "50"), ("오른쪽 (x1)", "250"), ("아래 (y1)", "200")]
        self.entries = {}
        for label, default in fields:
            row = tk.Frame(self.top)
            row.pack(fill=tk.X, padx=16, pady=3)
            tk.Label(row, text=label, width=14, anchor=tk.W).pack(side=tk.LEFT)
            e = tk.Entry(row, width=10)
            e.insert(0, default)
            e.pack(side=tk.LEFT)
            self.entries[label] = e

        btn_frame = tk.Frame(self.top)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="삽입", command=self._ok, width=10).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="취소", command=self.top.destroy, width=10).pack(side=tk.LEFT, padx=4)

    def _ok(self):
        try:
            vals = [float(e.get()) for e in self.entries.values()]
            self.result = tuple(vals)
        except ValueError:
            pass
        self.top.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MiniPDF(root)
    root.mainloop()
