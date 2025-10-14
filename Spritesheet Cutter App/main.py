import os
import platform
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.font as tkfont
from tkinter import filedialog

from cutter import ImageProcessor

cwd = os.getcwd()

# ---- UI knobs ----
RIGHT_PANEL_WIDTH = 320
WINDOW_SIZE = "1400x900+120+60"
MAC_SCALING = 2.0          # Retina-friendly (adjust 1.75–2.5 to taste)
DEFAULT_FONT_SIZE = 12

# ---------- Styling ----------
def setup_style(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # Base fonts
    try:
        base_font = tkfont.nametofont("TkDefaultFont")
        base_font.configure(size=DEFAULT_FONT_SIZE)
    except tk.TclError:
        pass
    try:
        heading_font = tkfont.nametofont("TkHeadingFont")
        heading_font.configure(size=DEFAULT_FONT_SIZE, weight="bold")
    except tk.TclError:
        pass

    # Palette
    BG   = "#f7f7fb"
    CARD = "#ffffff"
    SUBT = "#6b7280"
    TEXT = "#111827"

    root.configure(background=BG)
    style.configure(".", background=BG, foreground=TEXT)

    # Card frames
    style.configure("Card.TFrame", background=CARD, relief="groove", borderwidth=1)

    # Group boxes
    style.configure("Group.TLabelframe", background=CARD, relief="groove", borderwidth=1)
    style.configure("Group.TLabelframe.Label", background=CARD, foreground=SUBT)

    # Header labels
    style.configure("Header.TLabel", background="#111827", foreground="#ffffff", padding=(8,6))
    style.configure("SubHeader.TLabel", background="#111827", foreground="#d1d5db", padding=(8,6))

    # Field labels / entries / buttons
    style.configure("Field.TLabel", background=CARD, foreground=SUBT, padding=(2,2))
    style.configure("TEntry", padding=(4,2))
    style.configure("TButton", padding=(8,6))

    return {"BG": BG, "CARD": CARD}

def _configure_scaling(root):
    """Fix tiny UI on Retina / allow easy global scaling."""
    if platform.system() == "Darwin":
        try:
            root.tk.call('tk', 'scaling', MAC_SCALING)
        except tk.TclError:
            pass

# ---------- App ----------
class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master=master)
        self.master = master
        self.grid(sticky="nsew")

        # Grid weights: canvas column expands
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # State
        self.filepath = None
        self.zoom_val = tk.IntVar(value=100)
        self.crop_option = tk.IntVar()
        self.options = {
            'Divide by TileSize': 1,
            'Divide in Rows & Columns': 2,
            'Custom Cropping': 3,
            'Rectangular Selection': 4
        }

        self.image = None            # Tk PhotoImage (display)
        self.lines = []              # overlay item IDs
        self.scale = 1.0             # display/original ratio
        self.imobject = None         # ImageProcessor
        self.original_imsize = (0, 0)

        # Vars
        self.x = tk.IntVar(); self.y = tk.IntVar()
        self.x1 = tk.IntVar(); self.y1 = tk.IntVar()
        self.tilewidth = tk.IntVar(value=24)
        self.tileheight = tk.IntVar(value=24)
        self.rows = tk.IntVar(); self.columns = tk.IntVar()
        self.imwidth = tk.IntVar(); self.imheight = tk.IntVar()

        self.first = None
        self.second = None
        self.drag = True

        # Build UI
        self.draw_frames()
        self.draw_editor()
        self.draw_canvas()
        self.draw_options_frame()
        self.draw_header_frame()
        self.draw_menu_frame()

        # Key bindings
        self.master.bind('<Up>', self._go_up)
        self.master.bind('<Down>', self._go_down)
        self.master.bind('<Enter>', self._bound_to_mousewheel)
        self.master.bind('<Leave>', self._unbound_to_mousewheel)

    # ---------- Layout ----------
    def draw_frames(self):
        # Center canvas area
        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.grid(row=0, column=1, rowspan=2, sticky='nsew', padx=(12, 0), pady=(12, 12))
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        self.canvas_frame.grid_rowconfigure(0, weight=1)

        # Right: editor + options as "cards"
        self.editor_frame = ttk.Frame(self, style="Card.TFrame", width=RIGHT_PANEL_WIDTH)
        self.editor_frame.grid(row=0, column=2, sticky='new', padx=(12, 12), pady=(12, 6))
        self.editor_frame.grid_propagate(False)

        self.options_frame = ttk.Frame(self, style="Card.TFrame", width=RIGHT_PANEL_WIDTH)
        self.options_frame.grid(row=1, column=2, sticky='new', padx=(12, 12), pady=(0, 12))
        self.options_frame.grid_propagate(False)

    def draw_editor(self):
        # Header card
        self.header_frame = ttk.Frame(self.editor_frame, style="Card.TFrame")
        self.header_frame.pack(fill="x", padx=8, pady=8)

        # Groups
        self.menu_group = ttk.Labelframe(self.editor_frame, text="Mode", style="Group.TLabelframe")
        self.menu_group.pack(fill="x", padx=8, pady=(0,8))

        self.variable_group = ttk.Labelframe(self.editor_frame, text="Parameters", style="Group.TLabelframe")
        self.variable_group.pack(fill="x", padx=8, pady=(0,8))

    def draw_canvas(self):
        self.scrolly = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL)
        self.scrolly.grid(row=0, column=1, sticky='ns')

        self.scrollx = ttk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        self.scrollx.grid(row=1, column=0, sticky='we')

        self.canvas = tk.Canvas(
            self.canvas_frame, bg='#242424',
            yscrollcommand=self.scrolly.set, xscrollcommand=self.scrollx.set,
            highlightthickness=0
        )
        self.canvas.grid(row=0, column=0, sticky='nsew')

        self.scrolly.configure(command=self.canvas.yview)
        self.scrollx.configure(command=self.canvas.xview)

        self.canvas.bind('<ButtonPress-1>', self._get_position)
        self.canvas.bind("<B1-Motion>", self._drag)

    def draw_options_frame(self):
        inner = ttk.Frame(self.options_frame, style="Card.TFrame")
        inner.pack(fill="x", padx=8, pady=8)

        self.open = ttk.Button(inner, text='Open', command=self.open_img)
        self.open.grid(row=0, column=0, padx=(0, 8), pady=(2, 8), sticky="ew")

        self.resize_btn = ttk.Button(inner, text='Resize', state=tk.DISABLED, command=self.resize_frame)
        self.resize_btn.grid(row=0, column=1, padx=(8, 0), pady=(2, 8), sticky="ew")

        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=1)

        self.scaler = ttk.Scale(self.options_frame, from_=5, to=400, orient=tk.HORIZONTAL, length=RIGHT_PANEL_WIDTH-40)
        self.scaler['variable'] = self.zoom_val
        self.scaler.set(100)
        self.scaler.bind("<ButtonRelease-1>", self.do_zoom)
        self.scaler.pack(padx=8, pady=(0, 10))
        self.scaler.pack_forget()  # shown after image open

    def draw_header_frame(self):
        for w in self.header_frame.winfo_children():
            w.destroy()
        self.header = ttk.Label(self.header_frame, text="No file", style="Header.TLabel", anchor="center")
        self.header.pack(fill="x")
        self.size = ttk.Label(self.header_frame, text="—", style="SubHeader.TLabel", anchor="center")
        self.size.pack(fill="x")

    def draw_menu_frame(self):
        for w in self.menu_group.winfo_children():
            w.destroy()
        r = 0
        for text, value in self.options.items():
            ttk.Radiobutton(
                self.menu_group, text=text, variable=self.crop_option,
                value=value, command=self.draw_variable_frame
            ).grid(row=r, column=0, sticky="w", padx=10, pady=4)
            r += 1
        self.menu_group.grid_columnconfigure(0, weight=1)
        self.crop_option.set(2)  # default to Rows & Columns
        self.draw_variable_frame()

    # Small helper to render a labeled field
    def _field(self, parent, row, label, var, width=8):
        ttk.Label(parent, text=label, style="Field.TLabel").grid(row=row, column=0, padx=(10,8), pady=4, sticky="w")
        e = ttk.Entry(parent, textvariable=var, width=width)
        e.grid(row=row, column=1, padx=(0,10), pady=4, sticky="w")
        parent.grid_columnconfigure(1, weight=1)
        self._last_entry = e
        return e

    def draw_variable_frame(self):
        for w in self.variable_group.winfo_children():
            w.destroy()

        if self.lines:
            for id_ in self.lines:
                self.canvas.delete(id_)
            self.lines.clear()
        self.first = None
        self.second = None

        opt = self.crop_option.get()

        if opt == 1:  # Tile size mode
            self._field(self.variable_group, 0, "Tile Width", self.tilewidth)
            self._field(self.variable_group, 1, "Tile Height", self.tileheight)
            ttk.Separator(self.variable_group, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(2,6))
            ttk.Button(self.variable_group, text='Draw Tiles', command=self.draw_tiles).grid(row=3, column=0, columnspan=2, padx=10, pady=4, sticky="ew")
            ttk.Button(self.variable_group, text='Cut Tiles', command=self.cut_tiles_by_tile).grid(row=4, column=0, columnspan=2, padx=10, pady=(0,6), sticky="ew")

        elif opt == 2:  # Rows/Cols
            self._field(self.variable_group, 0, "Num Rows", self.rows)
            self._field(self.variable_group, 1, "Num Columns", self.columns)
            ttk.Separator(self.variable_group, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(2,6))
            ttk.Button(self.variable_group, text='Draw Rows & Columns', command=self.draw_rc).grid(row=3, column=0, columnspan=2, padx=10, pady=4, sticky="ew")
            ttk.Button(self.variable_group, text='Cut Tiles', command=self.cut_tiles_by_rc).grid(row=4, column=0, columnspan=2, padx=10, pady=(0,6), sticky="ew")

        elif opt == 3:  # Custom (x,y,w,h)
            self.x.set(0); self.y.set(0); self.tilewidth.set(24); self.tileheight.set(24)
            self._field(self.variable_group, 0, "x", self.x)
            self._field(self.variable_group, 1, "y", self.y)
            self._field(self.variable_group, 2, "width", self.tilewidth)
            self._field(self.variable_group, 3, "height", self.tileheight)
            ttk.Separator(self.variable_group, orient="horizontal").grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=(2,6))
            ttk.Button(self.variable_group, text='Draw Rect', command=self.draw_rect).grid(row=5, column=0, columnspan=2, padx=10, pady=4, sticky="ew")
            ttk.Button(self.variable_group, text='Cut Tile', command=self.cut_tiles_custom).grid(row=6, column=0, columnspan=2, padx=10, pady=(0,6), sticky="ew")

        elif opt == 4:  # Rect selection (x,y,x1,y1)
            self.x.set(0); self.y.set(0); self.x1.set(0); self.y1.set(0)
            self.pos1 = self._field(self.variable_group, 0, "x", self.x)
            self.pos2 = self._field(self.variable_group, 1, "y", self.y)
            self.pos3 = self._field(self.variable_group, 2, "x1", self.x1)
            self.pos4 = self._field(self.variable_group, 3, "y1", self.y1)

            btnrow = ttk.Frame(self.variable_group)
            btnrow.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=(2,6))
            self.posbtn1 = ttk.Button(btnrow, text='Update Rect', command=self.update_rect)
            self.posbtn1.pack(side="left", expand=True, fill="x", padx=(0,4))
            self.posbtn2 = ttk.Button(btnrow, text='Clear Rect', command=self.clear_rect)
            self.posbtn2.pack(side="left", expand=True, fill="x", padx=(4,0))

            ttk.Button(self.variable_group, text='Cut Tile', command=self.cut_tiles_by_rect).grid(row=5, column=0, columnspan=2, padx=10, pady=(0,6), sticky="ew")

            for w in (self.pos1, self.pos2, self.pos3, self.pos4, self.posbtn1, self.posbtn2):
                w.config(state=tk.DISABLED)

    # ---------- File / zoom ----------
    def open_img(self):
        filetypes = (("Images","*.png *.jpg *.jpeg *.bmp *.gif"),)
        path = filedialog.askopenfilename(initialdir=cwd, filetypes=filetypes)
        if not path:
            return

        self.filepath = path
        self.imobject = ImageProcessor(self.filepath)

        self.image, _size = self.imobject.display_image()
        self.original_imsize = tuple(_size)
        self.scale = 1.0

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor='nw', image=self.image)

        self.header['text'] = os.path.basename(self.filepath)
        self.size['text'] = f'{_size[0]}x{_size[1]}'

        region = self.canvas.bbox("all")
        self.canvas.configure(scrollregion=region)

        self.resize_btn.config(state=tk.NORMAL)
        self.scaler.pack(padx=8, pady=(0, 10))  # reveal zoom slider

    def do_zoom(self, event=None):
        if not self.imobject:
            return

        if self.lines:
            for id_ in self.lines:
                self.canvas.delete(id_)
            self.lines.clear()

        factor = self.zoom_val.get()
        disp = self.imobject.zoom_image_for_display(factor)
        self.image = disp

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor='nw', image=self.image)

        self.scale = self.image.width() / float(self.original_imsize[0])

        region = self.canvas.bbox("all")
        self.canvas.configure(scrollregion=region)

    # ---------- Grid overlays (scale-aware) ----------
    def draw_tiles(self):
        if not self.image: return
        for id_ in self.lines: self.canvas.delete(id_)
        self.lines.clear()

        tile_w = max(1, self.tilewidth.get())
        tile_h = max(1, self.tileheight.get())

        disp_tile_w = tile_w * self.scale
        disp_tile_h = tile_h * self.scale

        im_w = self.image.width()
        im_h = self.image.height()

        y = 0
        while y <= im_h + 1:
            self.lines.append(self.canvas.create_line(0, y, im_w, y, fill='dodgerblue3'))
            y += disp_tile_h

        x = 0
        while x <= im_w + 1:
            self.lines.append(self.canvas.create_line(x, 0, x, im_h, fill='dodgerblue3'))
            x += disp_tile_w

    def draw_rc(self):
        if not self.image: return
        for id_ in self.lines: self.canvas.delete(id_)
        self.lines.clear()

        rows = max(1, int(self.rows.get() or 1))
        cols = max(1, int(self.columns.get() or 1))

        im_w = self.image.width()
        im_h = self.image.height()

        disp_cw = im_w / cols
        disp_ch = im_h / rows

        y = 0
        for _ in range(rows + 1):
            self.lines.append(self.canvas.create_line(0, y, im_w, y, fill='dodgerblue3'))
            y += disp_ch

        x = 0
        for _ in range(cols + 1):
            self.lines.append(self.canvas.create_line(x, 0, x, im_h, fill='dodgerblue3'))
            x += disp_cw

    def draw_rect(self):
        if not self.image: return
        for id_ in self.lines: self.canvas.delete(id_)
        self.lines.clear()

        x = self.x.get() * self.scale
        y = self.y.get() * self.scale
        w = self.tilewidth.get() * self.scale
        h = self.tileheight.get() * self.scale

        self.lines.append(self.canvas.create_rectangle(x, y, x + w, y + h, outline='dodgerblue3', width=2))

    def update_rect(self):
        if not self.image: return
        for id_ in self.lines: self.canvas.delete(id_)
        self.lines.clear()

        x  = self.x.get()  * self.scale
        y  = self.y.get()  * self.scale
        x1 = self.x1.get() * self.scale
        y1 = self.y1.get() * self.scale

        self.lines.append(self.canvas.create_rectangle(x, y, x1, y1, outline='dodgerblue3', width=2))

    def clear_rect(self):
        if self.lines:
            for id_ in self.lines:
                self.canvas.delete(id_)
            self.lines.clear()

        for w in (self.pos1, self.pos2, self.pos3, self.pos4, self.posbtn1, self.posbtn2):
            w.config(state=tk.DISABLED)

        self.first = None
        self.second = None

    # ---------- Mouse & cuts ----------
    def _get_position(self, event=None):
        if not self.image: return
        x, y = event.x, event.y
        opt = self.crop_option.get()
        if opt in (1, 2, 3):
            self.canvas.scan_mark(event.x, event.y)
            self.drag = True
        else:
            self.drag = False
            if not self.first:
                self.first = (x, y)
                self.x.set(int(x / self.scale))
                self.y.set(int(y / self.scale))
                self.lines.append(self.canvas.create_oval(x-1, y-1, x+2, y+2, fill='dodgerblue3'))
                self.posbtn2.config(state=tk.NORMAL)
            else:
                for w in (self.pos1, self.pos2, self.pos3, self.pos4, self.posbtn1):
                    w.config(state=tk.NORMAL)
                self.second = (x, y)
                self.x1.set(int(x / self.scale))
                self.y1.set(int(y / self.scale))
                self.update_rect()

    def cut_tiles_by_tile(self):
        if not self.image or not self.imobject: return
        twidth = max(1, int(self.tilewidth.get()))
        theight = max(1, int(self.tileheight.get()))
        self.imobject.dividebytile(twidth, theight, include_partial=False)

    def cut_tiles_by_rc(self):
        if not self.image or not self.imobject: return
        rows = max(1, int(self.rows.get() or 1))
        cols = max(1, int(self.columns.get() or 1))
        self.imobject.dividebyrc(rows, cols, include_partial=False)

    def cut_tiles_custom(self):
        if not self.image or not self.imobject: return
        x = int(self.x.get()); y = int(self.y.get())
        w = max(1, int(self.tilewidth.get()))
        h = max(1, int(self.tileheight.get()))
        self.imobject.dividecustom(x, y, w, h)

    def cut_tiles_by_rect(self):
        if not self.image or not self.imobject: return
        x  = int(self.x.get());  y  = int(self.y.get())
        x1 = int(self.x1.get()); y1 = int(self.y1.get())
        self.imobject.dividebyrect(x, y, x1, y1)

    # ---------- Resize tools ----------
    def resize_frame(self):
        for id_ in self.lines: self.canvas.delete(id_)
        self.lines.clear()

        for widget in self.editor_frame.winfo_children(): widget.destroy()
        self.draw_editor()  # rebuild card scaffolding

        self.imwidth.set(self.original_imsize[0])
        self.imheight.set(self.original_imsize[1])

        # Simple resize UI inside a card
        info = ttk.Label(self.editor_frame, text=f'Current Size : {self.original_imsize[0]}x{self.original_imsize[1]}')
        info.pack(padx=8, pady=(8,6), anchor="center")

        rf = ttk.Frame(self.editor_frame, style="Card.TFrame"); rf.pack(fill="x", padx=8, pady=(0,8))
        ttk.Label(rf, text='width', style="Field.TLabel").grid(row=0, column=0, padx=(10,8), pady=6, sticky="w")
        ttk.Entry(rf, width=10, textvariable=self.imwidth).grid(row=0, column=1, padx=(0,10), pady=6, sticky="w")
        ttk.Label(rf, text='height', style="Field.TLabel").grid(row=1, column=0, padx=(10,8), pady=6, sticky="w")
        ttk.Entry(rf, width=10, textvariable=self.imheight).grid(row=1, column=1, padx=(0,10), pady=6, sticky="w")

        bf = ttk.Frame(self.editor_frame); bf.pack(fill="x", padx=8, pady=(0,8))
        ttk.Button(bf, text='Resize', command=self.resize_image).pack(fill="x", pady=2)
        ttk.Button(bf, text='Undo', command=self.undo).pack(fill="x", pady=2)
        ttk.Button(bf, text='Save', command=self.save_resize).pack(fill="x", pady=2)
        ttk.Button(bf, text='Back', command=self.back).pack(fill="x", pady=8)

    def resize_image(self, save=False):
        if not self.imobject: return
        width = max(1, int(self.imwidth.get()))
        height = max(1, int(self.imheight.get()))
        self.image, self.imsize = self.imobject.resize_image(width, height, save)
        self.original_imsize = tuple(self.imsize)
        self.scale = 1.0
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor='nw', image=self.image)
        region = self.canvas.bbox("all")
        self.canvas.configure(scrollregion=region)

    def undo(self):
        if not self.imobject: return
        self.image, self.imsize = self.imobject.display_image()
        self.original_imsize = tuple(self.imsize)
        self.scale = 1.0
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor='nw', image=self.image)
        region = self.canvas.bbox("all")
        self.canvas.configure(scrollregion=region)

    def save_resize(self):
        self.resize_image(save=True)

    def back(self):
        for widget in self.editor_frame.winfo_children(): widget.destroy()
        self.draw_editor()
        self.draw_header_frame()
        self.draw_menu_frame()
        if self.filepath:
            self.header['text'] = os.path.basename(self.filepath)
            self.size['text'] = f'{self.original_imsize[0]}x{self.original_imsize[1]}'

    # ---------- Scrolling ----------
    def _drag(self, event=None):
        if self.drag:
            self.canvas.scan_dragto(event.x, event.y, gain=1)
    def _bound_to_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
    def _unbound_to_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    def _go_up(self, event):
        self.canvas.yview_scroll(-1, "units")
    def _go_down(self, event):
        self.canvas.yview_scroll(1, "units")

# ---------- Boot ----------
if __name__ == '__main__':
    root = tk.Tk()
    root.title('Sprite Cutter App (scale-accurate)')
    root.geometry(WINDOW_SIZE)
    root.resizable(True, True)

    _configure_scaling(root)
    setup_style(root)

    # Make top-level frame stretch
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)

    app = Application(master=root)
    app.mainloop()