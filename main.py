import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import os
import winreg


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

        self._build_ui()

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

        self.canvas.bind("<Button-1>", self.on_canvas_click)
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
        self.doc.save(self.current_path, garbage=4, deflate=True, incremental=False)
        self.status.config(text=f"저장됨: {self.current_path}")

    def save_pdf_as(self):
        if not self.doc:
            return
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if not path:
            return
        self.doc.save(path, garbage=4, deflate=True)
        self.current_path = path
        self.root.title(f"mini-pdf — {os.path.basename(path)}")
        self.status.config(text=f"저장됨: {path}")

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
                if f.lower().endswith((".ttf", ".otf")):
                    name = os.path.splitext(f)[0]
                    fonts[name] = os.path.join(d, f)
        return dict(sorted(fonts.items(), key=lambda x: x[0].lower()))

    def choose_font(self):
        dialog = FontPickerDialog(self.root, self.system_fonts)
        self.root.wait_window(dialog.top)
        if dialog.result:
            self.selected_font = dialog.result
            name = os.path.splitext(os.path.basename(dialog.result))[0]
            self.font_label.config(text=f"폰트: {name}", fg="black")
            self.status.config(text=f"폰트 설정: {dialog.result}")

    # ── 텍스트 교체 ────────────────────────────────────
    def replace_text_mode(self):
        if not self.doc:
            messagebox.showwarning("알림", "먼저 PDF를 열어주세요.")
            return
        self.status.config(text="교체할 텍스트 블록을 클릭하세요.")
        self._mode = "replace"

    def on_canvas_click(self, event):
        if not self.doc or not hasattr(self, "_mode"):
            return
        if self._mode == "replace":
            self._do_replace_at(event.x, event.y)

    def _do_replace_at(self, cx, cy):
        page = self.doc[self.current_page]
        # 캔버스 좌표 → PDF 좌표
        px = (cx - 10) / self.zoom
        py = (cy - 10) / self.zoom
        point = fitz.Point(px, py)

        # 클릭 위치의 텍스트 블록 찾기
        blocks = page.get_text("blocks")
        target = None
        for b in blocks:
            x0, y0, x1, y1, text, *_ = b
            if x0 <= px <= x1 and y0 <= py <= y1:
                target = b
                break

        if not target:
            self.status.config(text="텍스트 블록을 찾지 못했습니다. 다른 위치를 클릭해보세요.")
            return

        x0, y0, x1, y1, orig_text, *_ = target
        orig_text = orig_text.strip()

        # 번역 텍스트 입력 다이얼로그
        dialog = ReplaceDialog(self.root, orig_text)
        self.root.wait_window(dialog.top)
        if not dialog.result:
            return

        new_text, font_size = dialog.result

        # 원본 텍스트 가리기 (흰 사각형)
        rect = fitz.Rect(x0, y0, x1, y1)
        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))

        # 새 텍스트 삽입
        font_args = {}
        if self.selected_font:
            font_args["fontfile"] = self.selected_font
            font_args["fontname"] = "custom"
        else:
            font_args["fontname"] = "helv"

        page.insert_textbox(
            rect,
            new_text,
            fontsize=font_size,
            color=(0, 0, 0),
            align=0,
            **font_args,
        )

        self._mode = None
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
    def __init__(self, parent, orig_text):
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

        size_frame = tk.Frame(self.top)
        size_frame.pack(fill=tk.X, padx=10, pady=4)
        tk.Label(size_frame, text="폰트 크기:").pack(side=tk.LEFT)
        self.font_size = tk.Spinbox(size_frame, from_=6, to=72, value=11, width=5)
        self.font_size.pack(side=tk.LEFT, padx=4)

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
        if text:
            self.result = (text, size)
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
