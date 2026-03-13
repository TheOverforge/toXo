"""CategoriesMixin — category CRUD and task-category assignment."""
from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QMessageBox

from shared.i18n import tr


class CategoriesMixin:
    """Mixin: refresh_categories, category CRUD, task-drag-to-category."""

    def refresh_categories(self):
        self.categories = self.category_svc.list_categories()
        all_count = sum(1 for t in self.all_tasks if not t.is_archived)
        self.category_bar.load_categories(self.categories, all_count)
        if self.current_category_id is not None:
            self.category_bar.select_category(self.current_category_id)

    def on_category_selected(self, category_id: int):
        self.save_current_task_if_dirty()
        self.current_category_id = category_id
        if category_id == -1:
            self.filter_mode = self.FILTER_ALL
        else:
            self.filter_mode = self.FILTER_CATEGORY
        self.apply_filter(keep_selection=True)

    def on_add_category(self):
        from entities.task.ui.task_list import CategoryEditDialog
        dialog = CategoryEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, color = dialog.get_data()
            if name:
                try:
                    new_id = self.category_svc.create_category(name, color)
                    self.refresh_categories()
                    self.category_bar.select_category(new_id)
                    self.on_category_selected(new_id)
                except Exception as e:
                    self.show_error(tr("err.create_cat", e=e))

    def on_category_rename(self, category_id: int):
        from entities.task.ui.task_list import CategoryEditDialog
        cat = self.category_svc.get_category(category_id)
        if not cat:
            return
        dialog = CategoryEditDialog(category=cat, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, color = dialog.get_data()
            if name:
                try:
                    self.category_svc.update_category(category_id, name, color)
                    self.refresh_categories()
                except Exception as e:
                    self.show_error(tr("err.update_cat", e=e))

    def on_category_delete(self, category_id: int):
        cat = self.category_svc.get_category(category_id)
        if not cat:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr("dlg.del_cat_title"))
        box.setText(tr("dlg.del_cat_text", name=cat.name))
        box.setInformativeText(tr("dlg.del_cat_hint", count=cat.task_count))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)

        if box.exec() == QMessageBox.StandardButton.Yes:
            try:
                self.category_svc.delete_category(category_id)
                self.current_category_id = -1
                self.refresh()
                self.refresh_categories()
            except Exception as e:
                self.show_error(tr("err.delete_cat", e=e))

    def on_category_reordered(self, dragged_id: int, target_id: int):
        order = [c.id for c in self.categories]
        if dragged_id in order and target_id in order:
            order.remove(dragged_id)
            target_idx = order.index(target_id)
            order.insert(target_idx, dragged_id)
            try:
                self.category_svc.reorder_categories(order)
                self.refresh_categories()
            except Exception as e:
                self.show_error(tr("err.reorder", e=e))

    def on_task_dropped_to_category(self, task_ids, category_id: int):
        if isinstance(task_ids, int):
            task_ids = [task_ids]
        try:
            for tid in task_ids:
                self.category_svc.set_task_category(tid, category_id)
            self.refresh()
            self.refresh_categories()
        except Exception as e:
            self.show_error(tr("err.move_task", e=e))

    def move_task_to_category(self, task_id: int, category_id):
        try:
            self.category_svc.set_task_category(task_id, category_id)
            self.refresh()
            self.refresh_categories()
        except Exception as e:
            self.show_error(tr("err.move_task", e=e))
