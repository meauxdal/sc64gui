# sc64gui.py - SummerCart64 Deployment Utility
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk, simpledialog, messagebox
import subprocess
import threading
import os
import sys
import posixpath
import json

# Enable High-DPI awareness for Windows environments
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- Theme Configuration ---
BG       = "#CCCCCC"
BG2      = "#EEEEEE"
BG3      = "#999999"
FG       = "#000000"
FG_DIM   = "#444444"

TERM_BG  = "#000000"
TERM_FG  = "#00FF00"

FONT_NORMAL   = ("Segoe UI", 9)
FONT_BOLD     = ("Segoe UI", 9, "bold")
FONT_HDR      = ("Segoe UI", 12, "bold")
FONT_TERMINAL = ("Consolas", 10)

BTN = dict(bg=BG, fg=FG, activebackground=BG2, activeforeground=FG,
           font=FONT_BOLD, bd=2, relief="raised", cursor="arrow")

BTN_WIDE = BTN.copy()
BTN_WIDE.update(width=18)

BTN_SM = BTN.copy()
BTN_SM.update(font=FONT_NORMAL, width=12)

CONFIG_FILE = "sc64_settings.json"

def deployer_path():
    base = os.path.dirname(os.path.abspath(sys.argv[0]))
    exe = "sc64deployer.exe" if os.name == "nt" else "sc64deployer"
    local = os.path.join(base, exe)
    return local if os.path.exists(local) else f"./{exe}"

