# Copyright (c) 2026, Fuelbuddy and contributors
# For license information, please see license.txt

"""The business_doc_* Server Scripts moved into the app as
fuelbuddy_business_documents.api (whitelisted get_docs/add_version/force_save and
the daily expire_documents scheduler task). Delete the DB scripts so the old
/api/method/business_doc_* endpoints and the duplicate scheduler job disappear;
they are also gone from the app's fixtures, so sync-fixtures won't re-create them."""

import frappe

_SCRIPTS = (
	"business_doc_get_docs",
	"business_doc_add_version",
	"business_doc_force_save",
	"business_doc_expiry",
)


def execute():
	for name in _SCRIPTS:
		if frappe.db.exists("Server Script", name):
			frappe.delete_doc("Server Script", name, ignore_permissions=True, force=True)
