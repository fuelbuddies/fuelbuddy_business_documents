# Copyright (c) 2026, Fuelbuddy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

ALLOWED_EXTENSIONS = ("pdf", "jpg", "jpeg", "png")


class BusinessDocumentation(Document):
	def before_save(self):
		self.validate_attachment_type()
		self.validate_expiry()
		self.guard_submitted_reference()

	def validate_expiry(self):
		"""Expiry date is mandatory whenever a document is attached."""
		if self.attachment and not self.expiry:
			frappe.throw("Expiry date is mandatory when uploading a document.")

	def validate_attachment_type(self):
		"""Attachment must be a PDF/JPG/JPEG/PNG file."""
		fname = (self.attachment or "").lower().split("?")[0]
		ext = fname.rsplit(".", 1)[-1] if "." in fname else ""
		if ext not in ALLOWED_EXTENSIONS:
			frappe.throw(
				f"Attachment must be a PDF, JPG, JPEG or PNG file (got: .{ext or '?'})"
			)

	def guard_submitted_reference(self):
		"""Block uploading/changing documents on a submitted reference document."""
		if not (self.reference_doctype and self.reference_name):
			return

		if frappe.db.get_value(self.reference_doctype, self.reference_name, "docstatus") != 1:
			return

		attachment_changed = self.is_new() or (
			self.attachment
			!= frappe.db.get_value("Business Documentation", self.name, "attachment")
		)
		if attachment_changed:
			frappe.throw(
				f"Cannot upload or change documents on a submitted {self.reference_doctype}."
			)