class SC64Gui:
    def __init__(self, root):
        self.root = root
        self.root.title("sc64deployer")
        self.root.geometry("740x820")
        self.root.configure(bg=BG)
        
        self._conn_port   = tk.StringVar()
        self._conn_remote = tk.StringVar()
        self._rom_info    = tk.StringVar(value="No Rom selected")

        self._load_settings()
        self._build_header()
        self._build_conn_bar()
        self._build_rom_inspector()
        self._build_tabs()
        self._build_console()
        self._build_statusbar()

        self.root.after(100, self.check_status)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=BG, pady=10)
        hdr.pack(fill=tk.X, padx=16)
        tk.Label(hdr, text="⬡ SummerCart64", bg=BG, fg=FG, font=FONT_HDR).pack(side=tk.LEFT)
        tk.Button(hdr, text="Refresh", command=self.check_status, **BTN_SM).pack(side=tk.RIGHT, padx=4)
        self.status_label = tk.Label(hdr, text="Initializing...", bg=BG, fg="#884400", font=FONT_BOLD)
        self.status_label.pack(side=tk.RIGHT, padx=12)

    def _build_conn_bar(self):
        bar = tk.Frame(self.root, bg=BG3, pady=6, bd=1, relief="sunken")
        bar.pack(fill=tk.X, padx=12, pady=4)
        cfg = dict(bg="white", fg="black", font=FONT_NORMAL, bd=1, relief="sunken", width=15)
        tk.Label(bar, text="Port:", bg=BG3, fg=FG, font=FONT_NORMAL).pack(side=tk.LEFT, padx=(10, 2))
        tk.Entry(bar, textvariable=self._conn_port, **cfg).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(bar, text="Remote:", bg=BG3, fg=FG, font=FONT_NORMAL).pack(side=tk.LEFT, padx=(0, 2))
        tk.Entry(bar, textvariable=self._conn_remote, **cfg).pack(side=tk.LEFT)

    def _build_rom_inspector(self):
        ins = tk.Frame(self.root, bg=BG2, pady=8, bd=1, relief="groove")
        ins.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(ins, text="Rom info:", bg=BG2, fg=FG_DIM, font=FONT_BOLD).pack(side=tk.LEFT, padx=10)
        tk.Label(ins, textvariable=self._rom_info, bg=BG2, fg=FG, font=FONT_NORMAL).pack(side=tk.LEFT)

    def _build_tabs(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG, foreground=FG, font=FONT_NORMAL, padding=[12, 4])
        style.map("TNotebook.Tab", background=[("selected", BG2)])
        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.X, padx=12, pady=4)
        self._tab_main(nb)
        self._tab_sd(nb)
        self._tab_tools(nb)

    def _tab_frame(self, nb, label):
        f = tk.Frame(nb, bg=BG, pady=15, bd=2, relief="groove")
        nb.add(f, text=f" {label} ")
        return f

    def _tab_main(self, nb):
        f = self._tab_frame(nb, "Main")
        grid = tk.Frame(f, bg=BG)
        grid.pack(expand=True)
        
        tk.Button(grid, text="Upload ROM", command=self.upload_rom, **BTN_WIDE).grid(row=0, column=0, padx=6, pady=6)
        tk.Button(grid, text="Device Info", command=self.check_status, **BTN_WIDE).grid(row=0, column=1, padx=6, pady=6)
        tk.Button(grid, text="Download Save", command=self.download_save, **BTN_WIDE).grid(row=0, column=2, padx=6, pady=6)
        
        tk.Button(grid, text="Sync RTC", command=self.sync_rtc, **BTN_WIDE).grid(row=1, column=0, padx=6, pady=6)
        tk.Button(grid, text="Reset", command=self.reset_device, **BTN_WIDE).grid(row=1, column=1, padx=6, pady=6)
        tk.Button(grid, text="List Items", command=lambda: self.run_cmd(["list"]), **BTN_WIDE).grid(row=1, column=2, padx=6, pady=6)
        
        r3 = tk.Frame(f, bg=BG)
        r3.pack(pady=8)
        tk.Button(r3, text="LED Blink", command=lambda: self.run_cmd(["set", "blink-on"]), **BTN_SM).pack(side=tk.LEFT, padx=3)
        tk.Button(r3, text="LED Off", command=lambda: self.run_cmd(["set", "blink-off"]), **BTN_SM).pack(side=tk.LEFT, padx=3)

    def _tab_sd(self, nb):
        f = self._tab_frame(nb, "SD Card")
        path_row = tk.Frame(f, bg=BG); path_row.pack(fill=tk.X, padx=20, pady=6)
        self.sd_path = tk.Entry(path_row, bg="white", font=FONT_NORMAL, bd=1, relief="sunken")
        self.sd_path.insert(0, "/"); self.sd_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(path_row, text="List Dir", command=self.sd_ls, **BTN_SM).pack(side=tk.LEFT)
        
        grid = tk.Frame(f, bg=BG); grid.pack(pady=6, expand=True)
        tk.Button(grid, text="Upload", command=self.sd_upload, **BTN_WIDE).grid(row=0, column=0, padx=6, pady=6)
        tk.Button(grid, text="Download", command=self.sd_download, **BTN_WIDE).grid(row=0, column=1, padx=6, pady=6)
        tk.Button(grid, text="Make Dir", command=self.sd_mkdir, **BTN_WIDE).grid(row=1, column=0, padx=6, pady=6)
        tk.Button(grid, text="Remove Item", command=self.sd_rm, **BTN_WIDE).grid(row=1, column=1, padx=6, pady=6)

    def _tab_tools(self, nb):
        f = self._tab_frame(nb, "Tools")
        grid = tk.Frame(f, bg=BG); grid.pack(expand=True)
        cmds = [("Firmware Info", self.firmware_info), ("Firmware Update", self.firmware_update), 
                ("Start Server", self.start_server), ("Dump Memory", self.dump_memory), ("64DD Mode", self.launch_64dd)]
        for i, (txt, cmd) in enumerate(cmds):
            row, col = divmod(i, 2)
            tk.Button(grid, text=txt, command=cmd, **BTN_WIDE).grid(row=row, column=col, padx=6, pady=6)

    def _build_console(self):
        hdr = tk.Frame(self.root, bg=BG); hdr.pack(fill=tk.X, padx=16)
        tk.Label(hdr, text="Terminal Output", bg=BG, fg=FG_DIM, font=FONT_NORMAL).pack(side=tk.LEFT)
        tk.Button(hdr, text="Export Log", command=self.export_log, bg=BG, font=FONT_NORMAL, bd=1, relief="raised").pack(side=tk.RIGHT, padx=4)
        tk.Button(hdr, text="Clear", command=self.clear_log, bg=BG, font=FONT_NORMAL, bd=1, relief="raised").pack(side=tk.RIGHT)
        
        self.output_area = scrolledtext.ScrolledText(self.root, height=18, bg=TERM_BG, fg=TERM_FG, insertbackground=TERM_FG, font=FONT_TERMINAL, borderwidth=2, relief="sunken")
        self.output_area.pack(padx=12, pady=(2, 8), fill=tk.BOTH, expand=True)
        for t, c in [("ok",TERM_FG), ("err","#ff4444"), ("warn","#ffaa00"), ("dim","#007700")]:
            self.output_area.tag_config(t, foreground=c)

    def _build_statusbar(self):
        self.sb_label = tk.Label(self.root, text="", bg=BG, fg=FG_DIM, font=FONT_NORMAL, anchor="w", bd=1, relief="sunken")
        self.sb_label.pack(fill=tk.X, side=tk.BOTTOM)

    def sb(self, text): self.sb_label.config(text=f" Status: {text}")
    def log(self, text, tag="ok"): self.output_area.insert(tk.END, text, tag); self.output_area.see(tk.END)
    def clear_log(self): self.output_area.delete(1.0, tk.END)
    def log_sep(self, label=""): self.log(f"\n{'─'*20} {label} {'─'*20}\n" if label else f"\n{'─'*52}\n", "dim")

    def _load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self._conn_port.set(data.get("port", ""))
                    self._conn_remote.set(data.get("remote", ""))
            except: pass

    def _save_settings(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"port": self._conn_port.get(), "remote": self._conn_remote.get()}, f)

    def _on_close(self):
        self._save_settings()
        self.root.destroy()

    def _get_rom_name(self, path):
        try:
            with open(path, 'rb') as f:
                f.seek(0x20); name = f.read(20).decode('latin-1').strip()
                f.seek(0x3B); cid = f.read(4).decode('latin-1').strip()
                return f"{name} [{cid}]"
        except: return "Unknown Rom"

    def _conn_flags(self):
        flags = []
        p, r = self._conn_port.get().strip(), self._conn_remote.get().strip()
        if p: flags += ["-p", p]
        if r: flags += ["-r", r]
        return flags

    def check_status(self):
        self.clear_log(); self.log_sep("Device Info")
        try:
            r = subprocess.run([deployer_path()] + self._conn_flags() + ["info"], capture_output=True, text=True)
            if r.returncode == 0:
                self.log(r.stdout); self.status_label.config(text="Connected", fg="#008800")
                self.sb("Ready.")
            else:
                self.log(r.stderr or "Device not found.\n", "err")
                self.status_label.config(text="Disconnected", fg="#AA0000"); self.sb("Check connection.")
        except: self.status_label.config(text="Exe missing", fg="#AA0000")

    def run_cmd(self, args, label=None):
        self.clear_log(); self.log_sep(label or " ".join(args))
        threading.Thread(target=self._execute, args=(args, self._conn_flags()), daemon=True).start()

    def _execute(self, args, conn_flags):
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            proc = subprocess.Popen([deployer_path()] + conn_flags + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True, startupinfo=startupinfo)
            for line in proc.stdout:
                l = line.lower()
                tag = "err" if "error" in l or "fail" in l else "warn" if "warn" in l else "ok"
                self.root.after(0, self.log, line, tag)
            proc.wait(); self.root.after(0, self.sb, f"Done: {proc.returncode}")
        except Exception as e: self.root.after(0, self.log, f"\nError: {e}\n", "err")

    def upload_rom(self):
        p = filedialog.askopenfilename(filetypes=[("N64 Roms", "*.n64 *.z64 *.v64")])
        if p: self._rom_info.set(self._get_rom_name(p)); self.run_cmd(["upload", p])
    
    def download_save(self):
        p = filedialog.asksaveasfilename(defaultextension=".sav")
        if p: self.run_cmd(["download", "save", p])

    def export_log(self):
        p = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="sc64_log.txt")
        if p:
            with open(p, 'w', encoding='utf-8') as f: f.write(self.output_area.get(1.0, tk.END))
            self.sb("Log exported.")

    def sync_rtc(self): self.run_cmd(["set", "rtc"])
    def reset_device(self): self.run_cmd(["reset"])
    def sd_ls(self): self.run_cmd(["sd", "ls", self.sd_path.get()])
    def sd_upload(self):
        l = filedialog.askopenfilename(title="Select Rom to upload")
        if l:
            r = simpledialog.askstring("SD Path", "Dest:", initialvalue=posixpath.join(self.sd_path.get(), os.path.basename(l)))
            if r: self.run_cmd(["sd", "upload", l, r])
    def sd_download(self):
        r = simpledialog.askstring("SD Path", "Source Rom path:", initialvalue=self.sd_path.get())
        if r:
            l = filedialog.asksaveasfilename(initialfile=os.path.basename(r))
            if l: self.run_cmd(["sd", "download", r, l])
    def sd_mkdir(self):
        p = simpledialog.askstring("SD", "New Dir:", initialvalue=self.sd_path.get())
        if p: self.run_cmd(["sd", "mkdir", p])
    def sd_rm(self):
        p = simpledialog.askstring("SD", "Delete:", initialvalue=self.sd_path.get())
        if p and messagebox.askyesno("Delete", f"Confirm {p}?"): self.run_cmd(["sd", "rm", p])
    def firmware_info(self):
        p = filedialog.askopenfilename()
        if p: self.run_cmd(["firmware", "info", p])
    def firmware_update(self):
        p = filedialog.askopenfilename()
        if p and messagebox.askyesno("Update", "Flash firmware?"): self.run_cmd(["firmware", "update", p])
    def start_server(self): self.run_cmd(["server"])
    def dump_memory(self):
        a = simpledialog.askstring("Dump", "Addr:", initialvalue="0x10000000")
        l = simpledialog.askstring("Dump", "Len:", initialvalue="0x1000")
        if a and l:
            p = filedialog.asksaveasfilename(defaultextension=".bin")
            if p: self.run_cmd(["dump", a, l, p])
    def launch_64dd(self):
        i = filedialog.askopenfilename(title="IPL Rom")
        if i:
            d = filedialog.askopenfilename(title="Disk (Optional)")
            self.run_cmd(["64dd", i, d] if d else ["64dd", i])

if __name__ == "__main__":
    root = tk.Tk()
    SC64Gui(root)
    root.mainloop()