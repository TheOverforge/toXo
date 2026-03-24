"""SystemMixin — tray icon, notifications, reminders, deadlines, autostart, closeEvent."""
from __future__ import annotations

from pathlib import Path
from shared.config.paths import IMAGES_DIR, SOUNDS_DIR

from PyQt6.QtWidgets import QMenu, QApplication, QSystemTrayIcon
from PyQt6.QtCore import Qt, QTimer

from shared.i18n import tr


class SystemMixin:
    """Mixin: closeEvent, tray, reminder timer, autostart, toast notifications,
    reminder/deadline checks, auto-archive."""

    def closeEvent(self, event):
        if hasattr(self, "tray") and self.tray.isSystemTrayAvailable() and self.tray.isVisible():
            event.ignore()
            self.hide()
            self._show_notification(
                tr("tray.bg_title"),
                tr("tray.bg_body"),
            )
        else:
            try:
                self.save_current_task_if_dirty()
                self.svc.close()
            finally:
                super().closeEvent(event)

    def _setup_tray(self):
        icon_path = IMAGES_DIR / "app_icon.png"
        from PyQt6.QtGui import QIcon
        tray_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()

        self.tray = QSystemTrayIcon(tray_icon, self)
        self.tray.setToolTip("toXo")

        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu {
                background: #1c1c1e;
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 8px;
                color: #f5f5f7;
                font-size: 13px;
                padding: 4px 0;
            }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background: rgba(10,132,255,0.35); }
            QMenu::separator { height: 1px; background: rgba(255,255,255,0.1); margin: 4px 0; }
        """)

        self._tray_action_show = tray_menu.addAction(tr("tray.open"))
        self._tray_action_show.triggered.connect(self._restore_from_tray)
        tray_menu.addSeparator()
        self._tray_action_settings = tray_menu.addAction(tr("tray.settings"))
        self._tray_action_settings.triggered.connect(self.toggle_settings)
        tray_menu.addSeparator()
        self._tray_action_quit = tray_menu.addAction(tr("tray.quit"))
        self._tray_action_quit.triggered.connect(self._quit_app)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _setup_reminder_timer(self):
        self._reminder_timer = QTimer(self)
        self._reminder_timer.setInterval(10_000)
        self._reminder_timer.timeout.connect(self._check_reminders)
        self._reminder_timer.start()
        QTimer.singleShot(2000, self._check_reminders)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_from_tray()

    def _restore_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_app(self):
        if hasattr(self, "_reminder_timer"):
            self._reminder_timer.stop()
        self.tray.hide()
        try:
            self.save_current_task_if_dirty()
            self.svc.close()
        finally:
            QApplication.quit()

    def _is_autostart_enabled(self) -> bool:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ,
            )
            winreg.QueryValueEx(key, "toXo")
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def _set_autostart(self, enabled: bool) -> None:
        import sys
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            if enabled:
                python = Path(sys.executable)
                pythonw = python.parent / "pythonw.exe"
                if not pythonw.exists():
                    pythonw = python
                main = Path(__file__).resolve().parent.parent / "main.py"
                winreg.SetValueEx(key, "toXo", 0, winreg.REG_SZ,
                                  f'"{pythonw}" "{main}"')
            else:
                try:
                    winreg.DeleteValue(key, "toXo")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            self.show_error(tr("err.autostart", e=e))

    def _show_windows_toast(self, title: str, body: str) -> None:
        import subprocess
        import base64

        icon_path = IMAGES_DIR / "app_icon.png"
        sound_key = self._settings.value("notification_sound", "toXo_default")
        sound_path = SOUNDS_DIR / f"{sound_key}.wav" if sound_key else None
        has_custom_sound = bool(sound_path and sound_path.exists())

        def ps_sq(s: str) -> str:
            return s.replace("'", "''")

        t = ps_sq(title)
        b = ps_sq(body)

        if icon_path.exists():
            icon_uri = ps_sq(icon_path.as_uri())
            template = 'ToastImageAndText02'
            img_line = f"$doc.GetElementsByTagName('image').Item(0).SetAttribute('src','{icon_uri}');"
        else:
            template = 'ToastText02'
            img_line = ''

        if has_custom_sound:
            audio_line = '$audio=$doc.CreateElement("audio");$audio.SetAttribute("silent","true");$doc.DocumentElement.AppendChild($audio)|Out-Null;'
        else:
            audio_line = '$audio=$doc.CreateElement("audio");$audio.SetAttribute("src","ms-winsoundevent:Notification.Reminder");$doc.DocumentElement.AppendChild($audio)|Out-Null;'

        ps = (
            '[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]|Out-Null;'
            f'$doc=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::{template});'
            f"$doc.GetElementsByTagName('text').Item(0).InnerText='{t}';"
            f"$doc.GetElementsByTagName('text').Item(1).InnerText='{b}';"
            f'{img_line}'
            f'{audio_line}'
            '$n=[Windows.UI.Notifications.ToastNotification]::new($doc);'
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('toXo').Show($n)"
        )

        encoded = base64.b64encode(ps.encode("utf-16-le")).decode("ascii")
        subprocess.Popen(
            ["powershell", "-NonInteractive", "-WindowStyle", "Hidden",
             "-EncodedCommand", encoded],
            creationflags=0x08000000,
        )

        if has_custom_sound and sound_path:
            try:
                import winsound
                winsound.PlaySound(
                    str(sound_path),
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                )
            except Exception:
                pass

    def _show_notification(self, title: str, body: str) -> None:
        import platform
        if platform.system() == "Windows":
            try:
                self._show_windows_toast(title, body)
                return
            except Exception:
                pass
        self.tray.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 8000)

    def _check_reminders(self):
        try:
            due = self.svc.get_due_reminders()
        except Exception:
            return

        for task in due:
            title = (task.title or tr("editor.untitled")).strip()
            self._show_notification(tr("notif.remind_title", title=title), tr("notif.remind_body"))
            try:
                self.svc.mark_reminder_shown(task.id)
                if self.current_task_id == task.id:
                    updated = self.svc.get_task(task.id)
                    if updated:
                        self._update_reminder_label(updated)
            except Exception:
                pass

        self._check_deadlines()
        self._auto_archive_check()

    def _auto_archive_check(self):
        days = self._archive_auto_days
        if days <= 0:
            return
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        try:
            n = self.svc.archive_completed_tasks(older_than=cutoff)
            if n > 0:
                self.all_tasks = self.svc.list_tasks()
                self.apply_filter(keep_selection=True)
        except Exception:
            pass

    def _check_deadlines(self):
        from datetime import datetime, timezone, date
        now = datetime.now(timezone.utc)
        today = date.today()

        for task in self.all_tasks:
            if task.is_archived or task.is_done or not task.deadline_at:
                continue
            try:
                dl = datetime.fromisoformat(task.deadline_at)
                if dl.tzinfo is None:
                    dl = dl.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            dl_local_date = dl.astimezone().date()
            title = (task.title or tr("editor.untitled")).strip()

            if task.deadline_notified < 2 and dl <= now:
                self._show_notification(
                    tr("notif.deadline_passed_title", title=title),
                    tr("notif.deadline_passed_body"),
                )
                try:
                    self.svc.mark_deadline_notified(task.id, 2)
                    task.deadline_notified = 2
                    if self.current_task_id == task.id:
                        updated = self.svc.get_task(task.id)
                        if updated:
                            self._update_deadline_label(updated)
                except Exception:
                    pass

            elif task.deadline_notified == 0 and dl_local_date == today:
                self._show_notification(
                    tr("notif.deadline_today_title", title=title),
                    tr("notif.deadline_today_body"),
                )
                try:
                    self.svc.mark_deadline_notified(task.id, 1)
                    task.deadline_notified = 1
                except Exception:
                    pass
