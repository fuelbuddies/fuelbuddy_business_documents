# Copyright (c) 2026, Fuelbuddy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Shared "Fuelbuddy Settings" single (hosted in fuelbuddy_crm): the "document_required"
# flag gates document enforcement across the deal flow. Same semantics as
# fuelbuddy_finance_dossier's documents_required().
FB_SETTINGS_DOCTYPE = "Fuelbuddy Settings"


def documents_enforced():
	"""True when Business Documents are enforced ("Document Required" in Fuelbuddy
	Settings). Defaults to enforced when the flag has never been set. Read straight
	from tabSingles because ``get_single_value`` casts a missing Check field to 0,
	hiding "never set"."""
	row = frappe.db.sql(
		"select value from `tabSingles` where doctype=%s and field=%s",
		(FB_SETTINGS_DOCTYPE, "document_required"),
	)
	if not row:
		return True
	return bool(frappe.utils.cint(row[0][0]))


class BusinessDocumentation(Document):
	def before_save(self):
		self.guard_submitted_reference()

	def guard_submitted_reference(self):
		"""Block uploading/changing documents on a submitted reference document.
		Not enforced when "Document Required" is off in Fuelbuddy Settings."""
		if not documents_enforced():
			return

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
