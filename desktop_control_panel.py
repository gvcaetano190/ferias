from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

from apps.scheduler.app_control import ApplicationControlService


class ControlPanelApp:
    BG = "#e9f2fb"
    CARD = "#ffffff"
    TEXT = "#0f172a"
    MUTED = "#64748b"
    PRIMARY = "#0b5cab"
    PRIMARY_DARK = "#0d2a4d"
    SUCCESS = "#0f9d58"
    WARNING = "#f59e0b"
    DANGER = "#dc2626"

    def __init__(self) -> None:
        self.service = ApplicationControlService()
        self.root = tk.Tk()
        self.root.title("Controle de Férias")
        self.root.geometry("950x600")
        self.root.minsize(900, 550)
        self.root.configure(bg=self.BG)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.tray_icon: Icon | None = None
        self.status_value = tk.StringVar(value="Carregando...")
        self.web_value = tk.StringVar(value="Verificando...")
        self.q2_value = tk.StringVar(value="Verificando...")
        self.url_value = tk.StringVar(value=self.service.url)
        self.last_action_value = tk.StringVar(value="Painel iniciado.")
        self.logs = tk.StringVar(value=())
        self._build_styles()
        self._build_ui()
        self._append_log("Painel iniciado.")
        self.refresh_status()
        self._start_tray()
        self.root.after(1200, self._poll_queue)
        self.root.after(5000, self._auto_refresh)

    def run(self) -> None:
        self.root.mainloop()

    def _build_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Panel.TFrame", background=self.BG)
        style.configure("Card.TFrame", background=self.CARD)
        style.configure("Title.TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 24, "bold"))
        style.configure("Eyebrow.TLabel", background=self.BG, foreground=self.PRIMARY, font=("Segoe UI", 10, "bold"))
        style.configure("Body.TLabel", background=self.BG, foreground=self.MUTED, font=("Segoe UI", 11))
        style.configure("CardTitle.TLabel", background=self.CARD, foreground=self.TEXT, font=("Segoe UI", 11, "bold"))
        style.configure("CardValue.TLabel", background=self.CARD, foreground=self.TEXT, font=("Segoe UI", 15, "bold"))
        style.configure("LogTitle.TLabel", background=self.CARD, foreground=self.TEXT, font=("Segoe UI", 12, "bold"))

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, style="Panel.TFrame", padding=24)
        shell.pack(fill="both", expand=True)

        ttk.Label(shell, text="Painel de controle", style="Eyebrow.TLabel").pack(anchor="w")
        ttk.Label(shell, text="Controle de Férias", style="Title.TLabel").pack(anchor="w", pady=(4, 0))
        ttk.Label(
            shell,
            text="Gerencie a aplicação web e o worker Q2 sem usar terminal.",
            style="Body.TLabel",
        ).pack(anchor="w", pady=(8, 18))

        summary = ttk.Frame(shell, style="Panel.TFrame")
        summary.pack(fill="x")
        for column in range(4):
            summary.columnconfigure(column, weight=1)

        self._add_status_card(summary, 0, "Sistema", self.status_value)
        self._add_status_card(summary, 1, "Aplicação web", self.web_value)
        self._add_status_card(summary, 2, "Worker Q2", self.q2_value)
        self._add_status_card(summary, 3, "URL local", self.url_value)

        actions = ttk.Frame(shell, style="Card.TFrame", padding=18)
        actions.pack(fill="x", pady=18)
        ttk.Label(actions, text="Ações rápidas", style="CardTitle.TLabel").pack(anchor="w")

        button_grid = tk.Frame(actions, bg=self.CARD)
        button_grid.pack(fill="x", pady=(12, 0))
        buttons = [
            ("Iniciar sistema", self.PRIMARY, self.start_system),
            ("Pausar sistema", self.WARNING, self.stop_system),
            ("Reiniciar sistema", self.PRIMARY_DARK, self.restart_system),
            ("Abrir sistema", self.SUCCESS, self.open_system),
            ("Abrir admin", self.PRIMARY, self.open_admin),
        ]
        for index, (label, color, command) in enumerate(buttons):
            row = index // 3
            column = index % 3
            button = tk.Button(
                button_grid,
                text=label,
                bg=color,
                fg="white",
                activebackground=color,
                activeforeground="white",
                relief="flat",
                bd=0,
                cursor="hand2",
                font=("Segoe UI", 11, "bold"),
                padx=18,
                pady=12,
                command=command,
            )
            button.grid(row=row, column=column, sticky="ew", padx=6, pady=6)
        for column in range(3):
            button_grid.grid_columnconfigure(column, weight=1)

        lower = ttk.Frame(shell, style="Panel.TFrame")
        lower.pack(fill="both", expand=True)
        lower.columnconfigure(0, weight=1)
        lower.columnconfigure(1, weight=1)

        info_card = ttk.Frame(lower, style="Card.TFrame", padding=18)
        info_card.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        ttk.Label(info_card, text="Última ação", style="LogTitle.TLabel").pack(anchor="w")
        ttk.Label(
            info_card,
            textvariable=self.last_action_value,
            style="Body.TLabel",
            wraplength=280,
            justify="left",
        ).pack(anchor="w", pady=(8, 16))
        ttk.Label(info_card, text="Comportamento", style="LogTitle.TLabel").pack(anchor="w")
        ttk.Label(
            info_card,
            text="Fechar a janela minimiza o painel para a bandeja. Use o menu do ícone para abrir, iniciar, pausar ou reiniciar.",
            style="Body.TLabel",
            wraplength=280,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        logs_card = ttk.Frame(lower, style="Card.TFrame", padding=18)
        logs_card.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        ttk.Label(logs_card, text="Logs rápidos", style="LogTitle.TLabel").pack(anchor="w")
        self.log_list = tk.Listbox(
            logs_card,
            height=10,
            bg=self.CARD,
            fg=self.TEXT,
            highlightthickness=0,
            relief="flat",
            borderwidth=0,
            activestyle="none",
            font=("Segoe UI", 10),
        )
        self.log_list.pack(fill="both", expand=True, pady=(10, 0))

    def _add_status_card(self, parent: ttk.Frame, column: int, title: str, value_var: tk.StringVar) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=18)
        card.grid(row=0, column=column, sticky="nsew", padx=6)
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, textvariable=value_var, style="CardValue.TLabel").pack(anchor="w", pady=(10, 0))

    def _poll_queue(self) -> None:
        try:
            while True:
                action, message = self.queue.get_nowait()
                if action == "log":
                    self._append_log(message)
                    self.last_action_value.set(message)
                elif action == "refresh":
                    self.refresh_status()
        except queue.Empty:
            pass
        self.root.after(1200, self._poll_queue)

    def _auto_refresh(self) -> None:
        self.refresh_status()
        self.root.after(5000, self._auto_refresh)

    def refresh_status(self) -> None:
        status = self.service.status_snapshot()
        self.status_value.set(status.overall_label)
        self.web_value.set(f"Rodando ({len(status.web_processes)})" if status.web_running else "Parado")
        self.q2_value.set(f"Rodando ({len(status.qcluster_processes)})" if status.qcluster_running else "Parado")
        self.url_value.set(status.url)

    def start_system(self) -> None:
        self._run_async(self.service.start_system)

    def stop_system(self) -> None:
        self._run_async(self.service.stop_system)

    def restart_system(self) -> None:
        self._run_async(self.service.restart_system)

    def open_system(self) -> None:
        self.service.open_system()
        self._append_log("Sistema aberto no navegador.")

    def open_admin(self) -> None:
        self.service.open_admin()
        self._append_log("Admin aberto no navegador.")

    def _run_async(self, action) -> None:
        def worker() -> None:
            ok, message = action()
            prefix = "OK" if ok else "ERRO"
            self.queue.put(("log", f"{prefix}: {message}"))
            self.queue.put(("refresh", ""))

        threading.Thread(target=worker, daemon=True).start()

    def _append_log(self, message: str) -> None:
        self.log_list.insert(0, message)
        while self.log_list.size() > 8:
            self.log_list.delete(8)

    def hide_window(self) -> None:
        self.root.withdraw()
        self._append_log("Painel minimizado para a bandeja.")

    def show_window(self, icon: Icon | None = None, item=None) -> None:
        del icon, item
        self.root.after(0, self._show_window_safe)

    def _show_window_safe(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def quit_app(self, icon: Icon | None = None, item=None) -> None:
        del item
        if icon:
            icon.stop()
        self.root.after(0, self.root.destroy)

    def _start_tray(self) -> None:
        image = self._build_tray_icon()
        menu = Menu(
            MenuItem("Abrir painel", self.show_window),
            MenuItem("Abrir sistema", lambda icon, item: self.open_system()),
            MenuItem("Abrir admin", lambda icon, item: self.open_admin()),
            MenuItem("Iniciar sistema", lambda icon, item: self.start_system()),
            MenuItem("Pausar sistema", lambda icon, item: self.stop_system()),
            MenuItem("Reiniciar sistema", lambda icon, item: self.restart_system()),
            MenuItem("Sair", self.quit_app),
        )
        self.tray_icon = Icon("controle_ferias", image, "Controle de Férias", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _build_tray_icon(self) -> Image.Image:
        image = Image.new("RGBA", (64, 64), (11, 42, 77, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((6, 6, 58, 58), radius=14, fill=(11, 92, 171, 255))
        draw.rectangle((18, 18, 46, 24), fill=(255, 255, 255, 235))
        draw.rectangle((18, 30, 40, 36), fill=(255, 255, 255, 200))
        draw.rectangle((18, 42, 34, 48), fill=(255, 255, 255, 170))
        return image


def main() -> None:
    try:
        import ctypes
        # Habilita suporte a monitores de alta resolução (DPI scaling) no Windows
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = ControlPanelApp()
    app.run()


if __name__ == "__main__":
    main()
