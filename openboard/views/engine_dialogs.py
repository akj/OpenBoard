"""Progress dialogs and engine-related UI components."""

import logging
import wx
import threading

from ..engine.stockfish_manager import StockfishManager

logger = logging.getLogger(__name__)


class EngineProgressDialog(wx.Dialog):
    """Modal progress for an installation that cannot be cancelled safely."""

    def __init__(self, parent, title: str, message: str):
        super().__init__(
            parent, title=title, style=wx.DEFAULT_DIALOG_STYLE & ~wx.CLOSE_BOX
        )
        self.message = wx.StaticText(self, label=message)
        self.gauge = wx.Gauge(self, range=100, name="Installation progress")
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(self.message, 0, wx.ALL | wx.EXPAND, 12)
        layout.Add(self.gauge, 0, wx.ALL | wx.EXPAND, 12)
        self.SetSizerAndFit(layout)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _on_close(self, event):
        if event.CanVeto():
            event.Veto()
        else:
            event.Skip()

    def update_progress(self, current: int, message: str | None = None):
        self.gauge.SetValue(max(0, min(current, 100)))
        if message:
            self.message.SetLabel(message)


class EngineStatusDialog(wx.Dialog):
    """Dialog showing detailed engine status information."""

    def __init__(self, parent, manager: StockfishManager):
        super().__init__(
            parent,
            title="Engine Status",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.manager = manager
        self._create_ui()
        self._update_status()

    def _create_ui(self):
        """Create the dialog UI."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Status information panel
        status_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Stockfish Status")

        self.status_text = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=wx.Size(500, 200),
            name="Stockfish status",
        )
        status_box.Add(self.status_text, 1, wx.EXPAND | wx.ALL, 5)

        main_sizer.Add(status_box, 1, wx.EXPAND | wx.ALL, 10)

        # Action buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.refresh_btn = wx.Button(self, label="Refresh")
        self.install_btn = wx.Button(self, label="Install/Update")
        close_btn = wx.Button(self, wx.ID_CLOSE, "Close")

        button_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.install_btn, 0, wx.ALL, 5)
        button_sizer.AddStretchSpacer()
        button_sizer.Add(close_btn, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main_sizer)

        # Bind events
        self.Bind(wx.EVT_BUTTON, self._on_refresh, self.refresh_btn)
        self.Bind(wx.EVT_BUTTON, self._on_install, self.install_btn)
        self.Bind(wx.EVT_BUTTON, self._on_close, close_btn)

    def _update_status(self):
        """Show installed engines without waiting for a network request."""
        status = self.manager.get_status()
        lines = []
        if status["system_installed"]:
            lines.append(f"System engine: {status['system_path']}")
        else:
            lines.append("System engine not found")
        if status["local_installed"]:
            lines.append(f"Local engine: {status['local_path']}")
            lines.append(f"Installed version: {status['local_version'] or 'Unknown'}")
        else:
            lines.append("Local engine not installed")
        lines.append("")
        lines.append(
            "Use Check for updates to contact GitHub for the latest release."
            if status["local_installed"]
            else self.manager.get_installation_instructions()
        )
        self.status_text.SetValue("\n".join(lines))
        self.install_btn.Enable(self.manager.can_install())
        self.install_btn.SetLabel(
            "Check for updates" if status["local_installed"] else "Install"
        )

    def _on_refresh(self, event):
        """Refresh the status display."""
        self._update_status()

    def _on_install(self, event):
        """Handle install/update button."""
        self.EndModal(wx.ID_OK)  # Return OK to parent to trigger installation

    def _on_close(self, event):
        """Handle close button."""
        self.EndModal(wx.ID_CANCEL)


class EngineInstallationRunner:
    """Run network and installation work outside the GUI event loop."""

    def __init__(self, parent_window, manager: StockfishManager, engine=None):
        self.parent = parent_window
        self.manager = manager
        self.engine = engine
        self.progress_dialog = None
        self.result = None

    def start_installation(self, update: bool = False) -> bool:
        self.manager.installation_started.connect(self._on_installation_started)
        self.manager.installation_progress.connect(self._on_installation_progress)
        self.manager.installation_completed.connect(self._on_installation_completed)
        title = "Updating Stockfish" if update else "Installing Stockfish"
        try:
            with EngineProgressDialog(
                self.parent, title, "Checking the latest release..."
            ) as dialog:
                self.progress_dialog = dialog
                threading.Thread(
                    target=self._run_installation,
                    args=(update,),
                    name="OpenBoard installation",
                    daemon=True,
                ).start()
                dialog.ShowModal()
        finally:
            self.progress_dialog = None
            self.manager.installation_started.disconnect(self._on_installation_started)
            self.manager.installation_progress.disconnect(
                self._on_installation_progress
            )
            self.manager.installation_completed.disconnect(
                self._on_installation_completed
            )
        if self.result is None:
            return False
        success, message = self.result
        wx.MessageBox(
            message,
            title,
            wx.OK | (wx.ICON_INFORMATION if success else wx.ICON_ERROR),
            self.parent,
        )
        return success

    def _run_installation(self, update):
        try:
            if self.engine:
                self.engine.stop()
            if update:
                self.manager.update_stockfish()
            else:
                self.manager.install_stockfish()
        except Exception as error:
            self._on_installation_completed(
                self.manager, False, f"Installation failed: {error}"
            )

    def _update_progress(self, current, message):
        if self.progress_dialog:
            self.progress_dialog.update_progress(current, message)

    def _on_installation_started(self, sender, version):
        wx.CallAfter(self._update_progress, 0, f"Installing Stockfish {version}...")

    def _on_installation_progress(self, sender, message, current, total):
        percentage = int(current * 100 / total) if total > 0 else 0
        wx.CallAfter(self._update_progress, percentage, message)

    def _on_installation_completed(self, sender, success, message):
        wx.CallAfter(self._complete, success, message)

    def _complete(self, success, message):
        if self.progress_dialog and self.result is None:
            self.result = success, message
            self.progress_dialog.EndModal(wx.ID_OK if success else wx.ID_CANCEL)
