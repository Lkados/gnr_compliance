import frappe
from frappe.model.document import Document

class GNRMovementLog(Document):
    def before_insert(self):
        if not self.user:
            self.user = frappe.session.user
        if not self.timestamp:
            self.timestamp = frappe.utils.now_datetime()