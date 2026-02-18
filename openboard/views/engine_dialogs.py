"""Progress dialogs and engine-related UI components."""

import logging
import wx
import threading

from ..engine.stockfish_manager import StockfishManager

logger = logging.getLogger(__name__)


class EngineProgressDialog(wx.ProgressDialog):
    """
    Progress dialog for engine installation/update operations.
    """

    def __init__(self, parent, title: str, message: str):
        super().__init__(
            title=title,
            message=message,
            maximum=100,
            parent=parent,
            style=wx.PD_AUTO_HIDE | wx.PD_APP_MODAL | wx.PD_CAN_ABORT | wx.PD_SMOOTH,
        )

        self.was_cancelled = False
        self._is_showing_modal = False

    def ShowModal(self):
        """Override ShowModal to track modal state."""
        try:
            self._is_showing_modal = True
            return super().ShowModal()
        finally:
            self._is_showing_modal = False

    def EndModal(self, retCode):
        """Override EndModal to safely handle state."""
        if self._is_showing_modal:
            self._is_showing_modal = False
            super().EndModal(retCode)
        else:
            logger.warning("EndModal called on non-modal dialog, ignoring")

    def update_progress(self, current: int, message: str | None = None):
        """Update progress and optionally change message."""
        try:
            if message:
                continue_flag, skip_flag = self.Update(current, message)
            else:
                continue_flag, skip_flag = self.Update(current)

            # Check if user cancelled
            if not continue_flag:
                self.was_cancelled = True
                return False

            return True

        except Exception as e:
            logger.warning(f"Progress dialog update failed: {e}")
            return False


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
            self, style=wx.TE_MULTILINE | wx.TE_READONLY, size=wx.Size(500, 200)
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
        """Update the status display."""
        status = self.manager.get_status()

        lines = ["=== Stockfish Engine Status ===\n"]

        # Platform support
        if status["platform_supported"]:
            lines.append("✓ Platform: Windows (automatic installation supported)")
        else:
            lines.append(
                f"⚠ Platform: {status.get('platform', 'Unknown')} (manual installation required)"
            )

        lines.append("")

        # System installation
        if status["system_installed"]:
            lines.append("✓ System Installation: Found")
            lines.append(f"  Path: {status['system_path']}")
        else:
            lines.append("✗ System Installation: Not found")

        lines.append("")

        # Local installation
        if status["local_installed"]:
            lines.append("✓ Local Installation: Found")
            lines.append(f"  Path: {status['local_path']}")
            lines.append(f"  Version: {status['local_version'] or 'Unknown'}")

            if status["latest_version"]:
                lines.append(f"  Latest Version: {status['latest_version']}")
                if status["update_available"]:
                    lines.append("  📥 Update available!")
                else:
                    lines.append("  ✓ Up to date")
        else:
            lines.append("✗ Local Installation: Not found")
            if status["latest_version"]:
                lines.append(f"  Latest Version Available: {status['latest_version']}")

        lines.append("")

        # Best path recommendation
        best_path = self.manager.get_best_engine_path()
        if best_path:
            lines.append(f"🎯 Active Engine: {best_path}")
        else:
            lines.append("❌ No engine available")

        lines.append("")

        # Installation instructions
        if not status["local_installed"] or status["update_available"]:
            lines.append("📋 Installation Instructions:")
            instructions = self.manager.get_installation_instructions()
            lines.append(f"   {instructions}")

        self.status_text.SetValue("\n".join(lines))

        # Update button states
        can_install = self.manager.can_install()
        self.install_btn.Enable(can_install)

        if status["local_installed"] and status["update_available"]:
            self.install_btn.SetLabel("Update Available")
        elif status["local_installed"]:
            self.install_btn.SetLabel("Reinstall")
        else:
            self.install_btn.SetLabel("Install")

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
    """
    Manages the installation process with progress feedback.
    Runs installation in a background thread and updates GUI.
    """

    def __init__(self, parent_window, manager: StockfishManager):
        self.parent = parent_window
        self.manager = manager
        self.progress_dialog: EngineProgressDialog | None = None
        self.installation_thread: threading.Thread | None = None

        # Connect to manager signals
        self.manager.installation_started.connect(self._on_installation_started)
        self.manager.installation_progress.connect(self._on_installation_progress)
        self.manager.installation_completed.connect(self._on_installation_completed)

    def start_installation(self) -> bool:
        """
        Start the installation process.

        Returns:
            True if installation was started, False if already running
        """
        if self.installation_thread and self.installation_thread.is_alive():
            return False

        # Create progress dialog
        self.progress_dialog = EngineProgressDialog(
            self.parent, "Installing Stockfish", "Preparing installation..."
        )

        # Start installation in background thread
        self.installation_thread = threading.Thread(
            target=self._run_installation, daemon=True
        )
        self.installation_thread.start()

        # Show modal progress dialog immediately - this is safer than wx.CallAfter
        try:
            result = self.progress_dialog.ShowModal()
            return result != wx.ID_CANCEL
        except Exception as e:
            logger.error(f"Failed to show progress dialog: {e}")
            return False

    def _run_installation(self):
        """Run installation in background thread."""
        try:
            self.manager.install_stockfish()
        except Exception as e:
            # Ensure completion signal is sent even on exception
            error_msg = f"Installation failed: {str(e)}"
            wx.CallAfter(
                lambda: self.manager.installation_completed.send(
                    self.manager, success=False, message=error_msg
                )
            )

    def _on_installation_started(self, sender, version):
        """Handle installation started signal."""

        def update_ui():
            if self.progress_dialog:
                self.progress_dialog.update_progress(
                    0, f"Installing Stockfish {version}..."
                )

        wx.CallAfter(update_ui)

    def _on_installation_progress(self, sender, message, current, total):
        """Handle installation progress signal."""

        def update_ui():
            if self.progress_dialog and not self.progress_dialog.was_cancelled:
                # Calculate percentage
                if total > 0:
                    percent = int((current / total) * 100)
                else:
                    percent = 0

                self.progress_dialog.update_progress(percent, message)

        wx.CallAfter(update_ui)

    def _on_installation_completed(self, sender, success, message):
        """Handle installation completed signal."""

        def update_ui():
            try:
                if self.progress_dialog:
                    # Update progress to 100%
                    self.progress_dialog.update_progress(
                        100,
                        "Installation complete!" if success else "Installation failed!",
                    )

                    # Safely close the dialog using our custom modal tracking
                    try:
                        if (
                            hasattr(self.progress_dialog, "_is_showing_modal")
                            and self.progress_dialog._is_showing_modal
                        ):
                            self.progress_dialog.EndModal(
                                wx.ID_OK if success else wx.ID_CANCEL
                            )
                        else:
                            # Dialog not modal, try to close it normally
                            self.progress_dialog.Close()
                    except Exception as e:
                        logger.warning(f"Could not close progress dialog normally: {e}")
                        # Force close if needed
                        try:
                            self.progress_dialog.Destroy()
                        except Exception:
                            pass

                    # Clear the dialog reference
                    self.progress_dialog = None

                    # Show completion message after dialog is closed
                    wx.CallAfter(self._show_completion_message, success, message)

            except Exception as e:
                logger.error(f"Error in installation completion handler: {e}")

        wx.CallAfter(update_ui)

    def _show_completion_message(self, success: bool, message: str):
        """Show the final completion message after dialog cleanup."""
        try:
            if success:
                wx.MessageBox(
                    message, "Installation Complete", wx.OK | wx.ICON_INFORMATION
                )
            else:
                wx.MessageBox(message, "Installation Failed", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            logger.error(f"Failed to show completion message: {e}")
